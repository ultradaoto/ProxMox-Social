# Social Worker - Windows Service Installation Script
# ==================================================
# Installs the Queue Fetcher and Social Poster as Windows services
#
# Prerequisites:
#   - Python 3.8+ installed
#   - NSSM (Non-Sucking Service Manager) installed via Chocolatey:
#     choco install nssm -y
#   - Playwright browsers installed:
#     playwright install chromium
#
# Usage:
#   .\install_services.ps1           # Install all services
#   .\install_services.ps1 -Uninstall # Remove services
#   .\install_services.ps1 -Status    # Check service status

param(
    [switch]$Uninstall,
    [switch]$Status,
    [switch]$Start,
    [switch]$Stop,
    [string]$WorkerDir = "C:\SocialWorker"
)

$ErrorActionPreference = "Stop"

# Configuration
$FETCHER_SERVICE = "SocialFetcher"
$POSTER_SERVICE = "SocialPoster"

# Colors for output
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }
function Write-Info { Write-Host $args -ForegroundColor Cyan }

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "This script must be run as Administrator!"
    exit 1
}

# Check NSSM is installed
function Test-NSSM {
    try {
        $null = Get-Command nssm -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

if (-not (Test-NSSM)) {
    Write-Error "NSSM not found. Install with: choco install nssm -y"
    exit 1
}

# Status check
if ($Status) {
    Write-Info "`n=== Social Worker Service Status ==="

    $services = @($FETCHER_SERVICE, $POSTER_SERVICE)
    foreach ($svc in $services) {
        $status = nssm status $svc 2>&1
        if ($status -match "SERVICE_RUNNING") {
            Write-Success "$svc : RUNNING"
        } elseif ($status -match "SERVICE_STOPPED") {
            Write-Warning "$svc : STOPPED"
        } else {
            Write-Warning "$svc : NOT INSTALLED"
        }
    }
    exit 0
}

# Stop services
if ($Stop) {
    Write-Info "Stopping services..."
    nssm stop $FETCHER_SERVICE 2>&1 | Out-Null
    nssm stop $POSTER_SERVICE 2>&1 | Out-Null
    Write-Success "Services stopped"
    exit 0
}

# Start services
if ($Start) {
    Write-Info "Starting services..."
    nssm start $FETCHER_SERVICE 2>&1 | Out-Null
    nssm start $POSTER_SERVICE 2>&1 | Out-Null
    Write-Success "Services started"
    exit 0
}

# Uninstall
if ($Uninstall) {
    Write-Info "Uninstalling Social Worker services..."

    # Stop and remove fetcher
    nssm stop $FETCHER_SERVICE 2>&1 | Out-Null
    nssm remove $FETCHER_SERVICE confirm 2>&1 | Out-Null
    Write-Success "Removed $FETCHER_SERVICE"

    # Stop and remove poster
    nssm stop $POSTER_SERVICE 2>&1 | Out-Null
    nssm remove $POSTER_SERVICE confirm 2>&1 | Out-Null
    Write-Success "Removed $POSTER_SERVICE"

    Write-Success "`nServices uninstalled successfully!"
    exit 0
}

# =============================================================================
# INSTALLATION
# =============================================================================

Write-Info @"

========================================
  SOCIAL WORKER SERVICE INSTALLATION
========================================

This will install the following services:
  - $FETCHER_SERVICE: Polls dashboard for new posts
  - $POSTER_SERVICE: Posts to social media platforms

Working Directory: $WorkerDir

"@

# Create working directory
if (-not (Test-Path $WorkerDir)) {
    Write-Info "Creating working directory: $WorkerDir"
    New-Item -ItemType Directory -Path $WorkerDir -Force | Out-Null
}

# Create subdirectories
$dirs = @("logs", "venv")
foreach ($dir in $dirs) {
    $path = Join-Path $WorkerDir $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}

# Create PostQueue directories
$queueDir = "C:\PostQueue"
$queueDirs = @("pending", "in_progress", "completed", "failed")
foreach ($dir in $queueDirs) {
    $path = Join-Path $queueDir $dir
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}
Write-Success "Created queue directories at $queueDir"

# Copy scripts to working directory
$sourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Copy-Item "$sourceDir\fetcher.py" "$WorkerDir\" -Force
Copy-Item "$sourceDir\poster.py" "$WorkerDir\" -Force
Copy-Item "$sourceDir\requirements.txt" "$WorkerDir\" -Force
if (Test-Path "$sourceDir\.env") {
    Copy-Item "$sourceDir\.env" "$WorkerDir\" -Force
} elseif (Test-Path "$sourceDir\.env.example") {
    Copy-Item "$sourceDir\.env.example" "$WorkerDir\.env" -Force
    Write-Warning "Copied .env.example to .env - please edit with your settings!"
}
Write-Success "Copied scripts to $WorkerDir"

# Create virtual environment
$venvPath = Join-Path $WorkerDir "venv"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Info "Creating Python virtual environment..."
    python -m venv $venvPath
    Write-Success "Created virtual environment"
}

# Install dependencies
Write-Info "Installing Python dependencies..."
& "$venvPath\Scripts\pip.exe" install --upgrade pip | Out-Null
& "$venvPath\Scripts\pip.exe" install -r "$WorkerDir\requirements.txt" | Out-Null
Write-Success "Installed dependencies"

# Install Playwright browsers
Write-Info "Installing Playwright browser (Chromium)..."
& "$venvPath\Scripts\playwright.exe" install chromium | Out-Null
Write-Success "Installed Playwright Chromium"

# Install Queue Fetcher service
Write-Info "Installing $FETCHER_SERVICE service..."

# Remove existing if present
nssm stop $FETCHER_SERVICE 2>&1 | Out-Null
nssm remove $FETCHER_SERVICE confirm 2>&1 | Out-Null

# Install
nssm install $FETCHER_SERVICE $pythonExe "$WorkerDir\fetcher.py"
nssm set $FETCHER_SERVICE AppDirectory $WorkerDir
nssm set $FETCHER_SERVICE AppStdout "$WorkerDir\logs\fetcher_stdout.log"
nssm set $FETCHER_SERVICE AppStderr "$WorkerDir\logs\fetcher_stderr.log"
nssm set $FETCHER_SERVICE AppRotateFiles 1
nssm set $FETCHER_SERVICE AppRotateBytes 10485760  # 10MB
nssm set $FETCHER_SERVICE Description "Fetches pending social media posts from dashboard"
nssm set $FETCHER_SERVICE Start SERVICE_AUTO_START
nssm set $FETCHER_SERVICE AppThrottle 30000  # 30 second restart delay

Write-Success "Installed $FETCHER_SERVICE"

# Install Social Poster service
# Note: Poster needs GUI access, so we configure it differently
Write-Info "Installing $POSTER_SERVICE service..."

# Remove existing if present
nssm stop $POSTER_SERVICE 2>&1 | Out-Null
nssm remove $POSTER_SERVICE confirm 2>&1 | Out-Null

# Install
nssm install $POSTER_SERVICE $pythonExe "$WorkerDir\poster.py"
nssm set $POSTER_SERVICE AppDirectory $WorkerDir
nssm set $POSTER_SERVICE AppStdout "$WorkerDir\logs\poster_stdout.log"
nssm set $POSTER_SERVICE AppStderr "$WorkerDir\logs\poster_stderr.log"
nssm set $POSTER_SERVICE AppRotateFiles 1
nssm set $POSTER_SERVICE AppRotateBytes 10485760
nssm set $POSTER_SERVICE Description "Posts content to social media platforms via browser automation"
nssm set $POSTER_SERVICE Start SERVICE_AUTO_START
nssm set $POSTER_SERVICE AppThrottle 30000

# Important: Poster needs to run as logged-in user for GUI access
# nssm set $POSTER_SERVICE ObjectName ".\YourUsername" "YourPassword"

Write-Success "Installed $POSTER_SERVICE"

# Summary
Write-Info @"

========================================
  INSTALLATION COMPLETE
========================================

Services installed:
  - $FETCHER_SERVICE
  - $POSTER_SERVICE

Configuration:
  Edit: $WorkerDir\.env

Before starting services:
  1. Edit .env with your API key and settings
  2. Log into social media accounts in browser first
  3. For poster GUI access, configure service to run as your user

Commands:
  Start:   .\install_services.ps1 -Start
  Stop:    .\install_services.ps1 -Stop
  Status:  .\install_services.ps1 -Status
  Remove:  .\install_services.ps1 -Uninstall

Manual start (for testing):
  cd $WorkerDir
  .\venv\Scripts\python.exe fetcher.py --once
  .\venv\Scripts\python.exe poster.py --test

"@

Write-Warning @"
IMPORTANT: The Social Poster service needs GUI access!

Option 1: Run as your user account (recommended for testing)
  - Open Services (services.msc)
  - Find 'SocialPoster', right-click Properties
  - Go to 'Log On' tab
  - Select 'This account' and enter your Windows credentials
  - Click OK and restart the service

Option 2: Run manually for now
  - Don't start the service
  - Run poster.py manually when you're logged in

"@
