# disable_telemetry.ps1 - Disable Windows Telemetry
#
# Minimizes data collection and telemetry to reduce fingerprinting.
#
# Usage: Run as Administrator in PowerShell
#   .\disable_telemetry.ps1

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

function Disable-DiagnosticDataCollection {
    Write-Log "Disabling diagnostic data collection..."

    $dataCollectionPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"

    if (-not (Test-Path $dataCollectionPath)) {
        New-Item -Path $dataCollectionPath -Force | Out-Null
    }

    # Set telemetry to Security level (minimum, enterprise only)
    Set-ItemProperty -Path $dataCollectionPath -Name "AllowTelemetry" -Value 0 -Type DWord

    # Disable diagnostic data viewer
    Set-ItemProperty -Path $dataCollectionPath -Name "DisableDiagnosticDataViewer" -Value 1 -Type DWord

    # Disable tailored experiences
    Set-ItemProperty -Path $dataCollectionPath -Name "DisableTailoredExperiencesWithDiagnosticData" -Value 1 -Type DWord

    Write-Log "Diagnostic data collection disabled"
}

function Disable-TelemetryServices {
    Write-Log "Disabling telemetry services..."

    $telemetryServices = @(
        "DiagTrack",                    # Connected User Experiences and Telemetry
        "dmwappushservice",             # WAP Push Message Routing Service
        "diagnosticshub.standardcollector.service"  # Diagnostics Hub
    )

    foreach ($service in $telemetryServices) {
        $svc = Get-Service -Name $service -ErrorAction SilentlyContinue
        if ($svc) {
            Stop-Service -Name $service -Force -ErrorAction SilentlyContinue
            Set-Service -Name $service -StartupType Disabled
            Write-Log "  Disabled: $service"
        }
    }
}

function Disable-TelemetryTasks {
    Write-Log "Disabling telemetry scheduled tasks..."

    $telemetryTasks = @(
        "\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser",
        "\Microsoft\Windows\Application Experience\ProgramDataUpdater",
        "\Microsoft\Windows\Autochk\Proxy",
        "\Microsoft\Windows\Customer Experience Improvement Program\Consolidator",
        "\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip",
        "\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector",
        "\Microsoft\Windows\Feedback\Siuf\DmClient",
        "\Microsoft\Windows\Windows Error Reporting\QueueReporting"
    )

    foreach ($task in $telemetryTasks) {
        Disable-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
        Write-Log "  Disabled task: $($task.Split('\')[-1])"
    }
}

function Block-TelemetryHosts {
    Write-Log "Blocking telemetry hosts..."

    $hostsFile = "$env:SystemRoot\System32\drivers\etc\hosts"
    $telemetryHosts = @(
        "vortex.data.microsoft.com",
        "vortex-win.data.microsoft.com",
        "telecommand.telemetry.microsoft.com",
        "telecommand.telemetry.microsoft.com.nsatc.net",
        "oca.telemetry.microsoft.com",
        "oca.telemetry.microsoft.com.nsatc.net",
        "sqm.telemetry.microsoft.com",
        "sqm.telemetry.microsoft.com.nsatc.net",
        "watson.telemetry.microsoft.com",
        "watson.telemetry.microsoft.com.nsatc.net",
        "redir.metaservices.microsoft.com",
        "choice.microsoft.com",
        "choice.microsoft.com.nsatc.net",
        "df.telemetry.microsoft.com",
        "reports.wes.df.telemetry.microsoft.com",
        "settings-sandbox.data.microsoft.com"
    )

    # Read current hosts file
    $currentHosts = Get-Content $hostsFile -ErrorAction SilentlyContinue

    # Add telemetry blocks
    $hostsToAdd = @()
    foreach ($host in $telemetryHosts) {
        if ($currentHosts -notcontains "0.0.0.0 $host") {
            $hostsToAdd += "0.0.0.0 $host"
        }
    }

    if ($hostsToAdd.Count -gt 0) {
        Add-Content -Path $hostsFile -Value ""
        Add-Content -Path $hostsFile -Value "# Telemetry blocks (added by anti-telemetry script)"
        Add-Content -Path $hostsFile -Value $hostsToAdd
        Write-Log "  Added $($hostsToAdd.Count) hosts to blocklist"
    }
    else {
        Write-Log "  Telemetry hosts already blocked"
    }
}

function Disable-ActivityHistory {
    Write-Log "Disabling activity history..."

    $activityPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\System"

    if (-not (Test-Path $activityPath)) {
        New-Item -Path $activityPath -Force | Out-Null
    }

    Set-ItemProperty -Path $activityPath -Name "EnableActivityFeed" -Value 0 -Type DWord
    Set-ItemProperty -Path $activityPath -Name "PublishUserActivities" -Value 0 -Type DWord
    Set-ItemProperty -Path $activityPath -Name "UploadUserActivities" -Value 0 -Type DWord

    Write-Log "Activity history disabled"
}

function Disable-AdvertisingID {
    Write-Log "Disabling advertising ID..."

    $advertisingPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo"

    if (-not (Test-Path $advertisingPath)) {
        New-Item -Path $advertisingPath -Force | Out-Null
    }

    Set-ItemProperty -Path $advertisingPath -Name "DisabledByGroupPolicy" -Value 1 -Type DWord

    Write-Log "Advertising ID disabled"
}

function Disable-Cortana {
    Write-Log "Disabling Cortana..."

    $cortanaPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Search"

    if (-not (Test-Path $cortanaPath)) {
        New-Item -Path $cortanaPath -Force | Out-Null
    }

    Set-ItemProperty -Path $cortanaPath -Name "AllowCortana" -Value 0 -Type DWord
    Set-ItemProperty -Path $cortanaPath -Name "AllowSearchToUseLocation" -Value 0 -Type DWord
    Set-ItemProperty -Path $cortanaPath -Name "DisableWebSearch" -Value 1 -Type DWord

    Write-Log "Cortana disabled"
}

function Disable-LocationTracking {
    Write-Log "Disabling location tracking..."

    $locationPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\LocationAndSensors"

    if (-not (Test-Path $locationPath)) {
        New-Item -Path $locationPath -Force | Out-Null
    }

    Set-ItemProperty -Path $locationPath -Name "DisableLocation" -Value 1 -Type DWord
    Set-ItemProperty -Path $locationPath -Name "DisableLocationScripting" -Value 1 -Type DWord
    Set-ItemProperty -Path $locationPath -Name "DisableSensors" -Value 1 -Type DWord

    Write-Log "Location tracking disabled"
}

function Disable-ErrorReporting {
    Write-Log "Disabling Windows Error Reporting..."

    $werPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Windows Error Reporting"

    if (-not (Test-Path $werPath)) {
        New-Item -Path $werPath -Force | Out-Null
    }

    Set-ItemProperty -Path $werPath -Name "Disabled" -Value 1 -Type DWord

    # Disable WER service
    Set-Service -Name "WerSvc" -StartupType Disabled -ErrorAction SilentlyContinue

    Write-Log "Error reporting disabled"
}

# Main execution
function Main {
    Write-Log "Windows Telemetry Disabling Script"
    Write-Log "==================================="

    Disable-DiagnosticDataCollection
    Disable-TelemetryServices
    Disable-TelemetryTasks
    Block-TelemetryHosts
    Disable-ActivityHistory
    Disable-AdvertisingID
    Disable-Cortana
    Disable-LocationTracking
    Disable-ErrorReporting

    Write-Log ""
    Write-Log "==================================="
    Write-Log "Telemetry disabled!"
    Write-Log ""
    Write-Log "A restart is recommended for full effect."
}

Main
