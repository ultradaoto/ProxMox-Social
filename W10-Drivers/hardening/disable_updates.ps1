# disable_updates.ps1 - Disable Windows Updates
#
# Prevents automatic updates that could interfere with operation.
#
# Usage: Run as Administrator in PowerShell
#   .\disable_updates.ps1

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

function Disable-WindowsUpdateService {
    Write-Log "Disabling Windows Update service..."

    $updateServices = @(
        "wuauserv",     # Windows Update
        "UsoSvc",       # Update Orchestrator Service
        "WaaSMedicSvc"  # Windows Update Medic Service
    )

    foreach ($service in $updateServices) {
        $svc = Get-Service -Name $service -ErrorAction SilentlyContinue
        if ($svc) {
            Stop-Service -Name $service -Force -ErrorAction SilentlyContinue
            Set-Service -Name $service -StartupType Disabled
            Write-Log "  Disabled: $service"
        }
    }
}

function Configure-UpdatePolicies {
    Write-Log "Configuring Windows Update policies..."

    $wuPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
    $auPath = "$wuPath\AU"

    # Create paths
    if (-not (Test-Path $wuPath)) {
        New-Item -Path $wuPath -Force | Out-Null
    }
    if (-not (Test-Path $auPath)) {
        New-Item -Path $auPath -Force | Out-Null
    }

    # Disable automatic updates
    Set-ItemProperty -Path $auPath -Name "NoAutoUpdate" -Value 1 -Type DWord

    # No auto-restart
    Set-ItemProperty -Path $auPath -Name "NoAutoRebootWithLoggedOnUsers" -Value 1 -Type DWord

    # Configure update notification only (no auto download)
    Set-ItemProperty -Path $auPath -Name "AUOptions" -Value 2 -Type DWord

    # Disable update deferral
    Set-ItemProperty -Path $wuPath -Name "DeferQualityUpdates" -Value 1 -Type DWord
    Set-ItemProperty -Path $wuPath -Name "DeferQualityUpdatesPeriodInDays" -Value 365 -Type DWord
    Set-ItemProperty -Path $wuPath -Name "DeferFeatureUpdates" -Value 1 -Type DWord
    Set-ItemProperty -Path $wuPath -Name "DeferFeatureUpdatesPeriodInDays" -Value 365 -Type DWord

    Write-Log "Update policies configured"
}

function Disable-UpdateTasks {
    Write-Log "Disabling Windows Update scheduled tasks..."

    $updateTasks = @(
        "\Microsoft\Windows\UpdateOrchestrator\Schedule Scan",
        "\Microsoft\Windows\UpdateOrchestrator\USO_UxBroker",
        "\Microsoft\Windows\UpdateOrchestrator\Reboot",
        "\Microsoft\Windows\UpdateOrchestrator\Refresh Settings",
        "\Microsoft\Windows\WindowsUpdate\Scheduled Start",
        "\Microsoft\Windows\WindowsUpdate\sih"
    )

    foreach ($task in $updateTasks) {
        Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
        Write-Log "  Disabled: $($task.Split('\')[-1])"
    }
}

function Block-UpdateServers {
    Write-Log "Blocking Windows Update servers..."

    # This is aggressive - only use if updates must be completely blocked
    Write-Log "  Skipping server block (use hosts file if needed)" "WARN"

    # Uncomment to block update servers
    # $updateHosts = @(
    #     "update.microsoft.com",
    #     "windowsupdate.microsoft.com",
    #     "download.windowsupdate.com"
    # )
}

function Disable-DeliveryOptimization {
    Write-Log "Disabling Delivery Optimization..."

    $doPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DeliveryOptimization"

    if (-not (Test-Path $doPath)) {
        New-Item -Path $doPath -Force | Out-Null
    }

    # Disable completely
    Set-ItemProperty -Path $doPath -Name "DODownloadMode" -Value 0 -Type DWord

    Write-Log "Delivery Optimization disabled"
}

function Configure-RestartBehavior {
    Write-Log "Configuring restart behavior..."

    $restartPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"

    # Set active hours (full day to prevent forced restarts)
    Set-ItemProperty -Path $restartPath -Name "SetActiveHours" -Value 1 -Type DWord -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $restartPath -Name "ActiveHoursStart" -Value 0 -Type DWord -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $restartPath -Name "ActiveHoursEnd" -Value 23 -Type DWord -ErrorAction SilentlyContinue

    Write-Log "Restart behavior configured"
}

function Disable-StoreUpdates {
    Write-Log "Disabling Microsoft Store updates..."

    $storePath = "HKLM:\SOFTWARE\Policies\Microsoft\WindowsStore"

    if (-not (Test-Path $storePath)) {
        New-Item -Path $storePath -Force | Out-Null
    }

    Set-ItemProperty -Path $storePath -Name "AutoDownload" -Value 2 -Type DWord

    # Disable Store app entirely (optional)
    # Set-ItemProperty -Path $storePath -Name "RemoveWindowsStore" -Value 1 -Type DWord

    Write-Log "Store updates disabled"
}

function Verify-UpdatesDisabled {
    Write-Log "Verifying update settings..."

    $wuService = Get-Service -Name "wuauserv" -ErrorAction SilentlyContinue

    if ($wuService.StartType -eq "Disabled") {
        Write-Log "  [PASS] Windows Update service disabled"
    }
    else {
        Write-Log "  [WARN] Windows Update service not fully disabled" "WARN"
    }
}

# Main execution
function Main {
    Write-Log "Windows Update Disabling Script"
    Write-Log "================================"

    Disable-WindowsUpdateService
    Configure-UpdatePolicies
    Disable-UpdateTasks
    Block-UpdateServers
    Disable-DeliveryOptimization
    Configure-RestartBehavior
    Disable-StoreUpdates
    Verify-UpdatesDisabled

    Write-Log ""
    Write-Log "================================"
    Write-Log "Windows Updates disabled!"
    Write-Log ""
    Write-Log "WARNING: Security updates will NOT be installed!" "WARN"
    Write-Log "Consider periodic manual updates for security patches." "WARN"
}

Main
