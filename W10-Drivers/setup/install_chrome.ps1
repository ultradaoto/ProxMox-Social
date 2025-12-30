# install_chrome.ps1 - Install and Configure Google Chrome
#
# Installs Chrome with anti-automation configurations.
#
# Usage: Run as Administrator in PowerShell
#   .\install_chrome.ps1

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

function Download-Chrome {
    Write-Log "Downloading Google Chrome..."

    $tempDir = "$env:TEMP\chrome"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

    # Chrome standalone installer
    $chromeUrl = "https://dl.google.com/chrome/install/latest/chrome_installer.exe"
    $chromePath = "$tempDir\chrome_installer.exe"

    try {
        Invoke-WebRequest -Uri $chromeUrl -OutFile $chromePath -UseBasicParsing
        return $chromePath
    }
    catch {
        Write-Log "Download failed: $_" "ERROR"
        return $null
    }
}

function Install-Chrome {
    param([string]$InstallerPath)

    Write-Log "Installing Google Chrome..."

    $process = Start-Process -FilePath $InstallerPath -ArgumentList "/silent /install" -Wait -PassThru

    if ($process.ExitCode -eq 0) {
        Write-Log "Chrome installed successfully"
        return $true
    }
    else {
        Write-Log "Chrome installation may have issues (exit code: $($process.ExitCode))" "WARN"
        return $true  # Chrome installer sometimes returns non-zero even on success
    }
}

function Configure-ChromePolicies {
    Write-Log "Configuring Chrome policies..."

    $chromePolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome"

    # Ensure registry path exists
    if (-not (Test-Path $chromePolicyPath)) {
        New-Item -Path $chromePolicyPath -Force | Out-Null
    }

    # Disable automation detection
    Set-ItemProperty -Path $chromePolicyPath -Name "CommandLineFlagSecurityWarningsEnabled" -Value 0 -Type DWord

    # Disable first run experience
    Set-ItemProperty -Path $chromePolicyPath -Name "SuppressFirstRunBubble" -Value 1 -Type DWord

    # Disable default browser check
    Set-ItemProperty -Path $chromePolicyPath -Name "DefaultBrowserSettingEnabled" -Value 0 -Type DWord

    # Disable password manager prompts
    Set-ItemProperty -Path $chromePolicyPath -Name "PasswordManagerEnabled" -Value 0 -Type DWord

    # Disable autofill
    Set-ItemProperty -Path $chromePolicyPath -Name "AutofillAddressEnabled" -Value 0 -Type DWord
    Set-ItemProperty -Path $chromePolicyPath -Name "AutofillCreditCardEnabled" -Value 0 -Type DWord

    # Disable sync prompts
    Set-ItemProperty -Path $chromePolicyPath -Name "SyncDisabled" -Value 1 -Type DWord

    # Disable background apps
    Set-ItemProperty -Path $chromePolicyPath -Name "BackgroundModeEnabled" -Value 0 -Type DWord

    # Disable crash reporting
    Set-ItemProperty -Path $chromePolicyPath -Name "MetricsReportingEnabled" -Value 0 -Type DWord

    # Disable Safe Browsing (can interfere with automation)
    Set-ItemProperty -Path $chromePolicyPath -Name "SafeBrowsingEnabled" -Value 0 -Type DWord

    Write-Log "Chrome policies configured"
}

function Create-ChromeShortcut {
    Write-Log "Creating Chrome shortcut with anti-automation flags..."

    $chromePath = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe"
    $chromePathX86 = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"

    if (Test-Path $chromePath) {
        $exePath = $chromePath
    }
    elseif (Test-Path $chromePathX86) {
        $exePath = $chromePathX86
    }
    else {
        Write-Log "Chrome executable not found" "ERROR"
        return
    }

    # Desktop shortcut with anti-automation flags
    $shortcutPath = "$env:PUBLIC\Desktop\Chrome.lnk"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $exePath
    $shortcut.Arguments = "--disable-blink-features=AutomationControlled --disable-features=IsolateOrigins,site-per-process"
    $shortcut.WorkingDirectory = Split-Path $exePath
    $shortcut.Save()

    Write-Log "Chrome shortcut created with anti-automation flags"
}

function Configure-ChromePreferences {
    Write-Log "Configuring Chrome preferences..."

    # Default Chrome profile path
    $chromeUserData = "$env:LOCALAPPDATA\Google\Chrome\User Data"
    $defaultProfile = "$chromeUserData\Default"

    # Create directories if they don't exist
    if (-not (Test-Path $defaultProfile)) {
        New-Item -ItemType Directory -Path $defaultProfile -Force | Out-Null
    }

    # Preferences file
    $prefsPath = "$defaultProfile\Preferences"

    $preferences = @{
        "browser" = @{
            "show_home_button" = $true
            "check_default_browser" = $false
        }
        "profile" = @{
            "default_content_setting_values" = @{
                "notifications" = 2  # Block notifications
            }
        }
        "download" = @{
            "prompt_for_download" = $false
        }
        "savefile" = @{
            "default_directory" = "$env:USERPROFILE\Downloads"
        }
    }

    $prefsJson = ConvertTo-Json -InputObject $preferences -Depth 10

    # Only write if Chrome isn't running
    $chromeProcess = Get-Process -Name "chrome" -ErrorAction SilentlyContinue
    if (-not $chromeProcess) {
        Set-Content -Path $prefsPath -Value $prefsJson -Force
        Write-Log "Chrome preferences configured"
    }
    else {
        Write-Log "Chrome is running, preferences not modified" "WARN"
    }
}

function Install-Extensions {
    Write-Log "Setting up extension installation..."

    # Note: Extensions need to be installed manually or via CRX
    # This sets up registry for forcing extension installation

    $extensionPolicyPath = "HKLM:\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"

    if (-not (Test-Path $extensionPolicyPath)) {
        New-Item -Path $extensionPolicyPath -Force | Out-Null
    }

    # uBlock Origin
    Set-ItemProperty -Path $extensionPolicyPath -Name "1" -Value "cjpalhdlnbpafiamejdnhcphjbkeiagm" -Type String

    Write-Log "Extension policy configured (uBlock Origin will be installed on first run)"
    Write-Log "For other extensions, install manually from Chrome Web Store" "WARN"
}

# Main execution
function Main {
    Write-Log "Chrome Installation Script"
    Write-Log "=========================="

    # Check if already installed
    $chromeInstalled = Test-Path "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe" -or
                       Test-Path "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"

    if ($chromeInstalled) {
        Write-Log "Chrome is already installed"
    }
    else {
        $installer = Download-Chrome
        if ($installer) {
            Install-Chrome -InstallerPath $installer
            Remove-Item -Path (Split-Path $installer -Parent) -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    Configure-ChromePolicies
    Create-ChromeShortcut
    Configure-ChromePreferences
    Install-Extensions

    Write-Log ""
    Write-Log "=========================="
    Write-Log "Chrome Setup Complete!"
    Write-Log ""
    Write-Log "Next steps:"
    Write-Log "  1. Launch Chrome and complete initial setup"
    Write-Log "  2. Log into Google account (for trust score)"
    Write-Log "  3. Install any additional extensions needed"
    Write-Log "  4. Create some browsing history for realism"
}

Main
