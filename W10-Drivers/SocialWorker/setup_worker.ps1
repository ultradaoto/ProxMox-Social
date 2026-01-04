# Setup script for Social Worker
$ErrorActionPreference = "Stop"

Write-Host "Setting up Social Worker..." -ForegroundColor Cyan

# 1. Create Directories
$dirs = @(
    "C:\PostQueue",
    "C:\PostQueue\pending",
    "C:\PostQueue\in_progress",
    "C:\PostQueue\completed",
    "C:\PostQueue\failed",
    "C:\SocialWorker",
    "C:\SocialWorker\logs"
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created $dir"
    }
    else {
        Write-Host "$dir already exists"
    }
}

# 2. Copy Files
Write-Host "Copying files to C:\SocialWorker..."
$source = $PSScriptRoot
# Exclude venv and __pycache__ if running from a dev folder. We also only need fetcher related files now.
$filesToCopy = @("fetcher.py", "requirements.txt", ".env.example", "healthcheck.py", "install_dependencies.ps1", "install_services.ps1")
foreach ($file in $filesToCopy) {
    if (Test-Path "$source\$file") {
        Copy-Item -Path "$source\$file" -Destination "C:\SocialWorker" -Force
        Write-Host "Copied $file"
    }
}
# Also copy .env if it exists
if (Test-Path "$source\.env") {
    Copy-Item -Path "$source\.env" -Destination "C:\SocialWorker" -Force
    Write-Host "Copied .env"
}

Write-Host "Files copied."

# 3. Setup Python Environment
Set-Location "C:\SocialWorker"

if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv venv
}

Write-Host "Installing dependencies..."
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\pip.exe install -r requirements.txt

Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "Run '.\venv\Scripts\python.exe fetcher.py --health' to test."
