<#
.SYNOPSIS
    Downloads and Installs VirtIO Drivers for Windows 10 (Proxmox/KVM).
    Must be run as ADMINISTRATOR.

.DESCRIPTION
    1. Downloads stable virtio-win.iso from fedorapeople.org.
    2. Mounts the ISO.
    3. Installs VirtIO Guest Tools (Drivers + Agent) silently.
    4. DISABLES QEMU-GA immediately after install to prevent resolution overrides.
    5. Ejects ISO and cleans up.
#>

$ErrorActionPreference = "Stop"

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges."
    Exit 1
}

$Url = "https://fedorapeople.org/groups/virt/virtio-win/direct-downloads/stable-virtio/virtio-win.iso"
$IsoPath = "$env:TEMP\virtio-win.iso"

# 1. Download ISO
Write-Host "Downloading VirtIO Drivers ISO..." -ForegroundColor Cyan
if (Test-Path $IsoPath) { Remove-Item $IsoPath -Force }
Invoke-WebRequest -Uri $Url -OutFile $IsoPath
Write-Host "Download Complete: $IsoPath" -ForegroundColor Green

# 2. Mount ISO
Write-Host "Mounting ISO..." -ForegroundColor Cyan
$MountResult = Mount-DiskImage -ImagePath $IsoPath -PassThru
$DriveLetter = ($MountResult | Get-Volume).DriveLetter
if (!$DriveLetter) {
    Write-Error "Failed to mount ISO or find drive letter."
}
$DriveRoot = "$($DriveLetter):\"
Write-Host "Mounted at ${DriveRoot}" -ForegroundColor Green

# 3. Install Drivers (Guest Tools)
# virtio-win-gt-x64.msi includes drivers and QEMU-GA
$Installer = Join-Path $DriveRoot "virtio-win-gt-x64.msi"
if (!(Test-Path $Installer)) {
    # Fallback to searching if name changed
    $Installer = Get-ChildItem -Path $DriveRoot -Filter "virtio-win-gt-x64.msi" -Recurse | Select-Object -First 1 -ExpandProperty FullName
}

if ($Installer) {
    Write-Host "Installing Drivers from $Installer..." -ForegroundColor Yellow
    Write-Host "This may take a minute..."
    
    # Run MSI Installer silently
    $Proc = Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$Installer`" /qn /norestart" -Wait -PassThru
    
    if ($Proc.ExitCode -eq 0) {
        Write-Host "Installation Successful!" -ForegroundColor Green
    }
    else {
        Write-Error "Data installation failed with exit code $($Proc.ExitCode)."
    }
}
else {
    Write-Error "Installer (virtio-win-gt-x64.msi) not found on ISO."
}

# 4. Post-Install Cleanup (Disable QEMU-GA)
Write-Host "Ensuring QEMU-GA is disabled (to protect Resolution)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5 # Wait for service registration
try {
    Stop-Service QEMU-GA -Force -ErrorAction SilentlyContinue
    Set-Service QEMU-GA -StartupType Disabled -ErrorAction SilentlyContinue
    Write-Host "QEMU-GA Disabled." -ForegroundColor Green
}
catch {
    Write-Warning "Could not disable QEMU-GA: $_"
}

# 5. Cleanup ISO
Write-Host "Unmounting ISO..."
Dismount-DiskImage -ImagePath $IsoPath | Out-Null
Remove-Item $IsoPath -Force

Write-Host "`n=== Driver Install Complete ===" -ForegroundColor Cyan
Write-Host "Please restart the computer to apply all driver changes."
