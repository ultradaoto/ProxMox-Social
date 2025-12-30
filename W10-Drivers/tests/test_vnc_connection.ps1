# test_vnc_connection.ps1 - Test VNC Server Connectivity
#
# Verifies that VNC is properly configured and accessible.
#
# Usage: Run in PowerShell
#   .\test_vnc_connection.ps1

$ErrorActionPreference = "SilentlyContinue"

function Write-TestResult {
    param([string]$Test, [bool]$Passed, [string]$Details = "")
    $status = if ($Passed) { "[PASS]" } else { "[FAIL]" }
    $color = if ($Passed) { "Green" } else { "Red" }

    Write-Host "$status $Test" -ForegroundColor $color
    if ($Details) {
        Write-Host "       $Details" -ForegroundColor Gray
    }
}

function Test-VNCServiceRunning {
    Write-Host "`nTesting VNC Service Status..." -ForegroundColor Cyan

    $vncServices = @("tvnserver", "TightVNC", "WinVNC4", "uvnc_service")
    $found = $false

    foreach ($svcName in $vncServices) {
        $service = Get-Service -Name $svcName -ErrorAction SilentlyContinue
        if ($service) {
            $running = $service.Status -eq "Running"
            Write-TestResult "VNC Service ($svcName)" $running "Status: $($service.Status)"
            $found = $true

            if ($running) {
                return $true
            }
        }
    }

    if (-not $found) {
        Write-TestResult "VNC Service Installed" $false "No VNC service found"
    }

    return $false
}

function Test-VNCPort {
    Write-Host "`nTesting VNC Port..." -ForegroundColor Cyan

    $vncPort = 5900

    # Check if port is listening
    $listener = Get-NetTCPConnection -LocalPort $vncPort -State Listen -ErrorAction SilentlyContinue

    if ($listener) {
        $process = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        Write-TestResult "Port $vncPort Listening" $true "Process: $($process.Name)"
        return $true
    }
    else {
        Write-TestResult "Port $vncPort Listening" $false "No listener on VNC port"
        return $false
    }
}

function Test-VNCFirewall {
    Write-Host "`nTesting Firewall Rules..." -ForegroundColor Cyan

    $vncRules = Get-NetFirewallRule -DisplayName "*VNC*" -ErrorAction SilentlyContinue

    if ($vncRules) {
        $enabledRules = $vncRules | Where-Object { $_.Enabled -eq $true }

        if ($enabledRules) {
            Write-TestResult "VNC Firewall Rules" $true "Found $($enabledRules.Count) enabled rules"
            return $true
        }
        else {
            Write-TestResult "VNC Firewall Rules" $false "Rules exist but disabled"
            return $false
        }
    }

    # Check for port-based rule
    $portRule = Get-NetFirewallRule -ErrorAction SilentlyContinue |
        Where-Object { $_.Enabled -eq $true } |
        Get-NetFirewallPortFilter -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -eq 5900 }

    if ($portRule) {
        Write-TestResult "VNC Firewall Rules" $true "Port 5900 rule exists"
        return $true
    }

    Write-TestResult "VNC Firewall Rules" $false "No VNC firewall rules found"
    return $false
}

function Test-VNCRegistry {
    Write-Host "`nTesting VNC Configuration..." -ForegroundColor Cyan

    $vncPaths = @(
        "HKLM:\SOFTWARE\TightVNC\Server",
        "HKLM:\SOFTWARE\ORL\WinVNC3",
        "HKLM:\SOFTWARE\RealVNC",
        "HKCU:\SOFTWARE\TightVNC\Server"
    )

    foreach ($path in $vncPaths) {
        if (Test-Path $path) {
            Write-TestResult "VNC Registry Config" $true "Found at: $path"

            # Check for password
            $password = Get-ItemProperty -Path $path -Name "Password" -ErrorAction SilentlyContinue
            if ($password) {
                Write-TestResult "VNC Password Set" $true
            }
            else {
                Write-TestResult "VNC Password Set" $false "No password configured"
            }

            return $true
        }
    }

    Write-TestResult "VNC Registry Config" $false "No VNC configuration found"
    return $false
}

