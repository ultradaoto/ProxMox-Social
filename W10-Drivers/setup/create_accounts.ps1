# create_accounts.ps1 - Create and Configure User Accounts
#
# Sets up user accounts with realistic profiles.
#
# Usage: Run as Administrator in PowerShell
#   .\create_accounts.ps1

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

function Create-MainUser {
    param(
        [string]$Username = "User",
        [string]$Password = "Password123!",
        [string]$FullName = "John Smith"
    )

    Write-Log "Creating main user account..."

    $existingUser = Get-LocalUser -Name $Username -ErrorAction SilentlyContinue

    if ($existingUser) {
        Write-Log "User '$Username' already exists"
        return
    }

    $securePass = ConvertTo-SecureString $Password -AsPlainText -Force
    New-LocalUser -Name $Username -Password $securePass -FullName $FullName -Description "Main user account" | Out-Null
    Add-LocalGroupMember -Group "Users" -Member $Username

    # Enable auto-login for this user
    $regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
    Set-ItemProperty -Path $regPath -Name "AutoAdminLogon" -Value "1"
    Set-ItemProperty -Path $regPath -Name "DefaultUserName" -Value $Username
    Set-ItemProperty -Path $regPath -Name "DefaultPassword" -Value $Password

    Write-Log "Main user created: $Username"
    Write-Log "Auto-login enabled for $Username"
}

function Create-UserProfile {
    param([string]$Username)

    Write-Log "Creating user profile structure..."

    # User profile base path
    $profilePath = "C:\Users\$Username"

    # Common directories
    $directories = @(
        "$profilePath\Documents",
        "$profilePath\Downloads",
        "$profilePath\Pictures",
        "$profilePath\Desktop",
        "$profilePath\Videos"
    )

    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }

    # Create some dummy files for realism
    $dummyFiles = @{
        "$profilePath\Documents\notes.txt" = "Personal notes file"
        "$profilePath\Documents\todo.txt" = "Tasks to complete"
        "$profilePath\Desktop\shortcuts.txt" = "Useful links"
    }

    foreach ($file in $dummyFiles.Keys) {
        Set-Content -Path $file -Value $dummyFiles[$file] -Force
    }

    Write-Log "User profile structure created"
}

function Configure-UserPreferences {
    param([string]$Username)

    Write-Log "Configuring user preferences..."

    # These settings require the user to be logged in
    # We'll create registry entries that apply on login

    $ntUserPath = "HKU:\.DEFAULT"

    # Disable lock screen
    $personalizePath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Personalization"
    if (-not (Test-Path $personalizePath)) {
        New-Item -Path $personalizePath -Force | Out-Null
    }
    Set-ItemProperty -Path $personalizePath -Name "NoLockScreen" -Value 1 -Type DWord

    # Disable screensaver
    $desktopPath = "HKCU:\Control Panel\Desktop"
    Set-ItemProperty -Path $desktopPath -Name "ScreenSaveActive" -Value "0" -ErrorAction SilentlyContinue

    Write-Log "User preferences configured"
}

function Set-WallpaperAndTheme {
    Write-Log "Setting wallpaper and theme..."

    # Use a default Windows wallpaper (more realistic than custom)
    $wallpaperPath = "C:\Windows\Web\Wallpaper\Windows\img0.jpg"

    if (Test-Path $wallpaperPath) {
        $regPath = "HKCU:\Control Panel\Desktop"
        Set-ItemProperty -Path $regPath -Name "Wallpaper" -Value $wallpaperPath -ErrorAction SilentlyContinue

        # Apply wallpaper
        rundll32.exe user32.dll, UpdatePerUserSystemParameters
    }

    # Set to light theme (default, more common)
    $themePath = "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    if (-not (Test-Path $themePath)) {
        New-Item -Path $themePath -Force | Out-Null
    }
    Set-ItemProperty -Path $themePath -Name "AppsUseLightTheme" -Value 1 -Type DWord -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $themePath -Name "SystemUsesLightTheme" -Value 1 -Type DWord -ErrorAction SilentlyContinue

    Write-Log "Theme configured"
}

function Create-StartMenuShortcuts {
    Write-Log "Creating Start Menu shortcuts..."

    $startMenuPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"

    # Create a folder for commonly used apps
    $customFolder = "$startMenuPath\Favorites"
    if (-not (Test-Path $customFolder)) {
        New-Item -ItemType Directory -Path $customFolder -Force | Out-Null
    }

    Write-Log "Start Menu configured"
}

function Configure-TaskbarPins {
    Write-Log "Configuring taskbar..."

    # Note: Taskbar pins require user to be logged in
    # This provides guidance for manual configuration

    Write-Log "Taskbar pins should be configured manually:" "WARN"
    Write-Log "  - Pin Chrome to taskbar" "WARN"
    Write-Log "  - Pin File Explorer to taskbar" "WARN"
    Write-Log "  - Remove unnecessary icons" "WARN"
}

# Main execution
function Main {
    Write-Log "User Account Setup Script"
    Write-Log "========================="

    $username = "User"
    $password = "Password123!"  # CHANGE THIS!
    $fullName = "John Smith"

    Create-MainUser -Username $username -Password $password -FullName $fullName
    Create-UserProfile -Username $username
    Configure-UserPreferences -Username $username
    Set-WallpaperAndTheme
    Create-StartMenuShortcuts
    Configure-TaskbarPins

    Write-Log ""
    Write-Log "========================="
    Write-Log "Account Setup Complete!"
    Write-Log ""
    Write-Log "Main user account:"
    Write-Log "  Username: $username"
    Write-Log "  Password: $password"
    Write-Log ""
    Write-Log "IMPORTANT: Change the password for production use!"
    Write-Log ""
    Write-Log "Auto-login is enabled. Restart to verify."
}

Main
