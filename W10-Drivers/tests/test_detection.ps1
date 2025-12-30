# test_detection.ps1 - Test Anti-Detection Measures
#
# Checks if the system appears as a normal user environment
# rather than an automated/virtualized system.
#
# Usage: Run in PowerShell
#   .\test_detection.ps1

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

function Test-WebDriverRegistry {
    Write-Host "`nChecking WebDriver Registry Keys..." -ForegroundColor Cyan

    $webdriverPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Edge\WebDriver",
        "HKLM:\SOFTWARE\Microsoft\Internet Explorer\WebDriver",
        "HKCU:\SOFTWARE\Microsoft\Edge\WebDriver",
        "HKLM:\SOFTWARE\Selenium",
        "HKCU:\SOFTWARE\Selenium"
    )

    $found = $false
    foreach ($path in $webdriverPaths) {
        if (Test-Path $path) {
            Write-TestResult "No WebDriver keys" $false "Found: $path"
            $found = $true
        }
    }

    if (-not $found) {
        Write-TestResult "No WebDriver keys" $true "No automation registry keys found"
    }

    return -not $found
}

function Test-SeleniumFiles {
    Write-Host "`nChecking for Selenium Files..." -ForegroundColor Cyan

    $seleniumPatterns = @(
        "$env:TEMP\scoped_dir*",
        "$env:LOCALAPPDATA\chromedriver*",
        "$env:LOCALAPPDATA\geckodriver*",
        "$env:APPDATA\Selenium*"
    )

    $found = $false
    foreach ($pattern in $seleniumPatterns) {
        $files = Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue
        if ($files) {
            Write-TestResult "No Selenium files" $false "Found: $pattern"
            $found = $true
        }
    }

    if (-not $found) {
        Write-TestResult "No Selenium files" $true "No Selenium artifacts found"
    }

    return -not $found
}

function Test-TelemetryDisabled {
    Write-Host "`nChecking Telemetry Settings..." -ForegroundColor Cyan

    $dataCollectionPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
    $telemetryValue = Get-ItemProperty -Path $dataCollectionPath -Name "AllowTelemetry" -ErrorAction SilentlyContinue

    if ($telemetryValue -and $telemetryValue.AllowTelemetry -eq 0) {
        Write-TestResult "Telemetry Disabled" $true "AllowTelemetry = 0"
        return $true
    }
    else {
        Write-TestResult "Telemetry Disabled" $false "Telemetry may be sending data"
        return $false
    }
}

function Test-TelemetryServices {
    Write-Host "`nChecking Telemetry Services..." -ForegroundColor Cyan

    $telemetryServices = @("DiagTrack", "dmwappushservice")
    $allDisabled = $true

    foreach ($svcName in $telemetryServices) {
        $service = Get-Service -Name $svcName -ErrorAction SilentlyContinue

        if ($service) {
            $disabled = $service.StartType -eq "Disabled"
            Write-TestResult "Service $svcName disabled" $disabled "Status: $($service.Status), StartType: $($service.StartType)"

            if (-not $disabled) {
                $allDisabled = $false
            }
        }
    }

    return $allDisabled
}

function Test-WindowsUpdateDisabled {
    Write-Host "`nChecking Windows Update Status..." -ForegroundColor Cyan

    $wuService = Get-Service -Name "wuauserv" -ErrorAction SilentlyContinue

    if ($wuService -and $wuService.StartType -eq "Disabled") {
        Write-TestResult "Windows Update Disabled" $true
        return $true
    }
    else {
        Write-TestResult "Windows Update Disabled" $false "Update service may interfere"
        return $false
    }
}

