# realistic_settings.ps1 - Configure Realistic User Settings
#
# Makes the VM appear as a normally-used computer.
#
# Usage: Run as Administrator in PowerShell
#   .\realistic_settings.ps1

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

function Set-RealisticTimezone {
    Write-Log "Setting realistic timezone..."

    # Choose a common US timezone
    $timezones = @(
        "Eastern Standard Time",
        "Central Standard Time",
        "Pacific Standard Time",
        "Mountain Standard Time"
    )

    $selectedTz = $timezones | Get-Random
    Set-TimeZone -Id $selectedTz

    Write-Log "Timezone set to: $selectedTz"
}

function Set-RealisticLocale {
    Write-Log "Setting realistic locale..."

    Set-WinSystemLocale -SystemLocale en-US
    Set-WinHomeLocation -GeoId 244  # United States
    Set-WinUserLanguageList -LanguageList en-US -Force

    # Set date/time format
    Set-ItemProperty -Path "HKCU:\Control Panel\International" -Name "sShortDate" -Value "M/d/yyyy"
    Set-ItemProperty -Path "HKCU:\Control Panel\International" -Name "sLongDate" -Value "dddd, MMMM d, yyyy"

    Write-Log "Locale configured for US English"
}

function Configure-DisplaySettings {
    Write-Log "Configuring display settings..."

    $personalizePath = "HKCU:\Control Panel\Desktop"

    # Standard DPI (100%)
    Set-ItemProperty -Path $personalizePath -Name "LogPixels" -Value 96 -Type DWord

    # Disable font smoothing adjustments that might indicate VM
    Set-ItemProperty -Path $personalizePath -Name "FontSmoothing" -Value "2"
    Set-ItemProperty -Path $personalizePath -Name "FontSmoothingType" -Value 2 -Type DWord

    # Normal icon spacing
    Set-ItemProperty -Path $personalizePath -Name "IconSpacing" -Value "-1125"
    Set-ItemProperty -Path $personalizePath -Name "IconVerticalSpacing" -Value "-1125"

    Write-Log "Display settings configured"
}

function Configure-MouseSettings {
    Write-Log "Configuring mouse settings..."

    $mousePath = "HKCU:\Control Panel\Mouse"

    # Standard mouse settings
    Set-ItemProperty -Path $mousePath -Name "MouseSpeed" -Value "1"
    Set-ItemProperty -Path $mousePath -Name "MouseThreshold1" -Value "6"
    Set-ItemProperty -Path $mousePath -Name "MouseThreshold2" -Value "10"

    # Disable enhanced pointer precision (more natural for automation)
    Set-ItemProperty -Path $mousePath -Name "MouseSensitivity" -Value "10"

    # Standard double-click speed
    Set-ItemProperty -Path $mousePath -Name "DoubleClickSpeed" -Value "500"

    Write-Log "Mouse settings configured"
}

function Configure-KeyboardSettings {
    Write-Log "Configuring keyboard settings..."

    $keyboardPath = "HKCU:\Control Panel\Keyboard"

    # Standard keyboard repeat rate
    Set-ItemProperty -Path $keyboardPath -Name "KeyboardDelay" -Value "1"
    Set-ItemProperty -Path $keyboardPath -Name "KeyboardSpeed" -Value "31"

    Write-Log "Keyboard settings configured"
}

function Create-RecentFiles {
    Write-Log "Creating recent file history..."

    # Create some recent documents
    $documentsPath = "$env:USERPROFILE\Documents"

    $recentFiles = @(
        @{Name = "notes.txt"; Content = "Meeting notes from today"},
        @{Name = "todo.txt"; Content = "Tasks to complete this week"},
        @{Name = "ideas.txt"; Content = "Project ideas and thoughts"}
    )

    foreach ($file in $recentFiles) {
        $filePath = Join-Path $documentsPath $file.Name
        Set-Content -Path $filePath -Value $file.Content -Force
        # Touch file to update timestamp
        (Get-Item $filePath).LastWriteTime = (Get-Date).AddDays(-(Get-Random -Minimum 1 -Maximum 7))
    }

    Write-Log "Recent files created"
}

