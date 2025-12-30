# ProxMox-Social System Status

**Last Updated:** 2025-12-29 22:20 PST
**Host:** ultranet (Proxmox VE)
**Status:** READY FOR TESTING

---

## Current System State

### Host Services

| Service | Status | Description |
|---------|--------|-------------|
| virtual-hid | RUNNING | Listens on ports 8888/8889 for mouse/keyboard JSON commands |
| dnsmasq | RUNNING | DHCP server for vmbr1 (192.168.100.0/24) |

### Network Configuration

| Interface | IP Address | Purpose |
|-----------|------------|---------|
| vmbr0 | 10.0.0.68 | External network (internet access) |
| vmbr1 | 192.168.100.1/24 | Internal VM-to-VM network (isolated) |

### Virtual Machines

| VMID | Name | Status | vmbr0 (external) | vmbr1 (internal) |
|------|------|--------|------------------|------------------|
| 100 | Ubuntu24 | ONLINE | DHCP | 192.168.100.100 |
| 101 | Windows10 | ONLINE | DHCP | 192.168.100.101 (RDP:3389 open) |

---

## IP Address Assignments

```
Host (Proxmox):     192.168.100.1
Ubuntu VM (100):    192.168.100.100
Windows VM (101):   192.168.100.101
```

## Port Assignments

```
Mouse input:        TCP 8888 (JSON protocol)
Keyboard input:     TCP 8889 (JSON protocol)
```

---

## VM Setup Instructions

### Ubuntu VM (VMID 100) - AI Controller

**Network Interface:** The second NIC (net1) is connected to vmbr1 but needs configuration inside the guest.

#### Step 1: Configure Internal Network Interface

```bash
# Find the second interface name (likely ens19 or enp6s19)
ip link show

# Create netplan configuration
sudo tee /etc/netplan/60-internal.yaml << 'EOF'
network:
  version: 2
  ethernets:
    ens19:
      addresses:
        - 192.168.100.100/24
      routes:
        - to: 192.168.100.0/24
          via: 192.168.100.1
EOF

# Apply the configuration
sudo netplan apply

# Verify connectivity
ping -c 3 192.168.100.1
```

#### Step 2: Install AI Controller

The AI controller scripts are in `ubu-cont/` directory. Copy them to the Ubuntu VM and run:

```bash
# From the Ubuntu VM, the host is reachable at 192.168.100.1
# Install the agent (see ubu-cont/README.md for details)
```

#### Step 3: Test Connectivity to HID Service

```bash
# Test mouse port
nc -zv 192.168.100.1 8888

# Test keyboard port
nc -zv 192.168.100.1 8889
```

---

### Windows VM (VMID 101) - Target Display

**Network Interface:** The second NIC (net1) is connected to vmbr1 but needs IP configuration.

#### Step 1: Configure Internal Network Interface

1. Open **Run** (Win+R) → type `ncpa.cpl` → Enter
2. Find **Ethernet 2** (or "Unidentified Network")
3. Right-click → **Properties** → **Internet Protocol Version 4 (TCP/IPv4)**
4. Select **Use the following IP address:**
   - IP address: `192.168.100.101`
   - Subnet mask: `255.255.255.0`
   - Default gateway: `192.168.100.1`
5. Click **OK** → **Close**

#### Step 2: Verify Connectivity

Open Command Prompt and run:
```cmd
ping 192.168.100.1
ping 192.168.100.100
```

#### Step 3: Install VNC Server (Optional)

For remote viewing, install TightVNC or similar from `w10-drivers/` directory.

---

## HID Input Protocol

The virtual-hid service accepts JSON commands over TCP.

### Mouse Commands (Port 8888)

```json
{"type": "move", "x": 100, "y": 50}
{"type": "click", "button": "left"}
{"type": "click", "button": "right"}
{"type": "scroll", "delta": -3}
```

### Keyboard Commands (Port 8889)

```json
{"type": "key", "key": "a"}
{"type": "key", "key": "enter"}
{"type": "key", "key": "ctrl+c"}
{"type": "text", "text": "Hello World"}
```

### Testing the HID Chain

From Ubuntu VM (after network is configured):