function Test-VNCConnectivity {
    Write-Host "`nTesting Local Connectivity..." -ForegroundColor Cyan

    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.Connect("127.0.0.1", 5900)

        if ($tcpClient.Connected) {
            # Try to read VNC handshake
            $stream = $tcpClient.GetStream()
            $buffer = New-Object byte[] 12
            $stream.ReadTimeout = 5000
            $bytesRead = $stream.Read($buffer, 0, 12)

            $handshake = [System.Text.Encoding]::ASCII.GetString($buffer, 0, $bytesRead)
            $tcpClient.Close()

            if ($handshake -like "RFB*") {
                Write-TestResult "VNC Handshake" $true "Protocol: $($handshake.Trim())"
                return $true
            }
            else {
                Write-TestResult "VNC Handshake" $false "Unexpected response"
                return $false
            }
        }
    }
    catch {
        Write-TestResult "VNC Handshake" $false "Connection failed: $($_.Exception.Message)"
        return $false
    }
}

function Test-VNCExternalAccess {
    Write-Host "`nTesting External Accessibility..." -ForegroundColor Cyan

    # Get non-loopback IP addresses
    $ipAddresses = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -ne "127.0.0.1" }

    if (-not $ipAddresses) {
        Write-TestResult "External IP Available" $false "No external IP addresses found"
        return $false
    }

    foreach ($ip in $ipAddresses) {
        Write-Host "       IP: $($ip.IPAddress) on $($ip.InterfaceAlias)" -ForegroundColor Gray

        try {
            $tcpClient = New-Object System.Net.Sockets.TcpClient
            $tcpClient.Connect($ip.IPAddress, 5900)

            if ($tcpClient.Connected) {
                $tcpClient.Close()
                Write-TestResult "VNC on $($ip.IPAddress)" $true
            }
        }
        catch {
            Write-TestResult "VNC on $($ip.IPAddress)" $false "Cannot connect"
        }
    }
}

function Test-VNCProcess {
    Write-Host "`nTesting VNC Process..." -ForegroundColor Cyan

    $vncProcesses = @("tvnserver", "winvnc", "winvnc4", "vncserver")

    foreach ($procName in $vncProcesses) {
        $process = Get-Process -Name $procName -ErrorAction SilentlyContinue

        if ($process) {
            Write-TestResult "VNC Process Running" $true "PID: $($process.Id), Name: $procName"
            Write-Host "       Memory: $([math]::Round($process.WorkingSet64 / 1MB, 2)) MB" -ForegroundColor Gray
            return $true
        }
    }

    Write-TestResult "VNC Process Running" $false "No VNC process found"
    return $false
}

function Get-VNCConnectionInfo {
    Write-Host "`nVNC Connection Information:" -ForegroundColor Cyan
    Write-Host "===========================" -ForegroundColor Cyan

    $ipAddresses = Get-NetIPAddress -AddressFamily IPv4 |
        Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.IPAddress -ne "127.0.0.1" }

    Write-Host "`nConnect using:" -ForegroundColor Yellow
    foreach ($ip in $ipAddresses) {
        Write-Host "  vnc://$($ip.IPAddress):5900" -ForegroundColor White
        Write-Host "  or: $($ip.IPAddress)::5900" -ForegroundColor Gray
    }
}

# Main execution
function Main {
    Write-Host "VNC Connection Test Suite" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan

    $results = @{
        Service = Test-VNCServiceRunning
        Port = Test-VNCPort
        Firewall = Test-VNCFirewall
        Registry = Test-VNCRegistry
        Process = Test-VNCProcess
        Connectivity = Test-VNCConnectivity
    }

    Test-VNCExternalAccess

    # Summary
    Write-Host "`n=========================" -ForegroundColor Cyan
    Write-Host "Test Summary" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan

    $passed = ($results.Values | Where-Object { $_ }).Count
    $total = $results.Count

    Write-Host "`nPassed: $passed / $total tests" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

    if ($passed -eq $total) {
        Write-Host "VNC is properly configured!" -ForegroundColor Green
        Get-VNCConnectionInfo
    }
    else {
        Write-Host "`nIssues detected. Run install_vnc.ps1 to fix." -ForegroundColor Yellow
    }
}

Main
