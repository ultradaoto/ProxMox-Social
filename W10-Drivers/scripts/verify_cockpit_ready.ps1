# Verify Windows 10 Cockpit is Ready
#
# Checks that Windows 10 is properly configured as a passive cockpit
# for Ubuntu-based automation.
#
# Run with: PowerShell -ExecutionPolicy Bypass -File verify_cockpit_ready.ps1

$ErrorActionPreference = "Continue"

Write-Host "=" * 70
Write-Host "Windows 10 Cockpit Readiness Check"
Write-Host "=" * 70
Write-Host ""

$checks = @{
    passed = 0
    failed = 0
    warnings = 0
}

function Test-Check {
    param(
        [string]$Name,
        [bool]$Result,
        [string]$FailMessage = "",
        [bool]$IsWarning = $false
    )
    
    if ($Result) {
        Write-Host "  ✓ $Name" -ForegroundColor Green
        $script:checks.passed++
    } else {
        if ($IsWarning) {
            Write-Host "  ⚠ $Name" -ForegroundColor Yellow
            if ($FailMessage) {
                Write-Host "    └─ $FailMessage" -ForegroundColor Yellow
            }
            $script:checks.warnings++
        } else {
            Write-Host "  ✗ $Name" -ForegroundColor Red
            if ($FailMessage) {
                Write-Host "    └─ $FailMessage" -ForegroundColor Red
            }
            $script:checks.failed++
        }
    }
}

# =============================================================================
# Check 1: VNC Server Running
# =============================================================================

Write-Host "[1/8] VNC Server Status..."

$vncService = Get-Service -Name "*vnc*" -ErrorAction SilentlyContinue | 
    Where-Object { $_.Status -eq "Running" } | 
    Select-Object -First 1

if ($vncService) {
    Test-Check "VNC service is running ($($vncService.Name))" $true
} else {
    Test-Check "VNC service is running" $false "No VNC service found running"
}

# Check VNC port listening
$vncPort = Get-NetTCPConnection -LocalPort 5900 -ErrorAction SilentlyContinue

if ($vncPort) {
    Test-Check "VNC port 5900 is listening" $true
} else {
    Test-Check "VNC port 5900 is listening" $false "Port 5900 not open" $true
}

Write-Host ""

# =============================================================================
# Check 2: Old Automation Disabled
# =============================================================================

Write-Host "[2/8] Old Automation Status..."

# Check for running processes
$oldProcesses = Get-Process -Name "python*" -ErrorAction SilentlyContinue | 
    Where-Object { 
        $_.CommandLine -like "*fetcher.py*" -or 
        $_.CommandLine -like "*poster.py*" -or 
        $_.CommandLine -like "*osp_gui.py*" 
    }

Test-Check "No old automation processes running" ($oldProcesses.Count -eq 0)

# Check Ollama
$ollama = Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
if ($ollama) {
    $ollamaDisabled = ($ollama.StartType -eq "Disabled" -and $ollama.Status -ne "Running")
    Test-Check "Ollama is disabled" $ollamaDisabled "" $true
}

Write-Host ""

# =============================================================================
# Check 3: PostQueue Folder Structure
# =============================================================================

Write-Host "[3/8] PostQueue Directory Structure..."

$queueBase = "C:\PostQueue"

Test-Check "C:\PostQueue exists" (Test-Path $queueBase) "Create with: mkdir C:\PostQueue"
Test-Check "C:\PostQueue\pending exists" (Test-Path "$queueBase\pending") "Create with: mkdir C:\PostQueue\pending"
Test-Check "C:\PostQueue\processing exists" (Test-Path "$queueBase\processing") "Create with: mkdir C:\PostQueue\processing" $true
Test-Check "C:\PostQueue\completed exists" (Test-Path "$queueBase\completed") "Create with: mkdir C:\PostQueue\completed" $true

Write-Host ""

# =============================================================================
# Check 4: Chrome Browser
# =============================================================================

Write-Host "[4/8] Chrome Browser..."

$chromeProcess = Get-Process -Name "chrome" -ErrorAction SilentlyContinue

if ($chromeProcess) {
    Test-Check "Chrome is running" $true
} else {
    Test-Check "Chrome is running" $false "Chrome should be running with accounts logged in" $true
}

