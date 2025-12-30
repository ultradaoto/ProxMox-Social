# base_install.ps1 - Post-Installation Configuration for Windows 10 Target VM
#
# Run this script after fresh Windows 10 installation.
# Requires: Administrator privileges, Internet access
#
# Usage: Run as Administrator in PowerShell
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\base_install.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

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

function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Set-ComputerConfiguration {
    Write-Log "Configuring computer name and settings..."

    # Set a realistic computer name (not the default DESKTOP-XXXXXXX)
    $newName = "WORKSTATION-$(Get-Random -Minimum 100 -Maximum 999)"
    Write-Log "Setting computer name to: $newName"

    try {
        Rename-Computer -NewName $newName -Force -ErrorAction SilentlyContinue
        Write-Log "Computer name set (will take effect after restart)"
    }
    catch {
        Write-Log "Could not rename computer: $_" "WARN"
    }

    # Set timezone to a common one
    Set-TimeZone -Id "Eastern Standard Time"
    Write-Log "Timezone set to Eastern Standard Time"

    # Set locale
    Set-WinSystemLocale -SystemLocale en-US
    Set-WinUserLanguageList -LanguageList en-US -Force
    Write-Log "System locale set to en-US"
}

function Install-VirtIODrivers {
    Write-Log "Checking VirtIO drivers..."

    # Check if VirtIO drivers are installed
    $virtioDevices = Get-PnpDevice | Where-Object { $_.FriendlyName -like "*VirtIO*" }

    if ($virtioDevices) {
        Write-Log "VirtIO drivers already installed"
        $virtioDevices | ForEach-Object {
            Write-Log "  - $($_.FriendlyName): $($_.Status)"
        }
    }
    else {
        Write-Log "VirtIO drivers may need to be installed manually" "WARN"
        Write-Log "Mount virtio-win ISO and run virtio-win-guest-tools.exe" "WARN"
    }
}

function Install-QemuGuestAgent {
    Write-Log "Checking QEMU Guest Agent..."

    $qemuAgent = Get-Service -Name "QEMU-GA" -ErrorAction SilentlyContinue

    if ($qemuAgent) {
        Write-Log "QEMU Guest Agent is installed (Status: $($qemuAgent.Status))"

        if ($qemuAgent.Status -ne "Running") {
            Start-Service "QEMU-GA"
            Write-Log "Started QEMU Guest Agent"
        }
    }
    else {
        Write-Log "QEMU Guest Agent not installed" "WARN"
        Write-Log "Install from VirtIO drivers ISO" "WARN"
    }
}

function Configure-Network {
    Write-Log "Configuring network..."

    # Get network adapters
    $adapters = Get-NetAdapter | Where-Object { $_.Status -eq "Up" }

    foreach ($adapter in $adapters) {
        Write-Log "Found adapter: $($adapter.Name) - $($adapter.InterfaceDescription)"

        # Check if this is the internal network adapter (for VM communication)
        $ip = Get-NetIPAddress -InterfaceIndex $adapter.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue

        if ($ip.IPAddress -like "192.168.100.*") {
            Write-Log "Internal network adapter detected: $($ip.IPAddress)"
        }
    }

    # Disable IPv6 on all adapters (reduces fingerprint)
    Write-Log "Disabling IPv6..."
    Get-NetAdapterBinding -ComponentID ms_tcpip6 | Disable-NetAdapterBinding

    # Enable ICMP (for ping diagnostics)
    netsh advfirewall firewall add rule name="Allow ICMPv4" protocol=icmpv4:8,any dir=in action=allow | Out-Null
    Write-Log "ICMP enabled for diagnostics"
}

