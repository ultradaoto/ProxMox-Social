Proxmox Host
├── LXC Container: "Input Router"
│   ├── Creates /dev/input/eventX (virtual mouse)
│   ├── Accepts commands via UNIX socket
│   └── Converts to evdev events


SYSTEM STARTUP SEQUENCE
1. Start Proxmox Host Services
bash
sudo systemctl start virtual-hid
sudo systemctl start vnc-bridge
2. Start Windows VM
bash
qm start 101  # Windows VM
# Wait 2 minutes for full boot
3. Start Ubuntu AI Controller
bash
qm start 100  # Ubuntu VM
# Wait 1 minute for boot
ssh ubuntu@192.168.100.100
sudo systemctl start ai-agent
4. Monitor System
bash
# On Proxmox host
tail -f /var/log/virtual-input.log

# On Ubuntu VM
journalctl -u ai-agent -f

# Check Windows VNC connection
netstat -tulpn | grep 5900
TROUBLESHOOTING
Common Issues
1. Virtual Mouse Not Detected
bash
# Check if device was created
ls -la /dev/input/by-id/

# Check Proxmox VM config
cat /etc/pve/qemu-server/100.conf | grep usb

# Restart virtual HID service
sudo systemctl restart virtual-hid
2. VNC Connection Failed
bash
# Check Windows VM IP
qm guest exec 100 ping 192.168.100.101

# Check VNC service on Windows
# Connect via Proxmox console to Windows
# Verify TightVNC service is running
3. AI Agent Crashes
bash
# Check logs
journalctl -u ai-agent -n 50

# Check Python dependencies
pip list | grep -E "(opencv|pyautogui|human)"

# Test individual components
python3 -c "import cv2; print(cv2.__version__)"
4. Human Movement Too Robotic
Adjust behavior settings in config.json

Increase mouse movement duration

Add more random delays

Enable higher tremor level

SECURITY NOTES
Isolate Network: Keep VM bridge internal only

Strong Passwords: Use unique passwords for VNC/RDP

Regular Snapshots: Take Proxmox snapshots before changes

Monitor Logs: Check for suspicious activity

No External Access: Don't expose VNC/RDP to internet

VPN Access Only: Use WireGuard/OpenVPN if remote access needed

PERFORMANCE TUNING
For Better AI Performance
bash
# On Proxmox host
# Give Ubuntu VM more CPU cores
qm set 101 --cores 8

# Enable NUMA if available
qm set 101 --numa 1

# Pass through GPU for AI acceleration
qm set 101 --hostpci0 01:00.0
For Better Windows Performance
bash
# Enable VirtIO disk cache
qm set 100 --cache writeback

# Add more RAM if needed
qm set 100 --memory 8192

# Enable ballooning driver
qm set 100 --balloon 1




FOLDER 1: HOST (Proxmox Host Configuration)
Purpose
Configure Proxmox to create virtual Logitech HID devices and set up screen capture between VMs.

Prerequisites
Proxmox 8.x installed

Two VMs created: Ubuntu 22.04+ and Windows 10

GPU passthrough capable hardware (optional but recommended)

Setup Steps
1. Create Virtual Input Devices
bash
# Create virtual input device script
cd /opt/virtual-input/
sudo nano create_virtual_hid.py
python
#!/usr/bin/env python3
"""
Creates virtual Logitech mouse/keyboard devices for Windows VM control
"""
import os
import struct
import fcntl
import array
import time
from pathlib import Path

