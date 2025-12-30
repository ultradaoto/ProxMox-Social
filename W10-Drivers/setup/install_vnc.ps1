# install_vnc.ps1 - Install and Configure TightVNC Server
#
# Installs TightVNC in service mode for screen capture by the AI controller.
#
# Usage: Run as Administrator in PowerShell
#   .\install_vnc.ps1

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$VncPassword = "changeme123"  # CHANGE THIS!
$VncPort = 5900
$AllowedIP = "192.168.100.101"  # Ubuntu AI Controller IP

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

function Download-TightVNC {
    Write-Log "Downloading TightVNC..."

    $tempDir = "$env:TEMP\tightvnc"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    # TightVNC download URL (update version as needed)
    $vncUrl = "https://www.tightvnc.com/download/2.8.81/tightvnc-2.8.81-gpl-setup-64bit.msi"
    $vncPath = "$tempDir\tightvnc-setup.msi"

    try {
        Write-Log "Downloading from: $vncUrl"
        Invoke-WebRequest -Uri $vncUrl -OutFile $vncPath -UseBasicParsing

        return $vncPath
    }
    catch {
        Write-Log "Download failed: $_" "ERROR"
        Write-Log "Please download TightVNC manually from https://www.tightvnc.com/download.php" "WARN"
        return $null
    }
}

function Install-TightVNC {
    param([string]$InstallerPath)

    Write-Log "Installing TightVNC..."

    # Convert password to hex for MSI parameters
    $passwordBytes = [System.Text.Encoding]::ASCII.GetBytes($VncPassword)
    $hexPassword = ($passwordBytes | ForEach-Object { $_.ToString("X2") }) -join ""

    # MSI installation with silent options
    $msiArgs = @(
        "/i", "`"$InstallerPath`"",
        "/quiet",
        "/norestart",
        "ADDLOCAL=Server",
        "SERVER_REGISTER_AS_SERVICE=1",
        "SERVER_ADD_FIREWALL_EXCEPTION=1",
        "SET_USEVNCAUTHENTICATION=1",
        "VALUE_OF_USEVNCAUTHENTICATION=1",
        "SET_PASSWORD=1",
        "VALUE_OF_PASSWORD=$hexPassword",
        "SET_RFBPORT=1",
        "VALUE_OF_RFBPORT=$VncPort"
    )

    $process = Start-Process -FilePath "msiexec.exe" -ArgumentList $msiArgs -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Log "TightVNC installed successfully"
        return $true
    }
    else {
        Write-Log "TightVNC installation failed with exit code: $($process.ExitCode)" "ERROR"
        return $false
    }
}

function Configure-VNCRegistry {
    Write-Log "Configuring VNC registry settings..."

    $vncRegPath = "HKLM:\SOFTWARE\TightVNC\Server"

    # Ensure registry path exists
    if (-not (Test-Path $vncRegPath)) {
        New-Item -Path $vncRegPath -Force | Out-Null
    }

    # Core settings
    Set-ItemProperty -Path $vncRegPath -Name "AcceptRfbConnections" -Value 1 -Type DWord
    Set-ItemProperty -Path $vncRegPath -Name "RfbPort" -Value $VncPort -Type DWord
    Set-ItemProperty -Path $vncRegPath -Name "UseVncAuthentication" -Value 1 -Type DWord

    # Disable file transfers (security)
    Set-ItemProperty -Path $vncRegPath -Name "EnableFileTransfers" -Value 0 -Type DWord

    # Disable clipboard transfer (reduces fingerprint)
    Set-ItemProperty -Path $vncRegPath -Name "EnableClipboard" -Value 0 -Type DWord

    # Disable remote input by default (we control via virtual HID)
    Set-ItemProperty -Path $vncRegPath -Name "BlockRemoteInput" -Value 1 -Type DWord

    # Disable local input blocking
    Set-ItemProperty -Path $vncRegPath -Name "LocalInputPriority" -Value 1 -Type DWord

    # Connection settings
    Set-ItemProperty -Path $vncRegPath -Name "AlwaysShared" -Value 1 -Type DWord
    Set-ItemProperty -Path $vncRegPath -Name "NeverShared" -Value 0 -Type DWord
    Set-ItemProperty -Path $vncRegPath -Name "DisconnectClients" -Value 0 -Type DWord

    # Polling settings for smooth capture
    Set-ItemProperty -Path $vncRegPath -Name "PollingInterval" -Value 30 -Type DWord
    Set-ItemProperty -Path $vncRegPath -Name "GrabTransparentWindows" -Value 1 -Type DWord

    # Logging (minimal)
    Set-ItemProperty -Path $vncRegPath -Name "EnableLogging" -Value 0 -Type DWord

    Write-Log "VNC registry configured"
}

function Configure-VNCFirewall {
    Write-Log "Configuring firewall for VNC..."

    # Remove any existing VNC rules
    Get-NetFirewallRule -DisplayName "*VNC*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule -ErrorAction SilentlyContinue

    # Allow VNC only from Ubuntu AI Controller
    New-NetFirewallRule -DisplayName "VNC from Ubuntu AI Controller" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $VncPort `
        -RemoteAddress $AllowedIP `
        -Action Allow `
        -Profile Any | Out-Null

    # Block VNC from all other sources
    New-NetFirewallRule -DisplayName "VNC Block Others" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort $VncPort `
        -Action Block `
        -Profile Any | Out-Null

    Write-Log "Firewall configured: VNC allowed only from $AllowedIP"
}

function Start-VNCService {
    Write-Log "Starting VNC service..."

    $service = Get-Service -Name "tvnserver" -ErrorAction SilentlyContinue

    if ($service) {
        if ($service.Status -ne "Running") {
            Start-Service -Name "tvnserver"
            Write-Log "VNC service started"
        }
        else {
            Write-Log "VNC service already running"
        }

        # Ensure service starts automatically
        Set-Service -Name "tvnserver" -StartupType Automatic
    }
    else {
        Write-Log "VNC service not found" "ERROR"
    }
}

function Test-VNCConnection {
    Write-Log "Testing VNC connection..."

    $tcpConnection = Test-NetConnection -ComputerName localhost -Port $VncPort -WarningAction SilentlyContinue

    if ($tcpConnection.TcpTestSucceeded) {
        Write-Log "VNC server is listening on port $VncPort"
    }
    else {
        Write-Log "VNC server is NOT listening on port $VncPort" "ERROR"
    }
}

# Main execution
function Main {
    Write-Log "TightVNC Installation Script"
    Write-Log "============================"

    # Check if already installed
    $existingService = Get-Service -Name "tvnserver" -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Log "TightVNC is already installed"
        Write-Log "Updating configuration..."
        Configure-VNCRegistry
        Configure-VNCFirewall
        Restart-Service -Name "tvnserver" -Force
        Test-VNCConnection
        return
    }

    # Download and install
    $installer = Download-TightVNC

    if ($installer) {
        if (Install-TightVNC -InstallerPath $installer) {
            Configure-VNCRegistry
            Configure-VNCFirewall
            Start-VNCService
            Test-VNCConnection
        }

        # Cleanup
        Remove-Item -Path (Split-Path $installer -Parent) -Recurse -Force -ErrorAction SilentlyContinue
    }

    Write-Log ""
    Write-Log "============================"
    Write-Log "VNC Setup Complete!"
    Write-Log ""
    Write-Log "Connection details:"
    Write-Log "  Address: 192.168.100.100:$VncPort"
    Write-Log "  Password: $VncPassword"
    Write-Log ""
    Write-Log "IMPORTANT: Change the VNC password for production use!"
}

Main