function Set-StaticInternalIP {
    Write-Log "Setting static IP for internal network..."

    # Find the internal network adapter (connected to vmbr1)
    $internalAdapter = Get-NetAdapter | Where-Object {
        $_.Status -eq "Up" -and
        (Get-NetIPAddress -InterfaceIndex $_.ifIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress -like "192.168.100.*"
    }

    if ($internalAdapter) {
        Write-Log "Internal adapter found: $($internalAdapter.Name)"

        # Set static IP
        Remove-NetIPAddress -InterfaceIndex $internalAdapter.ifIndex -Confirm:$false -ErrorAction SilentlyContinue
        New-NetIPAddress -InterfaceIndex $internalAdapter.ifIndex -IPAddress "192.168.100.100" -PrefixLength 24 | Out-Null

        Write-Log "Set static IP: 192.168.100.100/24"
    }
    else {
        Write-Log "Could not find internal network adapter" "WARN"
        Write-Log "Configure manually: 192.168.100.100/24" "WARN"
    }
}

function Configure-PowerSettings {
    Write-Log "Configuring power settings..."

    # Set high performance power plan
    powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c

    # Disable sleep
    powercfg /change standby-timeout-ac 0
    powercfg /change standby-timeout-dc 0

    # Disable hibernate
    powercfg /hibernate off

    # Disable screen timeout
    powercfg /change monitor-timeout-ac 0
    powercfg /change monitor-timeout-dc 0

    Write-Log "Power settings configured (no sleep/hibernate)"
}

function Install-Prerequisites {
    Write-Log "Installing prerequisites..."

    # Create temp directory
    $tempDir = "$env:TEMP\setup"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    # Install Visual C++ Redistributables (required by many apps)
    Write-Log "Installing Visual C++ Redistributables..."

    $vc2019Url = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    $vc2019Path = "$tempDir\vc_redist.x64.exe"

    try {
        Invoke-WebRequest -Uri $vc2019Url -OutFile $vc2019Path -UseBasicParsing
        Start-Process -FilePath $vc2019Path -ArgumentList "/install /quiet /norestart" -Wait
        Write-Log "Visual C++ Redistributable installed"
    }
    catch {
        Write-Log "Could not install VC++ Redistributable: $_" "WARN"
    }

    # Cleanup
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
}

function Set-ScreenResolution {
    Write-Log "Setting screen resolution..."

    # Note: This may require a restart or display driver to take effect
    # Default to 1920x1080 which is most common

    $resolution = @{
        Width = 1920
        Height = 1080
    }

    Write-Log "Target resolution: $($resolution.Width)x$($resolution.Height)"
    Write-Log "Resolution may need to be set manually in Display Settings" "WARN"
}

function Create-LocalAdmin {
    Write-Log "Checking local admin account..."

    # Create a backup admin account for emergency access
    $adminUser = "LocalAdmin"
    $adminPass = "ChangeMe123!" # Should be changed after setup

    $existingUser = Get-LocalUser -Name $adminUser -ErrorAction SilentlyContinue

    if (-not $existingUser) {
        Write-Log "Creating local admin account: $adminUser"

        $securePass = ConvertTo-SecureString $adminPass -AsPlainText -Force
        New-LocalUser -Name $adminUser -Password $securePass -FullName "Local Administrator" -Description "Emergency admin access" | Out-Null
        Add-LocalGroupMember -Group "Administrators" -Member $adminUser

        Write-Log "Local admin created. CHANGE THE PASSWORD!" "WARN"
    }
    else {
        Write-Log "Local admin account already exists"
    }
}

# Main execution
function Main {
    Write-Log "Starting Windows 10 Target VM Base Installation"
    Write-Log "================================================"

    if (-not (Test-Administrator)) {
        Write-Log "This script must be run as Administrator!" "ERROR"
        exit 1
    }

    Set-ComputerConfiguration
    Install-VirtIODrivers
    Install-QemuGuestAgent
    Configure-Network
    Set-StaticInternalIP
    Configure-PowerSettings
    Install-Prerequisites
    Set-ScreenResolution
    Create-LocalAdmin

    Write-Log ""
    Write-Log "================================================"
    Write-Log "Base installation complete!"
    Write-Log ""
    Write-Log "Next steps:"
    Write-Log "  1. Run install_vnc.ps1 to set up VNC server"
    Write-Log "  2. Run install_chrome.ps1 to install Chrome"
    Write-Log "  3. Run hardening scripts from hardening/ folder"
    Write-Log "  4. Restart the computer"
    Write-Log ""
    Write-Log "A restart may be required for some changes to take effect."
}

Main