# Create a virtual HID device that appears as Logitech hardware
def create_virtual_hid():
    # Linux HID driver constants
    BUS_USB = 0x03
    HID_MAX_DESCRIPTOR_SIZE = 4096
    
    # Logitech Unifying Receiver vendor/product IDs
    LOGITECH_VENDOR = 0x046d
    LOGITECH_MOUSE = 0xc52b  # M510/M525
    LOGITECH_KEYBOARD = 0xc534  # K350
    
    # Create uhid device file
    uhid_fd = os.open("/dev/uhid", os.O_RDWR)
    
    # Create mouse descriptor
    mouse_desc = bytes([
        0x05, 0x01,  # Usage Page (Generic Desktop)
        0x09, 0x02,  # Usage (Mouse)
        0xA1, 0x01,  # Collection (Application)
        0x09, 0x01,  #   Usage (Pointer)
        0xA1, 0x00,  #   Collection (Physical)
        0x05, 0x09,  #     Usage Page (Button)
        0x19, 0x01,  #     Usage Minimum (1)
        0x29, 0x03,  #     Usage Maximum (3)
        0x15, 0x00,  #     Logical Minimum (0)
        0x25, 0x01,  #     Logical Maximum (1)
        0x95, 0x03,  #     Report Count (3)
        0x75, 0x01,  #     Report Size (1)
        0x81, 0x02,  #     Input (Data,Var,Abs)
        0x95, 0x01,  #     Report Count (1)
        0x75, 0x05,  #     Report Size (5)
        0x81, 0x03,  #     Input (Const,Var,Abs)
        0x05, 0x01,  #     Usage Page (Generic Desktop)
        0x09, 0x30,  #     Usage (X)
        0x09, 0x31,  #     Usage (Y)
        0x09, 0x38,  #     Usage (Wheel)
        0x15, 0x81,  #     Logical Minimum (-127)
        0x25, 0x7F,  #     Logical Maximum (127)
        0x75, 0x08,  #     Report Size (8)
        0x95, 0x03,  #     Report Count (3)
        0x81, 0x06,  #     Input (Data,Var,Rel)
        0xC0,        #   End Collection
        0xC0         # End Collection
    ])
    
    # Create UHID device
    create2 = struct.pack('I', 30)  # size of struct
    create2 += b'virtual-logitech-mouse' + b'\x00' * (128 - 22)
    create2 += bytes([BUS_USB])
    create2 += struct.pack('H', LOGITECH_VENDOR)
    create2 += struct.pack('H', LOGITECH_MOUSE)
    create2 += struct.pack('I', 1)  # version
    create2 += struct.pack('I', len(mouse_desc))
    create2 += mouse_desc
    create2 += struct.pack('Q', 0)  # rd_size
    create2 += struct.pack('Q', 512)  # rd_data
    create2 += struct.pack('Q', 0)  # country
    
    fcntl.ioctl(uhid_fd, 0xC0285502, create2)  # UHID_CREATE2
    
    return uhid_fd

if __name__ == "__main__":
    print("Creating virtual Logitech HID devices...")
    mouse_fd = create_virtual_hid()
    print(f"Virtual mouse created at /dev/uhid (fd: {mouse_fd})")
    
    # Keep the device alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        os.close(mouse_fd)
2. Configure USB Passthrough to Windows VM
bash
# Find the virtual device
ls -la /dev/input/by-id/

# Add to Windows VM config (VMID=101)
nano /etc/pve/qemu-server/101.conf
Add to VM config:

text
# Virtual Logitech devices
usb0: host=046d:c52b,usb3=1  # Mouse
usb1: host=046d:c534,usb3=1  # Keyboard
3. Set Up Shared Memory for Inter-VM Communication
bash
# Create shared memory segment
sudo mkdir /dev/shm/virtual_input
sudo chmod 777 /dev/shm/virtual_input

# Create named pipe for mouse control
mkfifo /tmp/virtual_mouse_input
chmod 666 /tmp/virtual_mouse_input

# Create named pipe for keyboard control
mkfifo /tmp/virtual_keyboard_input
chmod 666 /tmp/virtual_keyboard_input
4. Install Required Packages
bash
sudo apt update
sudo apt install -y \
    evemu-tools \
    input-utils \
    python3-evdev \
    python3-pip \
    socat \
    netcat-openbsd

pip3 install evdev python-uinput
5. Create Systemd Service
bash
sudo nano /etc/systemd/system/virtual-hid.service
ini
[Unit]
Description=Virtual HID Device for AI Control
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/virtual-input/hid_controller.py
Restart=always
User=root

[Install]
WantedBy=multi-user.target
6. Enable VNC/Spice for Screen Capture
bash
# For Windows VM (VMID=101)
qm set 101 --vga virtio
qm set 100 --serial0 socket
qm set 100 --args '-device virtio-vga-gl -display gtk,gl=on'
7. Network Configuration for VMs
bash
# Create internal bridge for VM communication
sudo nano /etc/network/interfaces

# Add:
auto vmbr1
iface vmbr1 inet static
    address 192.168.100.1/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0

# Add to Windows VM
qm set 100 --net1 virtio,bridge=vmbr1,firewall=0

# Add to Ubuntu VM
qm set 101 --net1 virtio,bridge=vmbr1,firewall=0
Testing
bash
# Start virtual HID service
sudo systemctl start virtual-hid

# Check if device appears
ls -la /dev/input/by-id/

# Monitor input events
evtest /dev/input/eventX