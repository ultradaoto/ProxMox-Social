$ErrorActionPreference = "SilentlyContinue"

Write-Host "Configuring Chrome for 'Human' Appearance..."

# 1. Locate Chrome
$chromePath = "$env:ProgramFiles\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chromePath)) {
    $chromePath = "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
}

if (-not (Test-Path $chromePath)) {
    Write-Warning "Chrome executable not found. Please install Google Chrome first."
    Exit
}
else {
    Write-Host "Found Chrome at $chromePath"
}

# 2. Update Shortcuts (Desktop and Start Menu)
$WshShell = New-Object -comObject WScript.Shell
$shortcuts = @(
    "$env:PUBLIC\Desktop\Google Chrome.lnk",
    "$env:USERPROFILE\Desktop\Google Chrome.lnk",
    "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Google Chrome.lnk",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Google Chrome.lnk"
)

$args = "--disable-blink-features=AutomationControlled --disable-features=IsolateOrigins,site-per-process"

foreach ($linkPath in $shortcuts) {
    if (Test-Path $linkPath) {
        Write-Host "Updating shortcut: $linkPath"
        $shortcut = $WshShell.CreateShortcut($linkPath)
        # Append flags if not present
        if ($shortcut.Arguments -notlike "*$args*") {
            $shortcut.Arguments = "$($shortcut.Arguments) $args"
            $shortcut.Save()
            Write-Host "  -> Added anti-automation flags."
        }
        else {
            Write-Host "  -> Flags already present."
        }
    }
}

# 3. Launch Chrome for Extension Installation
Write-Host "`nLaunching Chrome to install extensions..."
Write-Host "Please manually install the following extensions from the tabs that open:"
Write-Host "1. uBlock Origin"
Write-Host "2. Privacy Badger"
Write-Host "3. Random User-Agent (Spoofer)"

$extensions = @(
    "https://chromewebstore.google.com/detail/ublock-origin/cjpalhdlnbpafiamejdnhcphjbkeiagm",
    "https://chromewebstore.google.com/detail/privacy-badger/pkehgijcmpdhfbdbbnkijodmdjhbjlgp",
    "https://chromewebstore.google.com/detail/random-user-agent-switcher/einpaelgookohagofgnnkcfjbkkgepnp" # Example
)

# Open tabs
Start-Process $chromePath -ArgumentList $extensions

Write-Host "`n[+] Chrome Configuration Script Completed."
Write-Host "Note: To verify flags, go to chrome://version/ and look at 'Command Line'."