function Test-BrowserPolicies {
    Write-Host "`nChecking Browser Policies..." -ForegroundColor Cyan

    $chromePath = "HKLM:\SOFTWARE\Policies\Google\Chrome"
    $edgePath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"

    $results = @{}

    # Chrome policies
    if (Test-Path $chromePath) {
        $thirdPartyCookies = Get-ItemProperty -Path $chromePath -Name "BlockThirdPartyCookies" -ErrorAction SilentlyContinue
        $cmdWarnings = Get-ItemProperty -Path $chromePath -Name "CommandLineFlagSecurityWarningsEnabled" -ErrorAction SilentlyContinue

        $results["Chrome 3rd Party Cookies Blocked"] = ($thirdPartyCookies.BlockThirdPartyCookies -eq 1)
        $results["Chrome Command Warnings Disabled"] = ($cmdWarnings.CommandLineFlagSecurityWarningsEnabled -eq 0)
    }
    else {
        $results["Chrome Policies Configured"] = $false
    }

    # Edge policies
    if (Test-Path $edgePath) {
        $edgeCookies = Get-ItemProperty -Path $edgePath -Name "BlockThirdPartyCookies" -ErrorAction SilentlyContinue
        $results["Edge 3rd Party Cookies Blocked"] = ($edgeCookies.BlockThirdPartyCookies -eq 1)
    }

    foreach ($test in $results.Keys) {
        Write-TestResult $test $results[$test]
    }

    return ($results.Values | Where-Object { $_ }).Count -ge 2
}

function Test-VMIndicators {
    Write-Host "`nChecking VM Detection Indicators..." -ForegroundColor Cyan

    # Check for obvious VM indicators that should be hidden
    $biosInfo = Get-WmiObject -Class Win32_BIOS
    $computerSystem = Get-WmiObject -Class Win32_ComputerSystem

    $vmIndicators = @()

    # Check manufacturer
    if ($computerSystem.Manufacturer -like "*QEMU*" -or
        $computerSystem.Manufacturer -like "*VMware*" -or
        $computerSystem.Manufacturer -like "*VirtualBox*") {
        $vmIndicators += "Manufacturer: $($computerSystem.Manufacturer)"
    }

    # Check model
    if ($computerSystem.Model -like "*Virtual*" -or
        $computerSystem.Model -like "*QEMU*") {
        $vmIndicators += "Model: $($computerSystem.Model)"
    }

    # Check BIOS
    if ($biosInfo.SerialNumber -like "*QEMU*" -or
        $biosInfo.Manufacturer -like "*QEMU*") {
        $vmIndicators += "BIOS shows VM"
    }

    if ($vmIndicators.Count -gt 0) {
        Write-TestResult "VM Indicators Hidden" $false
        foreach ($indicator in $vmIndicators) {
            Write-Host "       Found: $indicator" -ForegroundColor Yellow
        }
        return $false
    }
    else {
        Write-TestResult "VM Indicators Hidden" $true "System appears as physical hardware"
        return $true
    }
}

function Test-RealisticSettings {
    Write-Host "`nChecking Realistic User Settings..." -ForegroundColor Cyan

    $results = @{}

    # Check timezone is set
    $tz = Get-TimeZone
    $results["Timezone Configured"] = $tz -ne $null
    Write-Host "       Timezone: $($tz.Id)" -ForegroundColor Gray

    # Check locale
    $locale = Get-WinSystemLocale
    $results["Locale Configured"] = $locale -ne $null
    Write-Host "       Locale: $($locale.Name)" -ForegroundColor Gray

    # Check for user documents
    $docs = Get-ChildItem "$env:USERPROFILE\Documents" -ErrorAction SilentlyContinue
    $results["User Documents Exist"] = ($docs.Count -gt 0)
    Write-Host "       Documents: $($docs.Count) items" -ForegroundColor Gray

    # Check display settings
    Add-Type -AssemblyName System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $commonResolutions = @("1920x1080", "1366x768", "1440x900", "1536x864", "2560x1440")
    $currentRes = "$($screen.Width)x$($screen.Height)"
    $results["Common Resolution"] = $commonResolutions -contains $currentRes
    Write-Host "       Resolution: $currentRes" -ForegroundColor Gray

    foreach ($test in $results.Keys) {
        Write-TestResult $test $results[$test]
    }

    return ($results.Values | Where-Object { $_ }).Count -ge 3
}

