# install_drivers.ps1 - Install VirtIO and System Drivers
#
# Installs VirtIO drivers for Proxmox VM and ensures all
# necessary system drivers are properly configured.
#
# Usage: Run as Administrator in PowerShell
#   .\install_drivers.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "SilentlyContinue"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $color = switch ($Level) {
        "INFO" { "Green" }
        "WARN" { "Yellow" }
        "ERROR" { "Red" }
        default { "White" }
    }
    Write-Host "[$timestamp] [$Level] $Message" -ForegroundColor $color
}

function Find-VirtIODrive {
    Write-Log "Searching for VirtIO driver source..."

    # Check for mounted ISO
    $cdDrives = Get-WmiObject -Class Win32_CDROMDrive |
        Where-Object { $_.VolumeName -like "*virtio*" }

    if ($cdDrives) {
        $driveLetter = ($cdDrives | Select-Object -First 1).Drive
        Write-Log "  Found VirtIO ISO at: $driveLetter"
        return $driveLetter
    }

    # Check for extracted drivers in common locations
    $extractedPaths = @(
        "C:\Drivers\virtio",
        "C:\VirtIO",
        "$env:USERPROFILE\Downloads\virtio-win*",
        "D:\",
        "E:\"
    )

    foreach ($path in $extractedPaths) {
        $expanded = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($expanded) {
            if (Test-Path (Join-Path $expanded.FullName "vioscsi") -or
                Test-Path (Join-Path $path "vioscsi")) {
                Write-Log "  Found VirtIO drivers at: $path"
                return $path
            }
        }
    }

    Write-Log "  VirtIO driver source not found" "WARN"
    return $null
}

function Get-WindowsVersion {
    $os = Get-WmiObject -Class Win32_OperatingSystem
    $build = [int]$os.BuildNumber

    # Determine driver folder name
    if ($build -ge 19041) {
        return "w10"      # Windows 10 2004+
    }
    elseif ($build -ge 17763) {
        return "w10"      # Windows 10 1809+
    }
    elseif ($build -ge 10240) {
        return "w10"      # Windows 10
    }
    else {
        return "w8.1"     # Fallback
    }
}

function Install-VirtIODriver {
    param(
        [string]$DriverPath,
        [string]$DriverName
    )

    Write-Log "  Installing $DriverName..."

    $infFiles = Get-ChildItem -Path $DriverPath -Filter "*.inf" -Recurse

    foreach ($inf in $infFiles) {
        $result = pnputil.exe /add-driver $inf.FullName /install 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Log "    Installed: $($inf.Name)"
        }
    }
}

function Install-AllVirtIODrivers {
    param([string]$BasePath)

    Write-Log "Installing VirtIO drivers..."

    $winVer = Get-WindowsVersion
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "x86" }

    $drivers = @(
        @{Name = "VirtIO SCSI"; Path = "vioscsi"},
        @{Name = "VirtIO Block"; Path = "viostor"},
        @{Name = "VirtIO Network"; Path = "NetKVM"},
        @{Name = "VirtIO Balloon"; Path = "Balloon"},
        @{Name = "VirtIO Serial"; Path = "vioserial"},
        @{Name = "VirtIO RNG"; Path = "viorng"},
        @{Name = "VirtIO Input"; Path = "vioinput"},
        @{Name = "QEMU Guest Agent"; Path = "guest-agent"},
        @{Name = "QXL Display"; Path = "qxldod"}
    )

    foreach ($driver in $drivers) {
        $driverPath = Join-Path $BasePath $driver.Path
        $versionPath = Join-Path $driverPath "$winVer\$arch"

        if (Test-Path $versionPath) {
            Install-VirtIODriver -DriverPath $versionPath -DriverName $driver.Name
        }
        elseif (Test-Path $driverPath) {
            # Try without version subfolder
            Install-VirtIODriver -DriverPath $driverPath -DriverName $driver.Name
        }
        else {
            Write-Log "    $($driver.Name) not found - skipping" "WARN"
        }
    }
}

