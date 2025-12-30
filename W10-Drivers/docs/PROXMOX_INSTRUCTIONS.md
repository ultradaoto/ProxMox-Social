# Proxmox Host Configuration Guide

> [!IMPORTANT]
> These steps must be performed on your **Proxmox Virtual Environment (PVE) Host** (the bare metal server), NOT on this Windows VM.

## 1. Transfer Files
You need to copy the `Host` directory from this repository to your Proxmox server.
**Option A:** Clone the repo directly on Proxmox (Recommended).
**Option B:** Use SCP/SFTP to copy the folder.

### On Proxmox Host (SSH):
```bash
# Example: Install git and clone
apt update && apt install git -y
git clone https://github.com/ultradaoto/proxmox-social.git /opt/proxmox-social
cd /opt/proxmox-social/Host
```

## 2. Run Installation
The installation script will:
- Create virtual HID devices (mouse/keyboard).
- Configure network routing (`vmbr1`).
- Setup firewall rules.
- Install system services.

```bash
chmod +x scripts/install.sh
sudo ./scripts/install.sh
```

## 3. Verify Installation
After the script finishes, check that the components are ready:

### Virtual HID
```bash
# Check if services are active
systemctl status virtual-hid
systemctl status input-router

# Check for virtual logitech devices
ls -la /dev/input/by-id/ | grep "Logitech"
```

### Network
Ensure `vmbr1` is active:
```bash
ip addr show vmbr1
# Should show inet 192.168.100.1/24
```

## 4. Next Steps
Once the Host is ready:
1.  **Configure VMs**: Ensure this Windows VM is using `vmbr1` network bridge.
2.  **Ubuntu AI**: Setup the Controller VM (`Ubu-Cont`).
