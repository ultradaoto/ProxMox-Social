# Fresh Windows 10 Installation Checklist

## Pre-Installation

### Proxmox VM Configuration

- [ ] VM created with appropriate resources (4+ cores, 8+ GB RAM)
- [ ] VirtIO drivers ISO attached as second CD/DVD
- [ ] SMBIOS settings configured for realistic hardware identity
- [ ] Network bridge configured (vmbr1 for internal network)
- [ ] CPU type set appropriately (host or specific model)
- [ ] Machine type set (q35 recommended)

### Resources Prepared

- [ ] Windows 10 ISO available
- [ ] VirtIO drivers ISO available
- [ ] TightVNC installer downloaded
- [ ] Chrome installer downloaded
- [ ] All PowerShell scripts copied to accessible location

## Phase 1: Windows Installation

### Installation Steps

- [ ] Boot from Windows 10 ISO
- [ ] Select "Custom: Install Windows only"
- [ ] Load VirtIO storage drivers (vioscsi)
- [ ] Select disk and proceed with installation
- [ ] Choose region and keyboard layout
- [ ] Select "Domain join instead" for local account
- [ ] Create local user account
- [ ] Disable all privacy options during setup
- [ ] Complete installation and reach desktop

### Immediate Post-Install

- [ ] Windows boots to desktop successfully
- [ ] Can access Proxmox console
- [ ] Basic mouse and keyboard work

## Phase 2: Driver Installation

### VirtIO Drivers

- [ ] Run `install_drivers.ps1` as Administrator
- [ ] VirtIO SCSI driver installed
- [ ] VirtIO Network driver installed
- [ ] VirtIO Balloon driver installed
- [ ] VirtIO Serial driver installed
- [ ] QXL/VirtIO display driver installed
- [ ] QEMU Guest Agent installed

### Verification

- [ ] Device Manager shows no unknown devices
- [ ] Network adapter has connectivity
- [ ] Display resolution is correct
- [ ] No yellow warning icons in Device Manager

### Create Snapshot

```bash
qm snapshot <vmid> drivers-installed --description "VirtIO drivers installed"
```

## Phase 3: VNC Setup

### Installation

- [ ] Run `install_vnc.ps1` as Administrator
- [ ] TightVNC installed successfully
- [ ] VNC service is running
- [ ] Firewall rule created for port 5900

### Testing

- [ ] Run `test_vnc_connection.ps1`
- [ ] Can connect from Proxmox host
- [ ] Can connect from Ubuntu container
- [ ] Mouse and keyboard input work via VNC
- [ ] Screen updates properly

### Create Snapshot

```bash
qm snapshot <vmid> vnc-configured --description "VNC working and tested"
```

## Phase 4: Basic Configuration

### User Setup

- [ ] Run `create_accounts.ps1` if additional accounts needed
- [ ] Auto-login configured
- [ ] User profile created properly

### System Settings

- [ ] Run `base_install.ps1`
- [ ] Power settings configured (no sleep)
- [ ] UAC configured appropriately
- [ ] Basic Windows settings applied

### Browser Installation

- [ ] Run `install_chrome.ps1`
- [ ] Chrome installed successfully
- [ ] Chrome launches without errors
- [ ] Default browser set (if needed)

### Create Snapshot

```bash
qm snapshot <vmid> basic-configured --description "Basic setup complete"
```

## Phase 5: Hardening

### Anti-Automation

- [ ] Run `anti_automation.ps1`
- [ ] WebDriver registry keys removed
- [ ] Selenium indicators removed
- [ ] Browser policies configured

### Telemetry

- [ ] Run `disable_telemetry.ps1`
- [ ] Telemetry services disabled
- [ ] Telemetry hosts blocked
- [ ] Advertising ID disabled

### Updates

- [ ] Run `disable_updates.ps1`
- [ ] Windows Update service disabled
- [ ] Update policies configured
- [ ] Delivery optimization disabled

### Browser Hardening

- [ ] Run `browser_hardening.ps1`
- [ ] Third-party cookies blocked
- [ ] WebRTC settings configured
- [ ] Privacy policies applied

### Realistic Settings

- [ ] Run `realistic_settings.ps1`
- [ ] Timezone set appropriately
- [ ] Locale configured
- [ ] Display settings normalized
- [ ] Recent files created

### Create Snapshot

```bash
qm snapshot <vmid> hardening-complete --description "All hardening applied"
```

## Phase 6: Verification

### Run All Tests

- [ ] `test_vnc_connection.ps1` - All tests pass
- [ ] `test_input_devices.ps1` - Devices detected
- [ ] `test_detection.ps1` - Score 80%+

### Manual Verification

- [ ] VNC connection stable over 30+ minutes
- [ ] No unexpected popups or interruptions
- [ ] Browser launches and navigates correctly
- [ ] Mouse movements appear natural (test via VNC)

### Create Final Snapshot

```bash
qm snapshot <vmid> production-ready --description "Fully configured and verified"
```

## Phase 7: Documentation

### Record Configuration

- [ ] Document VM ID and name
- [ ] Record VNC password
- [ ] Note IP addresses
- [ ] List any customizations made

### Backup Plan

- [ ] Verify snapshots are created
- [ ] Test snapshot rollback works
- [ ] Document recovery procedures

## Quick Reference

### Execution Order

```powershell
# Run as Administrator in order:
.\install_drivers.ps1
.\install_vnc.ps1
.\base_install.ps1
.\create_accounts.ps1
.\install_chrome.ps1
.\anti_automation.ps1
.\disable_telemetry.ps1
.\disable_updates.ps1
.\browser_hardening.ps1
.\realistic_settings.ps1

# Then test:
.\test_vnc_connection.ps1
.\test_input_devices.ps1
.\test_detection.ps1
```

### Snapshot Commands

```bash
# Create snapshots
qm snapshot 100 fresh-install --description "Clean Windows install"
qm snapshot 100 drivers-installed --description "VirtIO drivers installed"
qm snapshot 100 vnc-configured --description "VNC working"
qm snapshot 100 hardening-complete --description "All hardening applied"
qm snapshot 100 production-ready --description "Ready for use"

# List snapshots
qm listsnapshot 100

# Rollback if needed
qm rollback 100 vnc-configured
```

## Troubleshooting

### VNC Won't Connect

1. Check VNC service is running
2. Verify firewall rules
3. Test with Proxmox console first
4. Run `quick_recovery.ps1`

### Input Devices Not Working

1. Check virtual HID devices on Proxmox host
2. Verify input-router service
3. Check USB passthrough if used

### Browser Issues

1. Clear Chrome profile
2. Re-run `install_chrome.ps1`
3. Check browser policies applied

### Detection Test Fails

1. Re-run hardening scripts
2. Check for Windows updates that reset settings
3. Review specific failed tests