function Install-GuestAgent {
    param([string]$BasePath)

    Write-Log "Installing QEMU Guest Agent..."

    $agentPaths = @(
        (Join-Path $BasePath "guest-agent\qemu-ga-x86_64.msi"),
        (Join-Path $BasePath "guest-agent\qemu-ga-x64.msi"),
        (Join-Path $BasePath "guest-agent\qemu-ga.msi")
    )

    foreach ($agentPath in $agentPaths) {
        if (Test-Path $agentPath) {
            Start-Process msiexec.exe -ArgumentList "/i `"$agentPath`" /quiet /norestart" -Wait
            Write-Log "  Guest Agent installed from: $agentPath"

            # Start the service
            Start-Service -Name "QEMU-GA" -ErrorAction SilentlyContinue
            return
        }
    }

    Write-Log "  Guest Agent MSI not found" "WARN"
}

function Update-SystemDrivers {
    Write-Log "Updating system drivers..."

    # Force Windows to search for driver updates
    $updateSession = New-Object -ComObject Microsoft.Update.Session
    $updateSearcher = $updateSession.CreateUpdateSearcher()

    try {
        $searchResult = $updateSearcher.Search("IsInstalled=0 and Type='Driver'")

        if ($searchResult.Updates.Count -gt 0) {
            Write-Log "  Found $($searchResult.Updates.Count) driver updates"

            foreach ($update in $searchResult.Updates) {
                Write-Log "    Available: $($update.Title)"
            }

            Write-Log "  Run Windows Update to install driver updates" "WARN"
        }
        else {
            Write-Log "  All drivers are up to date"
        }
    }
    catch {
        Write-Log "  Could not check for driver updates" "WARN"
    }
}

function Verify-InstalledDrivers {
    Write-Log "Verifying installed drivers..."

    $virtioDrivers = Get-WmiObject Win32_PnPSignedDriver |
        Where-Object { $_.DriverProviderName -like "*Red Hat*" -or
                      $_.DeviceName -like "*VirtIO*" -or
                      $_.DeviceName -like "*QEMU*" }

    if ($virtioDrivers) {
        Write-Log "  Installed VirtIO drivers:"
        foreach ($driver in $virtioDrivers) {
            Write-Log "    $($driver.DeviceName) - v$($driver.DriverVersion)"
        }
    }
    else {
        Write-Log "  No VirtIO drivers detected" "WARN"
    }

    # Check for problem devices
    $problemDevices = Get-WmiObject Win32_PnPEntity |
        Where-Object { $_.ConfigManagerErrorCode -ne 0 }

    if ($problemDevices) {
        Write-Log "  Devices with problems:" "WARN"
        foreach ($device in $problemDevices) {
            Write-Log "    $($device.Name) - Error: $($device.ConfigManagerErrorCode)" "WARN"
        }
    }
    else {
        Write-Log "  All devices functioning correctly"
    }
}

function Configure-DisplayDriver {
    Write-Log "Configuring display driver..."

    # Check if QXL is installed
    $displayAdapters = Get-WmiObject Win32_VideoController

    foreach ($adapter in $displayAdapters) {
        Write-Log "  Display: $($adapter.Name)"

        if ($adapter.Name -like "*QXL*") {
            Write-Log "    QXL driver is active"
        }
        elseif ($adapter.Name -like "*VirtIO*") {
            Write-Log "    VirtIO GPU driver is active"
        }
        elseif ($adapter.Name -like "*Microsoft Basic*") {
            Write-Log "    Using Basic Display - consider installing VirtIO GPU" "WARN"
        }
    }
}

function Configure-NetworkDriver {
    Write-Log "Configuring network driver..."

    $networkAdapters = Get-NetAdapter

    foreach ($adapter in $networkAdapters) {
        Write-Log "  Adapter: $($adapter.Name) - $($adapter.InterfaceDescription)"

        if ($adapter.InterfaceDescription -like "*VirtIO*" -or
            $adapter.InterfaceDescription -like "*Red Hat*") {
            Write-Log "    VirtIO network driver detected"

            # Optimize network settings
            Set-NetAdapterAdvancedProperty -Name $adapter.Name `
                -DisplayName "Large Send Offload*" -DisplayValue "Disabled" `
                -ErrorAction SilentlyContinue

            Write-Log "    Network optimizations applied"
        }
    }
}

# Main execution
function Main {
    Write-Log "VirtIO Driver Installation Script"
    Write-Log "=================================="
    Write-Log ""

    $virtioPath = Find-VirtIODrive

    if ($virtioPath) {
        Install-AllVirtIODrivers -BasePath $virtioPath
        Install-GuestAgent -BasePath $virtioPath
    }
    else {
        Write-Log "No VirtIO driver source found!" "ERROR"
        Write-Log "Please mount the VirtIO ISO or extract drivers to C:\Drivers\virtio" "ERROR"
        Write-Log ""
        Write-Log "Download from:"
        Write-Log "  https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/"
    }

    Write-Log ""
    Configure-DisplayDriver
    Configure-NetworkDriver
    Verify-InstalledDrivers

    Write-Log ""
    Write-Log "=================================="
    Write-Log "Driver installation complete!"
    Write-Log ""
    Write-Log "A restart may be required for all drivers to take effect."
}

Main