function Configure-ExplorerSettings {
    Write-Log "Configuring Explorer settings..."

    $explorerPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Advanced"

    # Show file extensions (common for power users)
    Set-ItemProperty -Path $explorerPath -Name "HideFileExt" -Value 0 -Type DWord

    # Show hidden files (optional)
    Set-ItemProperty -Path $explorerPath -Name "Hidden" -Value 1 -Type DWord

    # Quick access (default)
    Set-ItemProperty -Path $explorerPath -Name "LaunchTo" -Value 2 -Type DWord

    Write-Log "Explorer settings configured"
}

function Configure-NotificationSettings {
    Write-Log "Configuring notification settings..."

    $notifPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings"

    # Reduce notification popups
    if (-not (Test-Path $notifPath)) {
        New-Item -Path $notifPath -Force | Out-Null
    }

    # Disable focus assist during fullscreen
    $focusPath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\CloudStore\Store\DefaultAccount\Current\default`$windows.data.shell.focusassist"

    Write-Log "Notification settings configured"
}

function Set-WallpaperAndColors {
    Write-Log "Setting wallpaper and colors..."

    # Use default Windows wallpaper (most realistic)
    $wallpaperPath = "C:\Windows\Web\Wallpaper\Windows\img0.jpg"

    if (Test-Path $wallpaperPath) {
        $desktopPath = "HKCU:\Control Panel\Desktop"
        Set-ItemProperty -Path $desktopPath -Name "Wallpaper" -Value $wallpaperPath

        # Apply
        rundll32.exe user32.dll, UpdatePerUserSystemParameters, 0, $true
    }

    # Use default accent color
    $themePath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    if (-not (Test-Path $themePath)) {
        New-Item -Path $themePath -Force | Out-Null
    }

    # Light theme (most common)
    Set-ItemProperty -Path $themePath -Name "AppsUseLightTheme" -Value 1 -Type DWord
    Set-ItemProperty -Path $themePath -Name "SystemUsesLightTheme" -Value 1 -Type DWord

    Write-Log "Wallpaper and colors configured"
}

function Configure-SoundSettings {
    Write-Log "Configuring sound settings..."

    # Standard Windows sounds
    $soundPath = "HKCU:\AppEvents\Schemes"
    Set-ItemProperty -Path $soundPath -Name "(Default)" -Value ".Default"

    Write-Log "Sound settings configured"
}

function Disable-GameMode {
    Write-Log "Disabling Game Mode (can interfere with input)..."

    $gamePath = "HKCU:\SOFTWARE\Microsoft\GameBar"

    if (-not (Test-Path $gamePath)) {
        New-Item -Path $gamePath -Force | Out-Null
    }

    Set-ItemProperty -Path $gamePath -Name "AllowAutoGameMode" -Value 0 -Type DWord
    Set-ItemProperty -Path $gamePath -Name "AutoGameModeEnabled" -Value 0 -Type DWord

    # Disable Game DVR
    $gameDvrPath = "HKCU:\System\GameConfigStore"
    Set-ItemProperty -Path $gameDvrPath -Name "GameDVR_Enabled" -Value 0 -Type DWord -ErrorAction SilentlyContinue

    Write-Log "Game Mode disabled"
}

# Main execution
function Main {
    Write-Log "Realistic Settings Configuration Script"
    Write-Log "========================================"

    Set-RealisticTimezone
    Set-RealisticLocale
    Configure-DisplaySettings
    Configure-MouseSettings
    Configure-KeyboardSettings
    Create-RecentFiles
    Configure-ExplorerSettings
    Configure-NotificationSettings
    Set-WallpaperAndColors
    Configure-SoundSettings
    Disable-GameMode

    Write-Log ""
    Write-Log "========================================"
    Write-Log "Realistic settings configured!"
    Write-Log ""
    Write-Log "The VM should now appear as a normal user environment."
}

Main
