# Setup OSP Simplified Auto-Start
# This script creates a startup shortcut for the simplified OSP

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Simplified OSP Auto-Start Setup" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Get the current script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$OSPPath = Join-Path $ScriptDir "osp_simple.py"

# Verify osp_simple.py exists
if (-not (Test-Path $OSPPath)) {
    Write-Host "ERROR: osp_simple.py not found at $OSPPath" -ForegroundColor Red
    Write-Host "Please ensure osp_simple.py is in the same directory as this script." -ForegroundColor Yellow
    exit 1
}

Write-Host "[1/4] Found osp_simple.py" -ForegroundColor Green

# Find Python executable
$PythonExe = $null
$PythonPaths = @(
    "pythonw.exe",
    "python.exe",
    "C:\Python310\pythonw.exe",
    "C:\Python311\pythonw.exe",
    "C:\Python312\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\pythonw.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
)

foreach ($path in $PythonPaths) {
    if (Get-Command $path -ErrorAction SilentlyContinue) {
        $PythonExe = $path
        break
    }
}

if (-not $PythonExe) {
    Write-Host "ERROR: Python not found" -ForegroundColor Red
    Write-Host "Please install Python 3.10 or later" -ForegroundColor Yellow
    exit 1
}

Write-Host "[2/4] Found Python at: $PythonExe" -ForegroundColor Green

# Verify dependencies
Write-Host "[3/4] Checking dependencies..." -ForegroundColor Yellow
$RequiredModules = @("tkinter", "pyperclip", "requests", "PIL")
$MissingModules = @()

foreach ($module in $RequiredModules) {
    $TestCmd = "import $module"
    $result = & python -c $TestCmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        $MissingModules += $module
    }
}

if ($MissingModules.Count -gt 0) {
    Write-Host "Missing modules: $($MissingModules -join ', ')" -ForegroundColor Red
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    
    $RequirementsPath = Join-Path $ScriptDir "requirements_osp_simple.txt"
    if (Test-Path $RequirementsPath) {
        & pip install -r $RequirementsPath
        if ($LASTEXITCODE -ne 0) {
            Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "ERROR: requirements_osp_simple.txt not found" -ForegroundColor Red
        exit 1
    }
}

Write-Host "[3/4] All dependencies installed" -ForegroundColor Green

# Create startup shortcut
$StartupFolder = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $StartupFolder "OSP_Simple.lnk"

Write-Host "[4/4] Creating startup shortcut..." -ForegroundColor Yellow

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonExe
$Shortcut.Arguments = "`"$OSPPath`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.Description = "Simplified On-Screen Prompter for Social Media Posting"
$Shortcut.IconLocation = "pythonw.exe,0"
$Shortcut.Save()

Write-Host "[4/4] Shortcut created at: $ShortcutPath" -ForegroundColor Green

# Create PostQueue directory
$PostQueueDir = "C:\PostQueue"
if (-not (Test-Path $PostQueueDir)) {
    New-Item -ItemType Directory -Path $PostQueueDir -Force | Out-Null
    Write-Host "Created PostQueue directory at C:\PostQueue" -ForegroundColor Green
}

Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The OSP will automatically start on next Windows login." -ForegroundColor Green
Write-Host ""
Write-Host "To start it now, run:" -ForegroundColor Yellow
Write-Host "  python osp_simple.py" -ForegroundColor White
Write-Host ""
Write-Host "To remove auto-start, delete:" -ForegroundColor Yellow
Write-Host "  $ShortcutPath" -ForegroundColor White
Write-Host ""