$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
if (!(Test-Path $chromePath)) {
    $chromePath = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
}

Test-Check "Chrome is installed" (Test-Path $chromePath) "Install Chrome from https://www.google.com/chrome/"

Write-Host ""

# =============================================================================
# Check 5: Network Configuration
# =============================================================================

Write-Host "[5/8] Network Configuration..."

# Check IP address (should be on 192.168.100.x network)
$ipConfig = Get-NetIPAddress -AddressFamily IPv4 | 
    Where-Object { $_.IPAddress -like "192.168.100.*" } |
    Select-Object -First 1

if ($ipConfig) {
    Test-Check "IP on vmbr1 network (192.168.100.x)" $true
    Write-Host "    └─ IP: $($ipConfig.IPAddress)" -ForegroundColor Gray
} else {
    Test-Check "IP on vmbr1 network (192.168.100.x)" $false "Check Proxmox VM network config" $true
}

# Test connectivity to Proxmox host
$proxmoxReachable = Test-Connection -ComputerName "192.168.100.1" -Count 1 -Quiet -ErrorAction SilentlyContinue

Test-Check "Can reach Proxmox host (192.168.100.1)" $proxmoxReachable "Check network configuration" $true

Write-Host ""

# =============================================================================
# Check 6: Disk Space
# =============================================================================

Write-Host "[6/8] Disk Space..."

$drive = Get-PSDrive -Name C -ErrorAction SilentlyContinue

if ($drive) {
    $freeGB = [math]::Round($drive.Free / 1GB, 2)
    $totalGB = [math]::Round(($drive.Used + $drive.Free) / 1GB, 2)
    $percentFree = [math]::Round(($drive.Free / ($drive.Used + $drive.Free)) * 100, 1)
    
    Test-Check "Disk space available: ${freeGB}GB / ${totalGB}GB (${percentFree}%)" ($freeGB -gt 5)
    
    if ($freeGB -lt 5) {
        Write-Host "    └─ Clean up PostQueue completed files" -ForegroundColor Yellow
    }
}

Write-Host ""

# =============================================================================
# Check 7: Required Services NOT Running
# =============================================================================

Write-Host "[7/8] Services That Should NOT Be Running..."

$badServices = @("SocialWorker", "OSPGui", "Ollama")

foreach ($serviceName in $badServices) {
    $service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
    
    if ($service) {
        $notRunning = ($service.Status -ne "Running")
        Test-Check "$serviceName is stopped" $notRunning "Run disable_old_automation.ps1"
    }
}

Write-Host ""

# =============================================================================
# Check 8: Manual Checks Required
# =============================================================================

Write-Host "[8/8] Manual Verification Required..."

Write-Host ""
Write-Host "  Please verify manually:"
Write-Host "    □ Chrome extension OSP is disabled (chrome://extensions/)"
Write-Host "    □ Social accounts are logged in:"
Write-Host "        - Instagram (instagram.com)"
Write-Host "        - Facebook (facebook.com)"
Write-Host "        - TikTok (tiktok.com)"
Write-Host "        - Skool (skool.com)"
Write-Host "    □ Sessions set to 'Remember me' / stay logged in"
Write-Host ""

# =============================================================================
# Summary
# =============================================================================

$total = $checks.passed + $checks.failed + $checks.warnings

Write-Host "=" * 70
Write-Host "VERIFICATION SUMMARY"
Write-Host "=" * 70
Write-Host ""
Write-Host "  Passed:   $($checks.passed)/$total" -ForegroundColor Green
Write-Host "  Failed:   $($checks.failed)/$total" -ForegroundColor $(if ($checks.failed -gt 0) { "Red" } else { "Gray" })
Write-Host "  Warnings: $($checks.warnings)/$total" -ForegroundColor $(if ($checks.warnings -gt 0) { "Yellow" } else { "Gray" })
Write-Host ""

if ($checks.failed -eq 0) {
    Write-Host "✓ Windows 10 cockpit is READY for Ubuntu automation!" -ForegroundColor Green
} else {
    Write-Host "✗ Windows 10 cockpit has issues that need fixing" -ForegroundColor Red
    Write-Host "  Fix the failed checks above and run this script again" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 70

# Return exit code
if ($checks.failed -eq 0) {
    exit 0
} else {
    exit 1
}
