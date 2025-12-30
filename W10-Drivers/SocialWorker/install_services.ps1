$ErrorActionPreference = "Stop"

# Configuration
${FETCHER_SERVICE} = "SocialFetcher"
${WorkerDir} = "C:\SocialWorker"

function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }

# Check Admin
if (-NOT ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "ERROR: This script requires Administrator privileges."
    Exit 1
}

Write-Info "=== Social Worker Installation (Fetcher Only) ==="
Write-Warning "NOTE: Playwright/Poster is EXCLUDED to avoid detection."

# 1. Setup Directories
if (-not (Test-Path ${WorkerDir})) { New-Item -ItemType Directory -Path ${WorkerDir} -Force | Out-Null }
$dirs = @("logs", "venv")
foreach ($d in $dirs) { 
    $p = Join-Path ${WorkerDir} $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
}

# 2. Setup Queue Dirs
$queueDir = "C:\PostQueue"
$queueDirs = @("pending", "in_progress", "completed", "failed")
foreach ($d in $queueDirs) {
    if (-not (Test-Path "$queueDir\$d")) { New-Item -ItemType Directory -Path "$queueDir\$d" -Force | Out-Null }
}
Write-Success "Queue directories ready."

# 3. Copy Scripts (Only Fetcher components)
$sourceDir = "C:\ProxMox-Social\W10-Drivers\SocialWorker"
Copy-Item "$sourceDir\fetcher.py" "${WorkerDir}\" -Force
if (Test-Path "$sourceDir\requirements.txt") {
    # Filter out playwright and asyncio-compat from requirements
    Get-Content "$sourceDir\requirements.txt" | Where-Object { $_ -notmatch "playwright" -and $_ -notmatch "asyncio-compat" } | Set-Content "${WorkerDir}\requirements.txt"
}
if ((Test-Path "$sourceDir\.env.example") -and (-not (Test-Path "${WorkerDir}\.env"))) {
    Copy-Item "$sourceDir\.env.example" "${WorkerDir}\.env"
}
Write-Success "Copied scripts (fetcher only)."

# 4. Setup Python Venv
$venvPath = "${WorkerDir}\venv"
$pythonExe = "${venvPath}\Scripts\python.exe"

# Helper to find system python
function Get-SystemPython {
    if (Get-Command python -ErrorAction SilentlyContinue) { return "python" }
    $paths = @("C:\ProgramData\chocolatey\bin\python.exe", "C:\Python314\python.exe", "C:\Python313\python.exe")
    foreach ($p in $paths) { if (Test-Path $p) { return $p } }
    throw "Python not found!"
}

if (-not (Test-Path $pythonExe)) {
    $sysPy = Get-SystemPython
    Write-Info "Creating virtual environment..."
    & $sysPy -m venv $venvPath
}
Write-Success "Virtual environment ready."

# 5. Install Dependencies (No Playwright)
Write-Info "Installing dependencies (without Playwright)..."
$oldPref = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& "$venvPath\Scripts\pip.exe" install -r "${WorkerDir}\requirements.txt" --upgrade --no-warn-script-location 2>&1 | Out-Null
$ErrorActionPreference = $oldPref
Write-Success "Dependencies installed."

# 6. Install Service using NSSM
Write-Info "Installing ${FETCHER_SERVICE} service..."
$oldPref = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
nssm stop ${FETCHER_SERVICE} 2>&1 | Out-Null
nssm remove ${FETCHER_SERVICE} confirm 2>&1 | Out-Null
$ErrorActionPreference = $oldPref

nssm install ${FETCHER_SERVICE} $pythonExe "${WorkerDir}\fetcher.py"
nssm set ${FETCHER_SERVICE} AppDirectory ${WorkerDir}
nssm set ${FETCHER_SERVICE} AppStdout "${WorkerDir}\logs\fetcher_stdout.log"
nssm set ${FETCHER_SERVICE} AppStderr "${WorkerDir}\logs\fetcher_stderr.log"
nssm set ${FETCHER_SERVICE} Start SERVICE_AUTO_START

Write-Success "`n=== Installation Complete ==="
Write-Info "Service installed: ${FETCHER_SERVICE}"
Write-Warning "IMPORTANT: Edit C:\SocialWorker\.env with your API key before starting the service."
Write-Info "To start: nssm start ${FETCHER_SERVICE}"
Write-Info "To check: nssm status ${FETCHER_SERVICE}"
