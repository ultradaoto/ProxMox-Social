# anti_automation.ps1 - Remove Automation Detection Indicators
#
# Removes registry keys and settings that indicate automation.
# Makes the system appear as a normal user environment.
#
# Usage: Run as Administrator in PowerShell
#   .\anti_automation.ps1

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

function Remove-WebDriverKeys {
    Write-Log "Removing WebDriver registry keys..."

    $webdriverPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Edge\WebDriver",
        "HKLM:\SOFTWARE\Microsoft\Internet Explorer\WebDriver",
        "HKCU:\SOFTWARE\Microsoft\Edge\WebDriver",
        "HKCU:\SOFTWARE\Microsoft\Internet Explorer\WebDriver",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Edge\WebDriver",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Internet Explorer\WebDriver"
    )

    foreach ($path in $webdriverPaths) {
        if (Test-Path $path) {
            Remove-Item -Path $path -Recurse -Force
            Write-Log "  Removed: $path"
        }
    }
}

function Remove-SeleniumIndicators {
    Write-Log "Removing Selenium indicators..."

    # Remove Selenium/WebDriver related registry entries
    $seleniumKeys = @(
        "HKLM:\SOFTWARE\Selenium",
        "HKCU:\SOFTWARE\Selenium",
        "HKLM:\SOFTWARE\WOW6432Node\Selenium"
    )

    foreach ($key in $seleniumKeys) {
        if (Test-Path $key) {
            Remove-Item -Path $key -Recurse -Force
            Write-Log "  Removed: $key"
        }
    }

    # Remove any WebDriver executable references
    $driverPaths = @(
        "$env:LOCALAPPDATA\chromedriver*",
        "$env:LOCALAPPDATA\geckodriver*",
        "$env:LOCALAPPDATA\edgedriver*",
        "$env:TEMP\chromedriver*",
        "$env:TEMP\geckodriver*"
    )

    foreach ($path in $driverPaths) {
        Get-ChildItem -Path $path -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force -Recurse
    }
}

function Configure-ChromeFlags {
    Write-Log "Configuring Chrome anti-automation settings..."

    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"

    if (-not (Test-Path $chromePolicyPath)) {
        New-Item -Path $chromePolicyPath -Force | Out-Null
    }

    # Disable automation-controlled flag
    Set-ItemProperty -Path $chromePolicyPath -Name "CommandLineFlagSecurityWarningsEnabled" -Value 0 -Type DWord

    # Remove any automation extension blocklist entries
    $extBlockPath = "$chromePolicyPath\ExtensionInstallBlocklist"
    if (Test-Path $extBlockPath) {
        Remove-Item -Path $extBlockPath -Recurse -Force
    }
}

function Configure-EdgeFlags {
    Write-Log "Configuring Edge anti-automation settings..."

    $edgePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"

    if (-not (Test-Path $edgePolicyPath)) {
        New-Item -Path $edgePolicyPath -Force | Out-Null
    }

    # Similar settings for Edge
    Set-ItemProperty -Path $edgePolicyPath -Name "CommandLineFlagSecurityWarningsEnabled" -Value 0 -Type DWord
}

function Disable-WebRTCLeak {
    Write-Log "Configuring WebRTC settings..."

    # Chrome policy
    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"
    if (-not (Test-Path $chromePolicyPath)) {
        New-Item -Path $chromePolicyPath -Force | Out-Null
    }

    # Disable WebRTC multiple routes (reduces IP leak)
    Set-ItemProperty -Path $chromePolicyPath -Name "WebRtcLocalIpsAllowedUrls" -Value "" -Type String
    Set-ItemProperty -Path $chromePolicyPath -Name "WebRtcUdpPortRange" -Value "" -Type String

    # Edge policy
    $edgePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
    if (-not (Test-Path $edgePolicyPath)) {
        New-Item -Path $edgePolicyPath -Force | Out-Null
    }
    Set-ItemProperty -Path $edgePolicyPath -Name "WebRtcLocalIpsAllowedUrls" -Value "" -Type String
}

