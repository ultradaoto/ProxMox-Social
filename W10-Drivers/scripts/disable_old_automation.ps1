# Disable Old Automation Components on Windows 10
# 
# This script disables/stops the old automation system components
# that are no longer needed in the new architecture.
#
# Run with: PowerShell -ExecutionPolicy Bypass -File disable_old_automation.ps1

$ErrorActionPreference = "Continue"

Write-Host "=" * 70
Write-Host "Disabling Old Automation Components"
Write-Host "=" * 70
Write-Host ""

# =============================================================================
# Stop Running Processes
# =============================================================================

Write-Host "[1/6] Stopping Python automation processes..."

# Stop fetcher
$fetcher = Get-Process -Name "python*" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*fetcher.py*" }

if ($fetcher) {
    Write-Host "  → Stopping fetcher.py..."
    Stop-Process -Id $fetcher.Id -Force
    Write-Host "  ✓ Stopped"
} else {
    Write-Host "  - No fetcher process running"
}

# Stop poster
$poster = Get-Process -Name "python*" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*poster.py*" }

if ($poster) {
    Write-Host "  → Stopping poster.py..."
    Stop-Process -Id $poster.Id -Force
    Write-Host "  ✓ Stopped"
} else {
    Write-Host "  - No poster process running"
}

# Stop OSP GUI
$osp = Get-Process -Name "python*" -ErrorAction SilentlyContinue | 
    Where-Object { $_.CommandLine -like "*osp_gui.py*" }

if ($osp) {
    Write-Host "  → Stopping osp_gui.py..."
    Stop-Process -Id $osp.Id -Force
    Write-Host "  ✓ Stopped"
} else {
    Write-Host "  - No OSP GUI process running"
}

Write-Host ""

# =============================================================================
# Disable Scheduled Tasks
# =============================================================================

Write-Host "[2/6] Disabling scheduled tasks..."

$tasks = @("SocialWorkerFetcher", "SocialWorkerPoster", "OSPGuiLauncher")

foreach ($taskName in $tasks) {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($task) {
        Write-Host "  → Disabling task: $taskName"
        Disable-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        Write-Host "  ✓ Disabled"
    } else {
        Write-Host "  - Task not found: $taskName"
    }
}

Write-Host ""

# =============================================================================
# Disable Windows Services (if any)
# =============================================================================

Write-Host "[3/6] Disabling Windows services..."

$services = @("SocialWorker", "OSPGui")

foreach ($serviceName in $services) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    
    if ($service) {
        Write-Host "  → Stopping and disabling service: $serviceName"
        Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
        Set-Service -Name $serviceName -StartupType Disabled -ErrorAction SilentlyContinue
        Write-Host "  ✓ Disabled"
    } else {
        Write-Host "  - Service not found: $serviceName"
    }
}

Write-Host ""

# =============================================================================
# Disable Ollama (if installed)
# =============================================================================

Write-Host "[4/6] Disabling Ollama..."

$ollamaService = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue

if ($ollamaService) {
    Write-Host "  → Stopping Ollama service..."
    Stop-Service -Name "Ollama" -Force -ErrorAction SilentlyContinue
    
    Write-Host "  → Setting Ollama to disabled..."
    Set-Service -Name "Ollama" -StartupType Disabled -ErrorAction SilentlyContinue
    
    Write-Host "  ✓ Ollama disabled"
} else {
    Write-Host "  - Ollama service not found (may not be installed)"
}

Write-Host ""

# =============================================================================
# Disable Chrome Extension
# =============================================================================

Write-Host "[5/6] Chrome extension status..."
Write-Host "  → Extension cannot be disabled via script"
Write-Host "  → MANUAL ACTION REQUIRED:"
Write-Host "     1. Open Chrome"
Write-Host "     2. Go to chrome://extensions/"
Write-Host "     3. Find 'OSP' or 'On-Screen Prompter' extension"
Write-Host "     4. Toggle it OFF (but don't remove yet)"

Write-Host ""

# =============================================================================
# Remove from Startup
# =============================================================================

Write-Host "[6/6] Removing from startup..."

# Remove from current user startup
$startupPath = [Environment]::GetFolderPath("Startup")
$startupItems = @("SocialWorker.lnk", "OSPGui.lnk", "Fetcher.lnk")

foreach ($item in $startupItems) {
    $itemPath = Join-Path $startupPath $item
    if (Test-Path $itemPath) {
        Write-Host "  → Removing: $item"
        Remove-Item $itemPath -Force
        Write-Host "  ✓ Removed"
    }
}

# Check registry startup
$regPaths = @(
    "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
    "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
)

foreach ($regPath in $regPaths) {
    $regItems = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
    
    if ($regItems) {
        foreach ($prop in $regItems.PSObject.Properties) {
            if ($prop.Value -like "*SocialWorker*" -or 
                $prop.Value -like "*osp_gui*" -or 
                $prop.Value -like "*fetcher*") {
                
                Write-Host "  → Removing registry entry: $($prop.Name)"
                Remove-ItemProperty -Path $regPath -Name $prop.Name -ErrorAction SilentlyContinue
                Write-Host "  ✓ Removed"
            }
        }
    }
}

Write-Host ""

# =============================================================================
# Summary
# =============================================================================

Write-Host "=" * 70
Write-Host "AUTOMATION DISABLED SUCCESSFULLY"
Write-Host "=" * 70
Write-Host ""
Write-Host "What was disabled:"
Write-Host "  ✓ Python automation processes stopped"
Write-Host "  ✓ Scheduled tasks disabled"
Write-Host "  ✓ Windows services disabled"
Write-Host "  ✓ Ollama disabled (if installed)"
Write-Host "  ✓ Startup entries removed"
Write-Host ""
Write-Host "What to verify:"
Write-Host "  - Chrome extension disabled manually"
Write-Host "  - VNC server still running (should be ON)"
Write-Host "  - Chrome logged into social accounts"
Write-Host "  - C:\PostQueue\ folder structure intact"
Write-Host ""
Write-Host "The old code has NOT been deleted - see archive_old_code.ps1"
Write-Host ""
Write-Host "Run verify_cockpit_ready.ps1 to verify Windows 10 is ready"
Write-Host "=" * 70
