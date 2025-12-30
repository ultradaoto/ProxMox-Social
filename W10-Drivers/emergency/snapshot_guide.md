# Proxmox Snapshot Guide for Windows VM Recovery

## Overview

Snapshots are your safety net. Always create snapshots before making changes
and after achieving a stable, working configuration.

## Recommended Snapshot Strategy

### Initial Snapshots (Create in Order)

1. **fresh-install**
   - After Windows installation, before any customization
   - Clean slate for starting over

2. **drivers-installed**
   - After VirtIO drivers and basic drivers installed
   - Working display, network, storage

3. **vnc-configured**
   - After VNC installed and tested
   - Verify you can connect before snapshotting

4. **hardening-complete**
   - After running all hardening scripts
   - Telemetry disabled, updates blocked

5. **production-ready**
   - Fully configured, tested, and validated
   - This is your rollback target

## Proxmox CLI Commands

### Create Snapshot

```bash
# Basic snapshot
qm snapshot <vmid> <snapname>

# With description
qm snapshot <vmid> <snapname> --description "Description here"

# Include VM state (RAM)
qm snapshot <vmid> <snapname> --vmstate 1

# Example
qm snapshot 100 production-ready --description "Fully configured and tested"
```

### List Snapshots

```bash
qm listsnapshot <vmid>

# Example output:
# `-> fresh-install
#    `-> drivers-installed
#       `-> vnc-configured
#          `-> hardening-complete
#             `-> production-ready (current)
```

### Rollback to Snapshot

```bash
# Stop VM first
qm stop <vmid>

# Rollback
qm rollback <vmid> <snapname>

# Start VM
qm start <vmid>

# Example
qm stop 100
qm rollback 100 vnc-configured
qm start 100
```

### Delete Snapshot

```bash
qm delsnapshot <vmid> <snapname>

# Example
qm delsnapshot 100 old-snapshot
```

## Recovery Scenarios

### VNC Not Connecting

1. Wait 2-3 minutes (VM may be slow to boot)
2. Check VM status in Proxmox console
3. Try Proxmox's built-in VNC console
4. If still failing, rollback to `vnc-configured` snapshot

```bash
qm stop 100
qm rollback 100 vnc-configured
qm start 100
```

### Input Not Working

1. Run `quick_recovery.ps1` via Proxmox console
2. Check virtual HID devices on host
3. Restart input-router service on host
4. If still failing, rollback to `production-ready`

### Windows Updates Broke Something

1. This is why we disable updates
2. Rollback to `production-ready` snapshot
3. Re-run `disable_updates.ps1`

### Browser Detection Issues

1. Rollback to `production-ready`
2. Re-run hardening scripts
3. Clear browser data before next attempt

### Complete System Failure

1. Rollback to `fresh-install`
2. Run all setup scripts in order
3. Create new snapshots at each stage

## Best Practices

### When to Snapshot

- Before running any new script
- After successful configuration changes
- Before Windows updates (if you must allow them)
- After testing confirms everything works

### Snapshot Naming Convention

```
<stage>-<date>-<description>
```

Examples:
- `prod-20241215-verified-working`
- `test-20241215-new-hardening`

### Storage Considerations

- Snapshots consume disk space
- Keep only essential snapshots
- Delete old test snapshots regularly

```bash
# Check storage usage
pvesm status

# List snapshot sizes
qm config <vmid> --snapshot
```

### Automation Script

Create on Proxmox host at `/root/snapshot-vm.sh`:

```bash
#!/bin/bash
VMID=${1:-100}
NAME=${2:-"auto-$(date +%Y%m%d-%H%M)"}
DESC=${3:-"Automatic snapshot"}

echo "Creating snapshot '$NAME' for VM $VMID..."
qm snapshot $VMID "$NAME" --description "$DESC"

echo "Current snapshots:"
qm listsnapshot $VMID
```

Usage:
```bash
chmod +x /root/snapshot-vm.sh
./snapshot-vm.sh 100 "before-changes" "Testing new configuration"
```

## Emergency Recovery Checklist

1. [ ] Can you access Proxmox web UI?
2. [ ] Can you see the VM in Proxmox?
3. [ ] Can you access VM via Proxmox console?
4. [ ] Is the VM running? (`qm status <vmid>`)
5. [ ] What was the last working snapshot?
6. [ ] Did you try `quick_recovery.ps1`?
7. [ ] Did you try enabling RDP (`enable_rdp.ps1`)?

If all else fails:
```bash
qm stop 100
qm rollback 100 fresh-install
qm start 100
# Start over with setup scripts
```

## Notes

- VM state snapshots (with RAM) are larger but faster to restore
- Without VM state, Windows will boot fresh after rollback
- Always verify snapshot works immediately after creating it
- Document what changed between snapshots
