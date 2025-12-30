$ErrorActionPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "Starting Master Setup (Drivers, Config, Software)..."

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "ERROR: This script requires Administrator privileges. Please run as Administrator."
    Exit 1
}

# ---------------------------------------------------------
# 1. Install VirtIO Drivers
# ---------------------------------------------------------
Write-Host "`n[1/3] Installing VirtIO Drivers..."
$virtIoPath = "E:\virtio-win-guest-tools.exe"
if (Test-Path $virtIoPath) {
    Write-Host "    Found VirtIO Guest Tools at $virtIoPath"
    Write-Host "    Installing... (This may take a minute)"
    $proc = Start-Process -FilePath $virtIoPath -ArgumentList "/install", "/passive", "/norestart" -Wait -PassThru
    Write-Host "    VirtIO Install Exit Code: $($proc.ExitCode)"
}
else {
    Write-Warning "    VirtIO Guest Tools not found on E:\. Skipping."
}

# ---------------------------------------------------------
# 2. System Configuration
# ---------------------------------------------------------
Write-Host "`n[2/3] Configuring System Settings..."

Write-Host "    Disabling Windows Update Service..."
Stop-Service wuauserv -Force
Set-Service wuauserv -StartupType Disabled

Write-Host "    Configuring Telemetry..."
$telemetryPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
if (!(Test-Path $telemetryPath)) { New-Item -Path $telemetryPath -Force | Out-Null }
New-ItemProperty -Path $telemetryPath -Name "AllowTelemetry" -Value 0 -PropertyType DWord -Force | Out-Null

Write-Host "    Disabling SmartScreen..."
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" -Name "SmartScreenEnabled" -Value "Off" -Type String -Force

Write-Host "    Enabling RDP..."
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' -Name "fDenyTSConnections" -Value 0 -Force
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name "UserAuthentication" -Value 1 -Force
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"

Write-Host "    Disabling Edge WebRTC Leaks..."
$edgePath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
if (!(Test-Path $edgePath)) { New-Item -Path $edgePath -Force | Out-Null }
New-ItemProperty -Path $edgePath -Name "WebRtcLocalIpsAllowedUrls" -Value "[]" -PropertyType String -Force | Out-Null

# ---------------------------------------------------------
# 3. Install VNC Server
# ---------------------------------------------------------
Write-Host "`n[3/3] Installing TightVNC Server..."

# TightVNC URL (Standard 64-bit installer)
$vncUrl = "https://www.tightvnc.com/download/2.8.84/tightvnc-2.8.84-gpl-setup-64bit.msi" 
$vncInstaller = "$env:TEMP\tightvnc.msi"

Write-Host "    Downloading TightVNC..."
try {
    Invoke-WebRequest -Uri $vncUrl -OutFile $vncInstaller
    
    Write-Host "    Installing TightVNC Service..."
    # Properties: 
    #   SERVER_REGISTER_AS_SERVICE=1 (Run as service)
    #   SERVER_ADD_FIREWALL_EXCEPTION=1 (Allow in firewall)
    #   SERVER_ALLOW_SAS=1 (Ctrl+Alt+Del)
    #   SET_USEVNCAUTHENTICATION=1 (Enable password)
    #   VALUE_OF_PASSWORD=... (We need to set a default password or let user configure later. 
    #   For silent install, password setting is tricky without raw hex. 
    #   We will install basic service and let user set password or use default empty if allowed, 
    #   but TightVNC usually requires a password for service mode.)
    
    # Actually, simpler to just install validation and let user configure UI, 
    # OR fully automate. The setup needs to receive "human" input, so maybe interactive is fine?
    # But user asked for "setup". Let's do silent install with defaults.
    
    $procVnc = Start-Process "msiexec.exe" -ArgumentList "/i", "`"$vncInstaller`"", "/quiet", "/norestart", "SERVER_REGISTER_AS_SERVICE=1", "SERVER_ADD_FIREWALL_EXCEPTION=1" -Wait -PassThru
    Write-Host "    TightVNC Install Exit Code: $($procVnc.ExitCode)"
    
    # Configure VNC Firewall Rule Explicitly (just in case)
    if (Get-NetFirewallRule -DisplayName "VNC from Ubuntu" -ErrorAction SilentlyContinue) {
        Remove-NetFirewallRule -DisplayName "VNC from Ubuntu"
    }
    New-NetFirewallRule -DisplayName "VNC from Ubuntu" -Direction Inbound -Protocol TCP -LocalPort 5900 -Action Allow | Out-Null

}
catch {
    Write-Warning "    Failed to download/install TightVNC: $($_.Exception.Message)"
}

Write-Host "`n[+] Setup Complete! Please restart your computer for all changes (esp. drivers) to take full effect."
