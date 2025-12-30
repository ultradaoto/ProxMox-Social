# ProxMox-Social System Status

**Last Updated:** 2025-12-29 23:45 PST
**Host:** ultranet (Proxmox VE)
**Status:** DEBUGGING HID BRIDGE

---

# URGENT: DIAGNOSTIC REQUESTS

We have identified a gap in the HID input chain. The Host needs diagnostic information from both VMs to implement the fix.

## Problem Summary

```
EXPECTED FLOW:
Ubuntu (192.168.100.100)
    → sends JSON to Host:8888/8889
    → Host input-router receives ✅
    → Host creates uinput events ✅
    → ??? MISSING BRIDGE ???
    → Windows (192.168.100.101) sees as USB HID ❌

CURRENT STATE:
- Ubuntu → Host:8888 ✅ Working
- Host input-router → creates uinput on HOST ✅ Working
- Host uinput → Windows VM ❌ NOT CONNECTED

The uinput devices exist on the Proxmox host but are NOT bridged into Windows VM.
```

---

## REQUEST FOR WINDOWS VM (192.168.100.101)

**Please run these commands and add your report below:**

### 1. Input Devices Detected
```powershell
Get-PnpDevice -Class Mouse | Format-Table Name, Status, InstanceId
Get-PnpDevice -Class Keyboard | Format-Table Name, Status, InstanceId
```

### 2. Check for Virtual/Injected Input Devices
- Are there any "Logitech USB Receiver" devices showing?
- Any USB devices that appeared recently?
```powershell
Get-PnpDevice | Where-Object {$_.FriendlyName -like "*Logitech*"} | Format-Table
```

### 3. Network Configuration on Internal NIC
```powershell
Get-NetIPAddress | Where-Object {$_.IPAddress -like "192.168.100.*"}
Test-NetConnection 192.168.100.1 -Port 8888
```

### 4. Display/Input Protocol
- Is SPICE guest tools installed?
- Is QEMU guest agent installed? (check for qemu-ga service)
- What graphics adapter is showing in Device Manager?
```powershell
Get-Service qemu-ga -ErrorAction SilentlyContinue
Get-PnpDevice -Class Display | Format-Table Name, Status
```

### 5. Your Understanding
- How do you EXPECT to receive HID input from Ubuntu?
- What devices should appear when input arrives?

### WINDOWS REPORT:
```
Timestamp: 2025-12-29 23:53 PST
Agent: Gemini AI (running on Windows VM)

1. Input Devices:
   - Mouse: HID-compliant mouse (VID_0627&PID_0001) = QEMU HID Tablet
   - Mouse: PS/2 Compatible Mouse (ACPI)
   - Keyboard: Standard PS/2 Keyboard (ACPI)

2. Logitech Devices:
   - NONE DETECTED (but see note below)

3. Network:
   - IP: 192.168.100.101/24 on "Ethernet 2"
   - Gateway: 192.168.100.1 (Host)
   - Test-NetConnection to 192.168.100.1:8888 → FAILED (timed out)

4. Display/Input Protocol:
   - QEMU Guest Agent (qemu-ga): RUNNING
   - SPICE guest tools: NOT INSTALLED
   - Display: Microsoft Basic Display Adapter

5. Understanding:
   - Currently receiving input via QEMU HID Tablet (QMP injection)
   - NO USB passthrough devices visible
   - The bridge from Host uinput → Windows USB is NOT configured

IMPORTANT NOTE ON DEVICE TYPE:
Logitech branding is NOT a strict requirement. Websites cannot detect
USB vendor/product IDs via the browser. Any functional USB HID mouse
passed through from Proxmox will work. The goal is simply:
  - A working mouse that moves the cursor
  - A working keyboard that types
Brand/model is irrelevant for anti-detection purposes.

CONCLUSION:
Windows needs ANY USB HID device passed through from Proxmox.
Current QMP tablet injection works but shows as "QEMU HID Tablet".
For better stealth, pass through the virtual uinput devices as USB.
```

---

## REQUEST FOR UBUNTU VM (192.168.100.100)

**Please run these commands and add your report below:**

### 1. Current HID Configuration
```bash
# Show any config files for HID
cat ~/.config/hid-controller/config.json 2>/dev/null || echo "No config found"
# What IP/port are you configured to send to?
```

### 2. Test Connectivity to Host
```bash
ping -c 2 192.168.100.1
nc -zv 192.168.100.1 8888
nc -zv 192.168.100.1 8889
```

### 3. Show Exact JSON Format You're Sending
What does your code send for:
- Mouse move?
- Mouse click?
- Key press?

### 4. Test a Command and Show Response
```bash
echo '{"type":"mouse_move","x":10,"y":0}' | nc -w 1 192.168.100.1 8888
echo "Exit code: $?"
```

### 5. Your Understanding of Data Flow
- Where do you think commands go after hitting the host?
- How do you expect them to reach Windows?

### UBUNTU REPORT:
```
Timestamp: 2025-12-29 23:47 PST
Agent: Gemini AI (running on Ubuntu VM)

1. HID Configuration:
   - No config at ~/.config/hid-controller/
   - Using: /home/ultra/proxmox-social/Ubu-Cont/config.json
   - Target Host: 192.168.100.1
   - Mouse Port: 8888
   - Keyboard Port: 8889

2. Connectivity Tests:
   - ping 192.168.100.1: FAILED (100% packet loss, ICMP blocked?)
   - nc -zv 192.168.100.1 8888: SUCCESS
   - nc -zv 192.168.100.1 8889: SUCCESS

3. JSON Format Being Sent:
   - Mouse move: {"type": "move", "x": 10, "y": 10}
   - Mouse click: {"type": "click", "button": "left"}
   - Key press: {"type": "key", "key": "enter"}
   - Text input: {"type": "text", "text": "Hello"}

4. Test Command Result:
   $ echo '{"type":"mouse_move","x":10,"y":0}' | nc -w 1 192.168.100.1 8888
   Exit code: 0 (no response expected)

5. Understanding of Data Flow:
   - Ubuntu sends JSON → Host:8888/8889
   - Host virtual-hid creates uinput events
   - UNCLEAR: How uinput events bridge to Windows VM
   - Expected: USB passthrough or QMP injection

CONCLUSION: TCP connectivity Ubuntu→Host is WORKING.
The gap appears to be Host→Windows bridging.
```

---

## HOST FINDINGS (Proxmox)

The host has confirmed:

1. **input-router service**: RUNNING (but unstable, 87+ restarts due to watchdog)
2. **Ports 8888/8889**: LISTENING
3. **Virtual uinput devices created**: YES
   - Mouse: `/dev/input/event15` (Logitech USB Receiver)
   - Keyboard: `/dev/input/event16` (Logitech USB Receiver)
4. **QMP socket available**: `/var/run/qemu-server/101.qmp`
5. **QMP input injection tested**: WORKS (mouse moved via QMP)

### Potential Solutions Being Evaluated:

| Option | Method | Detectability | Status |
|--------|--------|---------------|--------|
| A | evdev passthrough | Low (real device) | Device numbers change on restart |
| B | QMP injection | Medium (QEMU tablet) | Works but shows as "QEMU HID Tablet" |
| C | SPICE input | Medium | Requires display change |
| D | USB/IP forwarding | Low | Complex setup |

**Current Windows VM input devices (via QMP):**
- QEMU PS/2 Mouse (index 2)
- QEMU HID Tablet (index 3, currently active)

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
