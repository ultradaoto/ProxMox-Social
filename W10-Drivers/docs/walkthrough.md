# Windows 10 "ProxyMox" Setup Walkthrough

I have successfully configured your Windows 10 environment to match the **VM2** specifications.

## Completed Actions
### 1. Drivers
- **VirtIO Drivers**: Installed from `E:\virtio-win-guest-tools.exe`.

### 2. System Configuration
- **Windows Updates**: Service `wuauserv` disabled.
- **Telemetry**: Disabled via Registry.
- **Security**: SmartScreen and Game Mode disabled.
- **RDP**: Enabled and secured with NLA.
- **Firewall**: Rules added for VNC (5900) and RDP.

### 3. Software
- **TightVNC Server**: Installed and running on port 5900.
- **Chrome**: Shortcuts updated with anti-automation flags. Extension installation pages opened.

## Verification Check
You can verify the setup by checking:
1.  **VNC**: `Get-Service tvnserver` (Should be Running).
2.  **Chrome**: Open via Desktop shortcut -> `chrome://version` -> Look for `--disable-blink-features=AutomationControlled` in Command Line.
3.  **Drivers**: Device Manager should show no missing drivers (if VirtIO matches your hardware/VM).

## Scripts
You can re-run these scripts at any time:
- `setup_all.ps1`: Re-applies System Config, Drivers, and VNC.
- `config_chrome.ps1`: Re-applies Chrome shortcuts and opens extension pages.