```bash
# Move mouse
echo '{"type": "move", "x": 100, "y": 50}' | nc 192.168.100.1 8888

# Type text
echo '{"type": "text", "text": "Hello from Ubuntu"}' | nc 192.168.100.1 8889

# Click
echo '{"type": "click", "button": "left"}' | nc 192.168.100.1 8888
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Proxmox Host (ultranet)                      │
│                        192.168.100.1                             │
│  ┌─────────────────┐              ┌─────────────────┐           │
│  │  virtual-hid    │              │    dnsmasq      │           │
│  │  :8888 (mouse)  │              │  DHCP server    │           │
│  │  :8889 (kbd)    │              │  for vmbr1      │           │
│  └────────┬────────┘              └─────────────────┘           │
│           │                                                      │
│           │ vmbr1 (192.168.100.0/24)                            │
│           │                                                      │
│  ┌────────┴────────┬──────────────────────┐                     │
│  │                 │                      │                     │
│  ▼                 ▼                      ▼                     │
│ ┌──────────────┐  ┌──────────────┐   (USB passthrough           │
│ │ Ubuntu24     │  │ Windows10    │    to Windows for            │
│ │ VM 100       │  │ VM 101       │    physical HID)             │
│ │ .100         │  │ .101         │                              │
│ │              │  │              │                              │
│ │ AI Agent     │  │ Target       │                              │
│ │ Controller   │──│ Display      │                              │
│ └──────────────┘  └──────────────┘                              │
└─────────────────────────────────────────────────────────────────┘

Data Flow:
1. AI Agent on Ubuntu captures screen/makes decisions
2. AI sends JSON commands to Host:8888/8889
3. Host virtual-hid converts to HID reports
4. HID reports sent to Windows via USB passthrough
5. Windows receives as native mouse/keyboard input
```

---

## Current Connectivity Status

**All systems connected and ready for testing!**

| From | To | Status |
|------|-----|--------|
| Host | Ubuntu (192.168.100.100) | PING OK |
| Host | Windows (192.168.100.101) | ARP OK (ping blocked by firewall) |
| Ubuntu | Host HID ports (8888/8889) | READY TO TEST |

## Next Steps for AI Agents

### Ubuntu AI Agent (192.168.100.100)
1. Test HID connectivity: `nc -zv 192.168.100.1 8888 && nc -zv 192.168.100.1 8889`
2. Send test mouse command: `echo '{"type": "move", "x": 100, "y": 100}' | nc 192.168.100.1 8888`
3. Send test keyboard command: `echo '{"type": "text", "text": "Hello"}' | nc 192.168.100.1 8889`

### Windows Target (192.168.100.101)
1. Observe mouse/keyboard input from Ubuntu's HID commands
2. RDP available on port 3389 for remote monitoring

---

## Known Limitations

1. **No Physical HID Devices Yet**
   - `/dev/hidg0` and `/dev/hidg1` don't exist on host
   - USB gadget mode may need hardware support or additional configuration
   - Current setup listens on TCP but can't output to real HID devices

2. **USB Passthrough**
   - Verify USB controller is passed through to Windows VM
   - Check `lsusb` inside Windows to confirm HID devices appear

---

## Quick Reference Commands

```bash
# Check VM status
qm list

# Check bridge connections
brctl show vmbr1

# Check services
systemctl status virtual-hid dnsmasq

# View DHCP leases
cat /var/lib/misc/dnsmasq.leases

# Test from host
ping 192.168.100.100  # Ubuntu
ping 192.168.100.101  # Windows

# Monitor vmbr1 traffic
tcpdump -i vmbr1 -n

# View HID service logs
journalctl -u virtual-hid -f
```

---

## File Locations

| Path | Description |
|------|-------------|
| `/root/ProxMox-Social/Host/` | Host configuration scripts |
| `/root/ProxMox-Social/ubu-cont/` | Ubuntu AI agent code |
| `/root/ProxMox-Social/w10-drivers/` | Windows drivers/tools |
| `/etc/dnsmasq.d/vmbr1.conf` | DHCP server config |
| `/etc/systemd/system/virtual-hid.service` | HID service unit |
