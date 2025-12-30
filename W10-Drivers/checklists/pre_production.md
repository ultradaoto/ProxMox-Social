# Pre-Production Verification Checklist

Use this checklist before deploying the Windows VM for actual automated tasks.
All items should pass before beginning production operations.

## System Health

### Resource Usage

- [ ] CPU usage at idle < 10%
- [ ] Memory usage < 60% of allocated
- [ ] Disk space > 20% free
- [ ] No high-resource processes unexpectedly running

### Services

- [ ] VNC service running
- [ ] QEMU Guest Agent running
- [ ] No pending Windows restarts
- [ ] No update notifications pending

### Network

- [ ] Network adapter connected
- [ ] Can resolve DNS queries
- [ ] Can reach internet (if required)
- [ ] Internal network to Ubuntu container accessible

## Detection Avoidance

### Anti-Automation Tests

```powershell
.\test_detection.ps1
```

- [ ] Score 80% or higher
- [ ] No WebDriver registry keys
- [ ] No Selenium artifacts
- [ ] Browser policies applied

### Input Devices

```powershell
.\test_input_devices.ps1
```

- [ ] Mouse device detected
- [ ] Keyboard device detected
- [ ] Devices appear as Logitech hardware
- [ ] No device errors

### VNC Connection

```powershell
.\test_vnc_connection.ps1
```

- [ ] VNC service running
- [ ] Port 5900 listening
- [ ] Firewall rules enabled
- [ ] Can connect from Ubuntu container

## Browser Readiness

### Chrome Status

- [ ] Chrome installed and launches
- [ ] No first-run dialogs pending
- [ ] Default browser prompts dismissed
- [ ] Extension installation prompts handled

### Browser Fingerprint

- [ ] Third-party cookies blocked
- [ ] DNT enabled
- [ ] User agent is standard
- [ ] No automation flags visible

### Browsing History

- [ ] Some history exists (not empty)
- [ ] Cookies present from previous sessions
- [ ] Bookmarks created (optional)
- [ ] Browser appears "used"

## User Environment

### Windows Settings

- [ ] Timezone appropriate for use case
- [ ] Locale set correctly
- [ ] Date/time format standard
- [ ] Display resolution is common (1920x1080, etc.)

### User Profile

- [ ] Documents folder has files
- [ ] Desktop not empty but not cluttered
- [ ] Wallpaper is Windows default
- [ ] Theme is light (more common)

### No Pending Dialogs

- [ ] No license activation popups
- [ ] No security warnings
- [ ] No update prompts
- [ ] No application notices

## Proxmox Host Verification

### Virtual HID Devices

```bash
# On Proxmox host
systemctl status virtual-hid.service
systemctl status input-router.service
```

- [ ] Virtual HID service running
- [ ] Input router service running
- [ ] No service errors in logs

### Network Bridge

- [ ] vmbr1 (internal bridge) is up
- [ ] Windows VM connected to internal network
- [ ] Ubuntu container connected to internal network
- [ ] Can ping between VMs

### Firewall

```bash
iptables -L -n | grep -A5 VM_ISOLATION
```

- [ ] Firewall rules active
- [ ] VM isolation rules in place
- [ ] Only allowed ports accessible

## Ubuntu Container Verification

### Agent Services

```bash
# In Ubuntu container
systemctl status computer-agent
```

- [ ] Agent service installed
- [ ] VNC connection to Windows working
- [ ] Can send mouse commands
- [ ] Can send keyboard commands

### Vision AI

- [ ] OmniParser model loaded
- [ ] Qwen-VL model accessible (if used)
- [ ] Can capture and analyze screenshots

### Human Input Simulation

- [ ] Mouse movement profiles loaded
- [ ] Keyboard timing configured
- [ ] Test movements appear natural

## Performance Baseline

### Response Times

Test and record baseline metrics:

- [ ] VNC frame capture latency: ____ms
- [ ] Mouse command round-trip: ____ms
- [ ] Keyboard command round-trip: ____ms
- [ ] Vision model inference time: ____ms

### Stability Test

- [ ] 30-minute idle test - no issues
- [ ] 30-minute active test - no issues
- [ ] No memory leaks observed
- [ ] No connection drops

## Security Review

### Credential Management

- [ ] No credentials in plain text files
- [ ] Password manager configured (if used)
- [ ] API keys secured
- [ ] VNC password is strong

### Access Control

- [ ] Only necessary ports open
- [ ] SSH keys rotated (if applicable)
- [ ] Logs configured appropriately
- [ ] Monitoring in place (if required)

## Backup Status

### Snapshots

```bash
qm listsnapshot <vmid>
```

- [ ] Current snapshot exists
- [ ] Snapshot is recent (< 24 hours old)
- [ ] Can identify rollback point

### Recovery Plan

- [ ] Know which snapshot to rollback to
- [ ] Emergency RDP script available
- [ ] Quick recovery script tested

## Final Verification

### End-to-End Test

Perform a complete test workflow:

1. [ ] Start agent on Ubuntu container
2. [ ] Verify Windows screen captured
3. [ ] Send test mouse movement
4. [ ] Send test keyboard input
5. [ ] Verify actions appear on Windows
6. [ ] Stop agent cleanly

### Approval

- [ ] All checklist items verified
- [ ] No blocking issues
- [ ] System ready for production use

## Quick Commands Reference

### Check All Services (Proxmox)

```bash
systemctl status virtual-hid input-router vnc-bridge
```

### Check All Services (Ubuntu)

```bash
systemctl status computer-agent
```

### Quick Tests (Windows)

```powershell
.\test_vnc_connection.ps1
.\test_input_devices.ps1
.\test_detection.ps1
```

### Create Pre-Production Snapshot

```bash
qm snapshot <vmid> pre-prod-$(date +%Y%m%d) --description "Pre-production verified"
```

## Issue Resolution

### If VNC Fails

1. Run `quick_recovery.ps1` on Windows
2. Check firewall rules
3. Restart VNC service
4. Test from Proxmox console

### If Input Fails

1. Check virtual-hid service on host
2. Check input-router service on host
3. Restart services in order
4. Test with simple commands

### If Detection Score Low

1. Re-run hardening scripts
2. Clear browser cache/cookies
3. Build more browsing history
4. Check for Windows updates that reset settings

### If Network Fails

1. Check bridge configuration
2. Verify VM network settings
3. Test from Proxmox shell
4. Check firewall rules

---

**Sign-off**

Date: ____________

Verified by: ____________

Notes:
