# quick_recovery.ps1 - Quick Recovery Script
#
# Quickly restores critical services when something goes wrong.
# Fixes common issues that break VNC or input functionality.
#
# Usage: Run as Administrator in PowerShell
#   .\quick_recovery.ps1

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

function Restart-VNCService {
    Write-Log "Restarting VNC service..."

    $vncServices = @("tvnserver", "TightVNC", "WinVNC4")

    foreach ($svc in $vncServices) {
        $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
        if ($service) {
            Restart-Service -Name $svc -Force
            Write-Log "  Restarted: $svc"
            return $true
        }
    }

    Write-Log "  No VNC service found" "WARN"
    return $false
}

function Reset-NetworkAdapter {
    Write-Log "Resetting network adapters..."

    Get-NetAdapter | Where-Object { $_.Status -eq "Disabled" } | Enable-NetAdapter

    # Restart primary adapter
    $primaryAdapter = Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Select-Object -First 1

    if ($primaryAdapter) {
        Restart-NetAdapter -Name $primaryAdapter.Name
        Write-Log "  Reset adapter: $($primaryAdapter.Name)"
    }

    # Flush DNS
    Clear-DnsClientCache
    Write-Log "  Flushed DNS cache"
}

function Fix-InputDevices {
    Write-Log "Fixing input device issues..."

    # Restart HID services
    $hidServices = @("hidserv", "TabletInputService")

    foreach ($svc in $hidServices) {
        $service = Get-Service -Name $svc -ErrorAction SilentlyContinue
        if ($service) {
            Restart-Service -Name $svc -Force
            Write-Log "  Restarted: $svc"
        }
    }

    # Reset mouse settings
    $mousePath = "HKCU:\Control Panel\Mouse"
    Set-ItemProperty -Path $mousePath -Name "MouseSpeed" -Value "1"
    Set-ItemProperty -Path $mousePath -Name "MouseSensitivity" -Value "10"

    Write-Log "  Mouse settings reset"
}

function Clear-TemporaryFiles {
    Write-Log "Clearing temporary files..."

    $tempPaths = @(
        "$env:TEMP\*",
        "$env:LOCALAPPDATA\Temp\*",
        "$env:SystemRoot\Temp\*"
    )

    $cleared = 0
    foreach ($path in $tempPaths) {
        $items = Get-ChildItem -Path $path -Recurse -Force -ErrorAction SilentlyContinue
        $items | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
        $cleared += $items.Count
    }

    Write-Log "  Cleared $cleared items"
}

function Reset-FirewallRules {
    Write-Log "Resetting firewall rules for VNC..."

    # Ensure VNC port is open
    $vncRule = Get-NetFirewallRule -DisplayName "*VNC*" -ErrorAction SilentlyContinue

    if (-not $vncRule) {
        New-NetFirewallRule -DisplayName "VNC Server" `
            -Direction Inbound -Protocol TCP -LocalPort 5900 `
            -Action Allow -Profile Any
        Write-Log "  Created VNC firewall rule"
    }
    else {
        $vncRule | Enable-NetFirewallRule
        Write-Log "  Enabled existing VNC rules"
    }
}

function Kill-ProblematicProcesses {
    Write-Log "Killing problematic processes..."

    $problematic = @(
        "dwm",      # Desktop Window Manager (if hung)
        "SearchUI", # Cortana search (can cause issues)
        "ShellExperienceHost"
    )

    # Only kill if they're using excessive resources
    foreach ($proc in $problematic) {
        $process = Get-Process -Name $proc -ErrorAction SilentlyContinue
        if ($process -and $process.CPU -gt 50) {
            Stop-Process -Name $proc -Force -ErrorAction SilentlyContinue
            Write-Log "  Killed high-CPU process: $proc"
        }
    }
}

function Restart-Explorer {
    Write-Log "Restarting Windows Explorer..."

    Stop-Process -Name explorer -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    Start-Process explorer

    Write-Log "  Explorer restarted"
}

function Check-DiskSpace {
    Write-Log "Checking disk space..."

    $drives = Get-WmiObject Win32_LogicalDisk -Filter "DriveType=3"

    foreach ($drive in $drives) {
        $freeGB = [math]::Round($drive.FreeSpace / 1GB, 2)
        $totalGB = [math]::Round($drive.Size / 1GB, 2)
        $percentFree = [math]::Round(($drive.FreeSpace / $drive.Size) * 100, 1)

        $level = if ($percentFree -lt 10) { "ERROR" } elseif ($percentFree -lt 20) { "WARN" } else { "INFO" }

        Write-Log "  $($drive.DeviceID) $freeGB GB free of $totalGB GB ($percentFree%)" $level
    }
}

function Check-SystemHealth {
    Write-Log "Checking system health..."

    # CPU usage
    $cpu = (Get-WmiObject Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
    $cpuLevel = if ($cpu -gt 90) { "ERROR" } elseif ($cpu -gt 70) { "WARN" } else { "INFO" }
    Write-Log "  CPU Usage: $cpu%" $cpuLevel

    # Memory usage
    $os = Get-WmiObject Win32_OperatingSystem
    $memUsed = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 2)
    $memTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
    $memPercent = [math]::Round(($memUsed / $memTotal) * 100, 1)
    $memLevel = if ($memPercent -gt 90) { "ERROR" } elseif ($memPercent -gt 80) { "WARN" } else { "INFO" }
    Write-Log "  Memory: $memUsed GB / $memTotal GB ($memPercent%)" $memLevel

    # Uptime
    $uptime = (Get-Date) - $os.ConvertToDateTime($os.LastBootUpTime)
    Write-Log "  Uptime: $($uptime.Days)d $($uptime.Hours)h $($uptime.Minutes)m"
}

function Test-VNCConnection {
    Write-Log "Testing VNC availability..."

    $vncPort = 5900
    $listener = Get-NetTCPConnection -LocalPort $vncPort -State Listen -ErrorAction SilentlyContinue

    if ($listener) {
        Write-Log "  VNC listening on port $vncPort" "INFO"
        return $true
    }
    else {
        Write-Log "  VNC NOT listening on port $vncPort" "ERROR"
        return $false
    }
}

# Main execution
function Main {
    Write-Log "Quick Recovery Script"
    Write-Log "====================="
    Write-Log ""

    # Run all recovery steps
    Restart-VNCService
    Reset-NetworkAdapter
    Fix-InputDevices
    Clear-TemporaryFiles
    Reset-FirewallRules
    Kill-ProblematicProcesses

    Write-Log ""
    Write-Log "System Status Check"
    Write-Log "-------------------"

    Check-SystemHealth
    Check-DiskSpace
    $vncOk = Test-VNCConnection

    Write-Log ""
    Write-Log "====================="

    if ($vncOk) {
        Write-Log "Recovery complete - VNC should be accessible"
    }
    else {
        Write-Log "VNC may still have issues - consider restarting VM" "WARN"
        Write-Log "Use enable_rdp.ps1 for emergency access if needed" "WARN"
    }
}

Main
