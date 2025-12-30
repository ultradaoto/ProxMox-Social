└── VM2: Windows 10 Target
    ├── VirtIO drivers
    ├── Sees virtual mouse as "Logitech USB Mouse"
    ├── Chrome with logged-in profiles
    └── RDP enabled for emergency access

    FOLDER 3: W10-DRIVERS (Windows 10 Target VM)
Purpose
Windows 10 VM that receives "human" input and displays screen to Ubuntu controller.

Setup Steps
1. Basic Windows 10 Installation
Install Windows 10 Pro (22H2 or newer)

4-8GB RAM, 2-4 CPU cores, 50GB disk

Use VirtIO drivers from Proxmox

2. Install VirtIO Drivers
powershell
# In Proxmox, download VirtIO ISO
# Mount to Windows VM and install:
# - viostor (storage)
# - vioserial (serial)
# - NetKVM (network)
# - Balloon (memory ballooning)
# - qemu-ga (QEMU guest agent)
3. Disable Windows Telemetry & Updates
powershell
# Run as Administrator
Set-ExecutionPolicy RemoteSigned -Force

# Disable Windows Update
Stop-Service wuauserv
Set-Service wuauserv -StartupType Disabled

# Reduce telemetry
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection" `
    -Name "AllowTelemetry" -Value 0 -PropertyType DWord -Force
4. Install VNC Server (For Screen Capture)
powershell
# Download TightVNC
# https://www.tightvnc.com/download.php

# Install with:
# - Service mode
# - Password protection
# - Port 5900
# - Disable file transfers
# - Enable "Accept connections"

# Configure in registry for auto-start
reg add "HKLM\SOFTWARE\TightVNC\Server" /v "AcceptRfbConnections" /t REG_DWORD /d 1 /f
reg add "HKLM\SOFTWARE\TightVNC\Server" /v "RfbPort" /t REG_DWORD /d 5900 /f
5. Configure Windows for "Human" Appearance
powershell
# Set realistic screen resolution
Set-DisplayResolution -Width 1920 -Height 1080 -Force

# Install Chrome and extensions
# - uBlock Origin
# - Privacy Badger
# - Random User-Agent (optional)

# Create realistic browsing history (optional but helpful)
# Visit common sites: google.com, youtube.com, amazon.com, etc.

# Set up user accounts realistically
# - Personal Microsoft account
# - Google account with 2FA
# - Social media accounts
6. Disable Bot Detection Clues
powershell
# Disable WebRTC leak
New-Item -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge" -Force
New-ItemProperty -Path "HKLM:\SOFTWARE\Policies\Microsoft\Edge" `
    -Name "WebRtcLocalIpsAllowedUrls" -Value "[]" -PropertyType String -Force

# Disable automation flags in Chrome
# Create Chrome shortcut with:
# --disable-blink-features=AutomationControlled
# --disable-features=IsolateOrigins,site-per-process
7. Install Logitech Drivers (Optional but Recommended)
powershell
# Download Logitech Options from official site
# This makes virtual devices appear more legitimate
# Windows will install generic HID drivers if not present
8. Configure Windows Firewall
powershell
# Allow VNC connections from Ubuntu VM
New-NetFirewallRule -DisplayName "VNC from Ubuntu" `
    -Direction Inbound -Protocol TCP -LocalPort 5900 `
    -RemoteAddress 192.168.100.101 -Action Allow
9. Create Emergency RDP Access
powershell
# Enable RDP
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server' `
    -Name "fDenyTSConnections" -Value 0

# Allow RDP through firewall
Enable-NetFirewallRule -DisplayGroup "Remote Desktop"

# Set Network Level Authentication (more secure)
Set-ItemProperty -Path 'HKLM:\System\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' `
    -Name "UserAuthentication" -Value 1
10. Final Security Settings
powershell
# Disable SmartScreen for file downloads
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer" `
    -Name "SmartScreenEnabled" -Value "Off" -Type String

# Set realistic timezone and locale
Set-TimeZone -Id "Eastern Standard Time"  # Or your preferred zone
Set-WinSystemLocale -SystemLocale en-US

# Disable game mode (can interfere with input)
Set-ItemProperty -Path "HKLM:\SOFTWARE\Microsoft\PolicyManager\default\ApplicationManagement\AllowGameDVR" `
    -Name "value" -Value 0 -Type DWord
Post-Install Checklist
Windows activated (legitimately)

Chrome installed with "human-like" extensions

User accounts logged in

VNC server running on port 5900

Firewall configured

VirtIO drivers installed

No automation software present

Realistic browsing history

Emergency RDP access configured

