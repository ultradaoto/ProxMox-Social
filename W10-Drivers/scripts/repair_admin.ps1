<#
.SYNOPSIS
    Master Admin Repair Script for OSP Environment.
    Must be run as ADMINISTRATOR.

.DESCRIPTION
    1. Stops and Disables QEMU Guest Agent (Fixes resolution reset).
    2. Configures TightVNC timeouts (Fixes frequent disconnects).
    3. Enforces 1600x1200 Resolution (Fixes mouse mapping).
#>

$ErrorActionPreference = "Stop"

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges."
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'."
    Exit 1
}

Write-Host "=== OSP Admin Repair Started ===" -ForegroundColor Cyan

# 1. Stop QEMU Guest Agent
Write-Host "`n[1/3] Handling QEMU Guest Agent..." -ForegroundColor Yellow
try {
    $svc = Get-Service QEMU-GA -ErrorAction SilentlyContinue
    if ($svc) {
        if ($svc.Status -eq "Running") {
            Stop-Service QEMU-GA -Force
            Write-Host "Stopped QEMU-GA." -ForegroundColor Green
        }
        
        # Disable it so it doesn't restart on reboot
        Set-Service QEMU-GA -StartupType Disabled
        Write-Host "Disabled QEMU-GA startup." -ForegroundColor Green
    }
    else {
        Write-Host "QEMU-GA service not found (Skipping)." -ForegroundColor Gray
    }
}
catch {
    Write-Error "Failed to manage QEMU-GA: $_"
}

# 2. Configure TightVNC
Write-Host "`n[2/3] Configuring TightVNC..." -ForegroundColor Yellow
$VncScript = Join-Path $PSScriptRoot "config_tightvnc.ps1"
if (Test-Path $VncScript) {
    & powershell -ExecutionPolicy Bypass -File $VncScript
}
else {
    Write-Error "Could not find config_tightvnc.ps1 at $VncScript"
}

# 3. Enforce Resolution
Write-Host "`n[3/3] Enforcing 1600x1200 Resolution..." -ForegroundColor Yellow
$ResScript = Join-Path $PSScriptRoot "set_resolution.ps1"
if (Test-Path $ResScript) {
    & powershell -ExecutionPolicy Bypass -File $ResScript
}
else {
    Write-Error "Could not find set_resolution.ps1 at $ResScript"
}

Write-Host "`n=== Repair Complete ===" -ForegroundColor Cyan
Write-Host "Resolution should be 1600x1200."
Write-Host "VNC should stay connected indefinitely."
Write-Host "QEMU-GA (Proxmox Agent) should be disabled."
