# Proxmox Computer Control Agent System

An **undetectable AI-controlled Windows environment** using Proxmox virtualization. The Windows VM receives input from virtual Logitech HID devices and has **zero knowledge** it's being controlled by AI.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PROXMOX HOST (Bare Metal)                    │
│                                                                 │
│   Virtual HID Bridge: Creates /dev/input devices appearing     │
│   as Logitech mouse/keyboard, routes commands between VMs      │
│                                                                 │
│  ┌───────────────────────┐      ┌───────────────────────┐      │
│  │  Ubuntu AI Controller │      │  Windows 10 Target    │      │
│  │  192.168.100.101      │      │  192.168.100.100      │      │
│  │                       │      │                       │      │
│  │  • Vision AI          │─────▶│  • Vanilla Windows    │      │
│  │  • Human-like input   │ VNC  │  • Chrome (logged in) │      │
│  │  • Decision making    │◀─────│  • No automation      │      │
│  └───────────────────────┘ HID  └───────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

## Why This Works

1. **Virtual USB HID devices** appear identical to physical Logitech hardware
2. **VNC screen capture** is passive - Windows doesn't know it's being watched
3. **No automation tools** installed on Windows - nothing to detect
4. **Human-like behavior** with Fitts's Law timing, micro-jitter, typing errors

## Project Structure

```
/proxmox-computer-control/
├── AGENTS.md              # Parallel development guide
├── README.md              # This file
├── host/                  # Proxmox host configuration
├── ubu-cont/              # Ubuntu AI controller VM
└── w10-drivers/           # Windows 10 target VM
```

## Quick Start

### Prerequisites
- Proxmox VE 8.x installed on bare metal
- NVIDIA GPU (optional, for faster vision AI)
- 32GB+ RAM recommended
- 200GB+ storage

### Setup Order

1. **Configure Proxmox Host** (`host/`)
   ```bash
   cd host
   ./scripts/install.sh
   ```

2. **Install Windows 10 VM** (`w10-drivers/`)
   - Create VM in Proxmox web UI
   - Install Windows, run hardening scripts
   - Set up VNC server and Chrome

3. **Set Up Ubuntu AI Controller** (`ubu-cont/`)
   ```bash
   cd ubu-cont
   ./scripts/install_models.sh
   python -m src.agent.main_agent
   ```

## Detection Avoidance

| Vector | Solution |
|--------|----------|
| Device ID | Virtual devices use Logitech vendor/product IDs |
| Movement patterns | Bezier curves with Fitts's Law timing |
| Typing speed | Variable WPM with realistic error rate |
| Browser automation | No CDP, no WebDriver, no automation flags |
| Input timing | Random micro-delays simulating human reaction |

## Parallel Development

See `AGENTS.md` for detailed workstream separation. Three independent agents can work on:
- **Host Agent**: Virtual HID and routing
- **Ubuntu AI Agent**: Vision and control
- **Windows Agent**: Target configuration

## License

Private project - not for distribution.