function Test-BrowsingHistory {
    Write-Host "`nChecking Browser Artifacts..." -ForegroundColor Cyan

    $chromeHistoryPath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\History"
    $edgeHistoryPath = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\History"

    $hasHistory = $false

    if (Test-Path $chromeHistoryPath) {
        $historySize = (Get-Item $chromeHistoryPath).Length
        Write-TestResult "Chrome History Exists" $true "Size: $([math]::Round($historySize/1KB, 2)) KB"
        $hasHistory = $true
    }
    else {
        Write-TestResult "Chrome History Exists" $false "No history - browser may look new"
    }

    if (Test-Path $edgeHistoryPath) {
        $historySize = (Get-Item $edgeHistoryPath).Length
        Write-TestResult "Edge History Exists" $true "Size: $([math]::Round($historySize/1KB, 2)) KB"
        $hasHistory = $true
    }

    return $hasHistory
}

function Test-FirewallPorts {
    Write-Host "`nChecking Suspicious Open Ports..." -ForegroundColor Cyan

    $suspiciousPorts = @(9222, 9229, 9515, 4444, 5555)  # Debug/Selenium ports
    $openSuspicious = @()

    foreach ($port in $suspiciousPorts) {
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            $openSuspicious += $port
        }
    }

    if ($openSuspicious.Count -gt 0) {
        Write-TestResult "No Debug Ports Open" $false "Open: $($openSuspicious -join ', ')"
        return $false
    }
    else {
        Write-TestResult "No Debug Ports Open" $true "No suspicious ports listening"
        return $true
    }
}

function Get-DetectionScore {
    param([hashtable]$Results)

    $passed = ($Results.Values | Where-Object { $_ }).Count
    $total = $Results.Count
    $percentage = [math]::Round(($passed / $total) * 100, 0)

    return @{
        Passed = $passed
        Total = $total
        Percentage = $percentage
    }
}

# Main execution
function Main {
    Write-Host "Anti-Detection Test Suite" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan

    $results = @{
        WebDriverRegistry = Test-WebDriverRegistry
        SeleniumFiles = Test-SeleniumFiles
        TelemetryDisabled = Test-TelemetryDisabled
        TelemetryServices = Test-TelemetryServices
        WindowsUpdateDisabled = Test-WindowsUpdateDisabled
        BrowserPolicies = Test-BrowserPolicies
        VMIndicators = Test-VMIndicators
        RealisticSettings = Test-RealisticSettings
        BrowsingHistory = Test-BrowsingHistory
        FirewallPorts = Test-FirewallPorts
    }

    # Summary
    Write-Host "`n=========================" -ForegroundColor Cyan
    Write-Host "Detection Risk Assessment" -ForegroundColor Cyan
    Write-Host "=========================" -ForegroundColor Cyan

    $score = Get-DetectionScore -Results $results

    Write-Host "`nPassed: $($score.Passed) / $($score.Total) tests ($($score.Percentage)%)" -ForegroundColor $(
        if ($score.Percentage -ge 80) { "Green" }
        elseif ($score.Percentage -ge 60) { "Yellow" }
        else { "Red" }
    )

    if ($score.Percentage -ge 80) {
        Write-Host "`nSystem appears well-configured for stealth operation." -ForegroundColor Green
    }
    elseif ($score.Percentage -ge 60) {
        Write-Host "`nSome detection risks present. Review failed tests." -ForegroundColor Yellow
    }
    else {
        Write-Host "`nHigh detection risk! Run hardening scripts before production use." -ForegroundColor Red
    }

    # Recommendations
    Write-Host "`nRecommendations:" -ForegroundColor Cyan

    if (-not $results.WebDriverRegistry) {
        Write-Host "  - Run anti_automation.ps1 to remove WebDriver keys" -ForegroundColor Yellow
    }
    if (-not $results.TelemetryDisabled -or -not $results.TelemetryServices) {
        Write-Host "  - Run disable_telemetry.ps1 to stop data collection" -ForegroundColor Yellow
    }
    if (-not $results.BrowsingHistory) {
        Write-Host "  - Build browsing history per fingerprint/browsing_history.md" -ForegroundColor Yellow
    }
    if (-not $results.VMIndicators) {
        Write-Host "  - Consider SMBIOS spoofing in Proxmox VM config" -ForegroundColor Yellow
    }
}

Main
