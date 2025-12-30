# enable_rdp.ps1 - Emergency RDP Access Script
#
# Enables RDP access for emergency recovery when VNC is unavailable.
# Use only when VNC connection fails and you need remote access.
#
# Usage: Run as Administrator in PowerShell
#   .\enable_rdp.ps1

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

function Enable-RDPService {
    Write-Log "Enabling Remote Desktop service..."

    # Enable Terminal Services
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" `
        -Name "fDenyTSConnections" -Value 0 -Type DWord

    # Enable RDP in Windows Firewall
    Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue

    # Start the service
    Set-Service -Name "TermService" -StartupType Automatic
    Start-Service -Name "TermService"

    Write-Log "RDP service enabled and started"
}

function Configure-RDPSettings {
    Write-Log "Configuring RDP settings..."

    $rdpPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    $rdpTcpPath = "$rdpPath\WinStations\RDP-Tcp"

    # Allow connections from computers running any version of Remote Desktop
    Set-ItemProperty -Path $rdpPath -Name "fSingleSessionPerUser" -Value 0 -Type DWord

    # Set security layer (2 = TLS)
    Set-ItemProperty -Path $rdpTcpPath -Name "SecurityLayer" -Value 2 -Type DWord

    # Set user authentication (1 = NLA required)
    Set-ItemProperty -Path $rdpTcpPath -Name "UserAuthentication" -Value 1 -Type DWord

    # Set encryption level (3 = High)
    Set-ItemProperty -Path $rdpTcpPath -Name "MinEncryptionLevel" -Value 3 -Type DWord

    Write-Log "RDP settings configured"
}

function Add-RDPFirewallRules {
    Write-Log "Adding firewall rules for RDP..."

    # Enable built-in RDP rules
    $rdpRules = Get-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue

    if ($rdpRules) {
        $rdpRules | Enable-NetFirewallRule
        Write-Log "  Enabled existing RDP firewall rules"
    }
    else {
        # Create custom rule if built-in rules don't exist
        New-NetFirewallRule -DisplayName "Remote Desktop (TCP-In)" `
            -Direction Inbound -Protocol TCP -LocalPort 3389 `
            -Action Allow -Profile Any -ErrorAction SilentlyContinue

        Write-Log "  Created custom RDP firewall rule"
    }
}

function Add-UserToRDPGroup {
    param([string]$Username)

    Write-Log "Adding user to Remote Desktop Users group..."

    if (-not $Username) {
        $Username = $env:USERNAME
    }

    try {
        Add-LocalGroupMember -Group "Remote Desktop Users" -Member $Username -ErrorAction SilentlyContinue
        Write-Log "  Added $Username to Remote Desktop Users"
    }
    catch {
        Write-Log "  User may already be in group or is an administrator" "WARN"
    }
}

function Get-RDPStatus {
    Write-Log "Checking RDP status..."

    $rdpEnabled = (Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" `
        -Name "fDenyTSConnections").fDenyTSConnections -eq 0

    $rdpService = Get-Service -Name "TermService"

    $firewallRules = Get-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq $true }

    Write-Log ""
    Write-Log "RDP Status:"
    Write-Log "  RDP Enabled: $rdpEnabled"
    Write-Log "  Service Status: $($rdpService.Status)"
    Write-Log "  Firewall Rules Enabled: $($firewallRules.Count -gt 0)"

    # Get IP addresses
    $ipAddresses = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } |
        Select-Object -ExpandProperty IPAddress

    Write-Log ""
    Write-Log "Connect using:"
    foreach ($ip in $ipAddresses) {
        Write-Log "  mstsc /v:$ip"
    }
}

function Disable-RDP {
    Write-Log "Disabling RDP (for when emergency is resolved)..."

    # Disable RDP
    Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server" `
        -Name "fDenyTSConnections" -Value 1 -Type DWord

    # Disable firewall rules
    Disable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue

    Write-Log "RDP disabled"
}

# Main execution
function Main {
    param([switch]$Disable)

    Write-Log "Emergency RDP Access Script"
    Write-Log "==========================="
    Write-Log ""
    Write-Log "WARNING: RDP can be detected by anti-automation systems!" "WARN"
    Write-Log "Only use for emergency recovery, then disable immediately." "WARN"
    Write-Log ""

    if ($Disable) {
        Disable-RDP
    }
    else {
        Enable-RDPService
        Configure-RDPSettings
        Add-RDPFirewallRules
        Add-UserToRDPGroup
        Get-RDPStatus

        Write-Log ""
        Write-Log "==========================="
        Write-Log "RDP emergency access enabled!"
        Write-Log ""
        Write-Log "IMPORTANT: Run with -Disable flag when done to re-secure system" "WARN"
    }
}

# Check for disable flag
if ($args -contains "-Disable" -or $args -contains "--disable") {
    Main -Disable
}
else {
    Main
}
