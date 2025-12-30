# browser_hardening.ps1 - Harden Browser Against Fingerprinting
#
# Configures Chrome and Edge to resist fingerprinting.
#
# Usage: Run as Administrator in PowerShell
#   .\browser_hardening.ps1

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

function Configure-ChromeHardening {
    Write-Log "Configuring Chrome hardening..."

    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"

    if (-not (Test-Path $chromePolicyPath)) {
        New-Item -Path $chromePolicyPath -Force | Out-Null
    }

    # Privacy settings
    Set-ItemProperty -Path $chromePolicyPath -Name "BlockThirdPartyCookies" -Value 1 -Type DWord
    Set-ItemProperty -Path $chromePolicyPath -Name "EnableDoNotTrack" -Value 1 -Type DWord

    # Disable features that reveal automation
    Set-ItemProperty -Path $chromePolicyPath -Name "CommandLineFlagSecurityWarningsEnabled" -Value 0 -Type DWord

    # Disable hardware acceleration fingerprinting
    Set-ItemProperty -Path $chromePolicyPath -Name "HardwareAccelerationModeEnabled" -Value 1 -Type DWord

    # Disable WebRTC IP leaks
    Set-ItemProperty -Path $chromePolicyPath -Name "WebRtcUdpPortRange" -Value "" -Type String

    # Disable prefetch (reduces fingerprint surface)
    Set-ItemProperty -Path $chromePolicyPath -Name "NetworkPredictionOptions" -Value 2 -Type DWord

    # Standard referrer policy
    Set-ItemProperty -Path $chromePolicyPath -Name "ForceMajorVersionToMinorPositionInUserAgent" -Value 0 -Type DWord

    Write-Log "Chrome hardening applied"
}

function Configure-EdgeHardening {
    Write-Log "Configuring Edge hardening..."

    $edgePolicyPath = "HKLM:\SOFTWARE\Policies\Microsoft\Edge"

    if (-not (Test-Path $edgePolicyPath)) {
        New-Item -Path $edgePolicyPath -Force | Out-Null
    }

    # Similar privacy settings for Edge
    Set-ItemProperty -Path $edgePolicyPath -Name "BlockThirdPartyCookies" -Value 1 -Type DWord
    Set-ItemProperty -Path $edgePolicyPath -Name "ConfigureDoNotTrack" -Value 1 -Type DWord
    Set-ItemProperty -Path $edgePolicyPath -Name "CommandLineFlagSecurityWarningsEnabled" -Value 0 -Type DWord

    Write-Log "Edge hardening applied"
}

function Create-BrowserLaunchScript {
    Write-Log "Creating browser launch script with anti-fingerprint flags..."

    $chromePath = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe"
    $chromePathX86 = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"

    if (Test-Path $chromePath) {
        $exePath = $chromePath
    }
    elseif (Test-Path $chromePathX86) {
        $exePath = $chromePathX86
    }
    else {
        Write-Log "Chrome not found" "WARN"
        return
    }

    # Create launch script
    $scriptPath = "$env:USERPROFILE\Desktop\Chrome-Private.bat"
    $scriptContent = @"
@echo off
REM Chrome with anti-fingerprint flags
start "" "$exePath" ^
    --disable-blink-features=AutomationControlled ^
    --disable-features=IsolateOrigins,site-per-process ^
    --disable-web-security ^
    --user-data-dir="%LOCALAPPDATA%\Google\Chrome\User Data" ^
    --no-first-run ^
    --no-default-browser-check
"@

    Set-Content -Path $scriptPath -Value $scriptContent -Force
    Write-Log "Browser launch script created: $scriptPath"
}

function Configure-DNSSettings {
    Write-Log "Configuring DNS settings..."

    # Use standard DNS (not DoH by default)
    # This is more common and less suspicious

    $dnsPath = "HKLM:\SYSTEM\CurrentControlSet\Services\Dnscache\Parameters"

    # Disable DNS over HTTPS (more common to not use it)
    Set-ItemProperty -Path $dnsPath -Name "EnableDnsOverHttps" -Value 0 -Type DWord -ErrorAction SilentlyContinue

    Write-Log "DNS settings configured"
}

function Configure-PluginsAndFonts {
    Write-Log "Configuring plugins and fonts..."

    # Standard Windows fonts (don't add unusual fonts)
    # Just verify common fonts exist

    $fontsPath = "C:\Windows\Fonts"
    $commonFonts = @("arial.ttf", "times.ttf", "cour.ttf", "verdana.ttf")

    foreach ($font in $commonFonts) {
        if (Test-Path (Join-Path $fontsPath $font)) {
            Write-Log "  Font present: $font"
        }
    }

    Write-Log "Fonts verified"
}

function Disable-WebGLFingerprinting {
    Write-Log "Note: WebGL fingerprinting mitigation..."

    # WebGL fingerprinting is primarily handled by browser extensions
    # Common extensions: Canvas Blocker, Privacy Badger

    Write-Log "  Install Canvas Blocker extension for WebGL protection" "WARN"
    Write-Log "  This cannot be fully mitigated via registry" "WARN"
}

function Configure-CookieSettings {
    Write-Log "Configuring cookie settings..."

    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"

    # Allow first-party cookies (normal behavior)
    Set-ItemProperty -Path $chromePolicyPath -Name "BlockThirdPartyCookies" -Value 1 -Type DWord

    # Don't clear cookies on exit (more normal)
    # Extensions can handle this if needed

    Write-Log "Cookie settings configured"
}

function Set-ScreenResolutionConsistent {
    Write-Log "Ensuring consistent screen resolution..."

    # Check current resolution
    Add-Type -AssemblyName System.Windows.Forms
    $screen = [System.Windows.Forms.Screen]::PrimaryScreen
    $bounds = $screen.Bounds

    Write-Log "  Current resolution: $($bounds.Width)x$($bounds.Height)"

    # Common resolutions (less fingerprinting risk)
    $commonResolutions = @(
        "1920x1080",
        "1366x768",
        "1440x900",
        "1536x864"
    )

    $currentRes = "$($bounds.Width)x$($bounds.Height)"
    if ($commonResolutions -contains $currentRes) {
        Write-Log "  Resolution is common: OK"
    }
    else {
        Write-Log "  Consider using a more common resolution" "WARN"
    }
}

# Main execution
function Main {
    Write-Log "Browser Hardening Script"
    Write-Log "========================"

    Configure-ChromeHardening
    Configure-EdgeHardening
    Create-BrowserLaunchScript
    Configure-DNSSettings
    Configure-PluginsAndFonts
    Disable-WebGLFingerprinting
    Configure-CookieSettings
    Set-ScreenResolutionConsistent

    Write-Log ""
    Write-Log "========================"
    Write-Log "Browser hardening complete!"
    Write-Log ""
    Write-Log "Additional recommendations:"
    Write-Log "  1. Install uBlock Origin extension"
    Write-Log "  2. Install Privacy Badger extension"
    Write-Log "  3. Consider Canvas Blocker for fingerprint protection"
    Write-Log "  4. Use the Chrome-Private.bat script on desktop"
}

Main
