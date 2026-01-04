$ErrorActionPreference = "Stop"

# TightVNC Configuration Script
# Enables video hook driver, multiple connections, and loopback

Write-Host "Configuring TightVNC Server..." -ForegroundColor Cyan

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges."
    Exit 1
}

$regPath = "HKLM:\SOFTWARE\TightVNC\Server"

# Create key if it doesn't exist
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
    Write-Host "Created registry key: $regPath"
}

# Enable video hook driver (improves screen capture)
Set-ItemProperty -Path $regPath -Name "UseVideoHook" -Value 1 -Type DWord
Write-Host "[OK] Video Hook Driver: ENABLED" -ForegroundColor Green

# Allow multiple VNC connections simultaneously
Set-ItemProperty -Path $regPath -Name "AllowLoopback" -Value 1 -Type DWord
Set-ItemProperty -Path $regPath -Name "LoopbackOnly" -Value 0 -Type DWord
Write-Host "[OK] Loopback Connections: ALLOWED" -ForegroundColor Green

# Don't disconnect other viewers when new one connects
Set-ItemProperty -Path $regPath -Name "AlwaysShared" -Value 1 -Type DWord
Set-ItemProperty -Path $regPath -Name "NeverShared" -Value 0 -Type DWord
Write-Host "[OK] Multiple Connections: ALLOWED (AlwaysShared)" -ForegroundColor Green

# Accept incoming connections
Set-ItemProperty -Path $regPath -Name "AcceptRfbConnections" -Value 1 -Type DWord
Set-ItemProperty -Path $regPath -Name "RfbPort" -Value 5900 -Type DWord
Write-Host "[OK] RFB Port: 5900" -ForegroundColor Green

# Don't block remote input or blank screen
Set-ItemProperty -Path $regPath -Name "BlockLocalInput" -Value 0 -Type DWord
Set-ItemProperty -Path $regPath -Name "BlockRemoteInput" -Value 0 -Type DWord
Set-ItemProperty -Path $regPath -Name "LocalInputPriority" -Value 0 -Type DWord
Write-Host "[OK] Input Blocking: DISABLED" -ForegroundColor Green

# Disable features that could cause black screen
Set-ItemProperty -Path $regPath -Name "RemoveWallpaper" -Value 0 -Type DWord
Set-ItemProperty -Path $regPath -Name "RemoveAero" -Value 0 -Type DWord
Write-Host "[OK] Wallpaper/Aero Removal: DISABLED" -ForegroundColor Green

# Web access (optional, usually port 5800)
Set-ItemProperty -Path $regPath -Name "AcceptHttpConnections" -Value 0 -Type DWord

# Disable Timeouts (Prevent disconnects/password prompts)
Set-ItemProperty -Path $regPath -Name "IdleTimeout" -Value 0 -Type DWord
Set-ItemProperty -Path $regPath -Name "QueryTimeout" -Value 0 -Type DWord
Write-Host "[OK] Timeouts: DISABLED (Always On)" -ForegroundColor Green

# Restart TightVNC service to apply changes
Write-Host "`nRestarting TightVNC service..." -ForegroundColor Yellow
Restart-Service tvnserver -Force
Start-Sleep -Seconds 2

# Verify service is running
$svc = Get-Service tvnserver
if ($svc.Status -eq "Running") {
    Write-Host "[OK] TightVNC Service: RUNNING" -ForegroundColor Green
}
else {
    Write-Host "[ERROR] TightVNC Service: $($svc.Status)" -ForegroundColor Red
}

Write-Host "`n=== Configuration Complete ===" -ForegroundColor Cyan
Write-Host "TightVNC should now allow multiple connections including from Proxmox."
Write-Host "If Ubuntu still sees black screen, check if Windows is on lock screen."
Write-Host "`nIMPORTANT: You may also need to set a VNC password via the TightVNC GUI."