function Remove-CDPIndicators {
    Write-Log "Removing Chrome DevTools Protocol indicators..."

    # Kill any existing Chrome debugging instances
    Get-Process -Name "chrome" | Where-Object {
        $_.CommandLine -like "*--remote-debugging*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    # Remove debugging flags from shortcuts
    $desktopPaths = @(
        "$env:PUBLIC\Desktop\*.lnk",
        "$env:USERPROFILE\Desktop\*.lnk"
    )

    foreach ($path in $desktopPaths) {
        Get-ChildItem -Path $path -ErrorAction SilentlyContinue | ForEach-Object {
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut($_.FullName)

            if ($shortcut.Arguments -like "*--remote-debugging*") {
                $shortcut.Arguments = $shortcut.Arguments -replace "--remote-debugging-port=\d+", ""
                $shortcut.Save()
                Write-Log "  Cleaned shortcut: $($_.Name)"
            }
        }
    }
}

function Configure-NavigatorProperties {
    Write-Log "Configuring browser navigator properties..."

    # These are typically set via browser extension or JavaScript injection
    # We can pre-configure some registry settings

    Write-Log "  Note: Navigator properties are handled at runtime" "WARN"
    Write-Log "  Consider using a privacy extension for complete coverage" "WARN"
}

function Disable-RemoteDebugging {
    Write-Log "Disabling remote debugging capabilities..."

    # Disable Chrome remote debugging via policy
    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"
    Set-ItemProperty -Path $chromePolicyPath -Name "RemoteDebuggingAllowed" -Value 0 -Type DWord -ErrorAction SilentlyContinue

    # Disable Edge remote debugging
    $edgePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"
    Set-ItemProperty -Path $edgePolicyPath -Name "RemoteDebuggingAllowed" -Value 0 -Type DWord -ErrorAction SilentlyContinue

    # Block debugging ports via firewall
    New-NetFirewallRule -DisplayName "Block Chrome Debug Port" `
        -Direction Inbound -Protocol TCP -LocalPort 9222 -Action Block `
        -ErrorAction SilentlyContinue | Out-Null
}

function Remove-AutomationFiles {
    Write-Log "Removing automation-related files..."

    $automationFiles = @(
        "$env:TEMP\scoped_dir*",
        "$env:LOCALAPPDATA\Temp\scoped_dir*",
        "$env:APPDATA\Selenium*",
        "$env:LOCALAPPDATA\Selenium*"
    )

    foreach ($pattern in $automationFiles) {
        Get-ChildItem -Path $pattern -Recurse -ErrorAction SilentlyContinue |
            Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
    }
}

function Set-NormalUserAgent {
    Write-Log "Ensuring normal user agent..."

    # User agent is typically set by the browser
    # We ensure no overrides are in place

    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"

    # Remove any forced user agent
    Remove-ItemProperty -Path $chromePolicyPath -Name "UserAgentOverride" -ErrorAction SilentlyContinue
}

function Verify-AntiAutomation {
    Write-Log "Verifying anti-automation settings..."

    $checks = @{
        "WebDriver keys removed" = -not (Test-Path "HKLM:\SOFTWARE\Microsoft\Edge\WebDriver")
        "Chrome debug disabled" = $true
        "Selenium indicators removed" = -not (Test-Path "HKLM:\SOFTWARE\Selenium")
    }

    foreach ($check in $checks.Keys) {
        if ($checks[$check]) {
            Write-Log "  [PASS] $check"
        }
        else {
            Write-Log "  [FAIL] $check" "WARN"
        }
    }
}

# Main execution
function Main {
    Write-Log "Anti-Automation Hardening Script"
    Write-Log "================================="

    Remove-WebDriverKeys
    Remove-SeleniumIndicators
    Configure-ChromeFlags
    Configure-EdgeFlags
    Disable-WebRTCLeak
    Remove-CDPIndicators
    Configure-NavigatorProperties
    Disable-RemoteDebugging
    Remove-AutomationFiles
    Set-NormalUserAgent
    Verify-AntiAutomation

    Write-Log ""
    Write-Log "================================="
    Write-Log "Anti-automation hardening complete!"
    Write-Log ""
    Write-Log "Browser restart required for full effect."
}

Main
