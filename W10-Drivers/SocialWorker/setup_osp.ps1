# OSP Setup Script

Write-Host "Setting up One-Click Social Poster (OSP)..." -ForegroundColor Cyan

# 1. Verify Directory Structure
$QueueDir = "C:\PostQueue"
$Dirs = @("pending", "completed", "failed")

if (!(Test-Path $QueueDir)) {
    New-Item -ItemType Directory -Force -Path $QueueDir | Out-Null
    Write-Host "Created $QueueDir" -ForegroundColor Green
}

foreach ($d in $Dirs) {
    $path = "$QueueDir\$d"
    if (!(Test-Path $path)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        Write-Host "Created $path" -ForegroundColor Green
    }
}

# 2. Enforce 1600x1200 Resolution
Write-Host "Enforcing 1600x1200 Resolution..." -ForegroundColor Yellow
$ResScript = Join-Path "$PSScriptRoot\..\scripts" "set_resolution.ps1"
if (Test-Path $ResScript) {
    # Run immediately
    & powershell -ExecutionPolicy Bypass -File $ResScript
    
    # Create Startup Shortcut for persistence
    $StartupDir = [Environment]::GetFolderPath("Startup")
    $ResShortcutPath = "$StartupDir\SetRes1600x1200.lnk"
    
    $WshShell = New-Object -comObject WScript.Shell
    $ResShortcut = $WshShell.CreateShortcut($ResShortcutPath)
    $ResShortcut.TargetPath = "powershell.exe"
    $ResShortcut.Arguments = "-ExecutionPolicy Bypass -WindowStyle Hidden -File ""$ResScript"""
    $ResShortcut.Description = "Enforce 1600x1200 Resolution for VNC"
    $ResShortcut.Save()
    Write-Host "Added Resolution Enforcer to Startup: $ResShortcutPath" -ForegroundColor Green
}
else {
    Write-Warning "set_resolution.ps1 not found at $ResScript"
}

# 3. Install Python Requirements
Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
$PipCmd = "pip"
if (Get-Command "pip3" -ErrorAction SilentlyContinue) {
    $PipCmd = "pip3"
}

# Install from requirements.txt in the same directory as script
$ReqFile = Join-Path $PSScriptRoot "requirements.txt"
if (Test-Path $ReqFile) {
    & $PipCmd install -r $ReqFile
}
else {
    Write-Host "requirements.txt not found! Installing manual deps..." -ForegroundColor Red
    & $PipCmd install PyQt6 requests Pillow pyperclip pygetwindow pywin32 schedule python-dotenv
}

# 3. Create Desktop Shortcut
$WshShell = New-Object -comObject WScript.Shell
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = "$DesktopPath\OSP GUI.lnk"
$Target = Join-Path $PSScriptRoot "osp_gui.py"
$PythonPath = (Get-Command python).Source

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonPath
$Shortcut.Arguments = """$Target"""
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.IconLocation = "$PSScriptRoot\osp_icon.ico" # Optional
$Shortcut.Description = "One-Click Social Poster"
$Shortcut.Save()

Write-Host "Access created: $ShortcutPath" -ForegroundColor Green
Write-Host "Setup Complete! You can now launch 'OSP GUI' from your desktop." -ForegroundColor Cyan
