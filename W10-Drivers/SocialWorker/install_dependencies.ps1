$ErrorActionPreference = "Stop"

function Write-Step { Write-Host "`n=== $args ===" -ForegroundColor Cyan }

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "ERROR: This script requires Administrator privileges."
    Exit 1
}

# 1. Install Chocolatey
Write-Step "Checking Chocolatey"
if (-not (Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..."
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Reload env vars
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "Chocolatey already installed."
}

# 2. Install Python
Write-Step "Installing Python 3"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    choco install python -y
    # Reload env vars to get python on path immediately
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "Python already installed."
}

# 3. Install NSSM
Write-Step "Installing NSSM"
if (-not (Get-Command nssm -ErrorAction SilentlyContinue)) {
    choco install nssm -y
} else {
    Write-Host "NSSM already installed."
}

# 4. Install Playwright (Browsers) - Pre-req for Poster
Write-Step "Pre-installing Playwright Browsers"
# We need pip first
if (Get-Command pip -ErrorAction SilentlyContinue) {
    pip install playwright
    playwright install chromium
}

Write-Step "Installation Complete"
python --version
nssm --version
