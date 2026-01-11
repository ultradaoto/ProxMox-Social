# AGENTS.md - Proxmox Computer Control System

## Project Overview

This system creates an **undetectable AI-controlled Windows environment** using Proxmox virtualization. The Windows VM receives input from virtual Logitech HID devices and displays its screen via VNC - it has **zero knowledge** it's being controlled by AI.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROXMOX HOST (Bare Metal)                           │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Virtual HID Bridge Layer                          │   │
│  │  • Creates /dev/input/eventX devices appearing as Logitech hardware  │   │
│  │  • Routes commands from Ubuntu VM to Windows VM                      │   │
│  │  • Adds human-like timing jitter at the lowest level                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│         ┌────────────────────┴────────────────────┐                        │
│         │                                         │                        │
│         ▼                                         ▼                        │
│  ┌─────────────────────────────┐    ┌─────────────────────────────┐       │
│  │   VM1: Ubuntu AI Controller │    │   VM2: Windows 10 Target    │       │
│  │   (192.168.100.101)         │    │   (192.168.100.100)         │       │
│  │                             │    │                             │       │
│  │  • Vision AI (Qwen-VL)      │    │  • Vanilla Windows 10       │       │
│  │  • OmniParser V2            │    │  • Chrome (logged in)       │       │
│  │  • Human mouse movement     │    │  • VNC Server (port 5900)   │       │
│  │  • Decision orchestration   │    │  • No automation tools      │       │
│  │  • Screen capture via VNC   │    │  • Real user fingerprint    │       │
│  └─────────────────────────────┘    └─────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Three Parallel Workstreams

This project has **three independent folders** that can be developed in parallel:

| Folder | Purpose | Owner | Dependencies |
|--------|---------|-------|--------------|
| `host/` | Proxmox host configuration, virtual HID devices | Host Agent | None |
| `ubu-cont/` | Ubuntu AI controller VM code | AI Agent | Interfaces from host/ |
| `w10-drivers/` | Windows 10 target VM setup | Windows Agent | None |

```
/proxmox-computer-control/
├── AGENTS.md                 # This file
├── README.md                 # Project overview
│
├── host/                     # Proxmox host configuration
│   ├── virtual-hid/          # Virtual input device creation
│   ├── network/              # VM bridge configuration
│   ├── services/             # Systemd services
│   └── scripts/              # Host management scripts
│
├── ubu-cont/                 # Ubuntu AI Controller VM
│   ├── src/                  # Main Python source
│   │   ├── vision/           # OmniParser, Qwen-VL integration
│   │   ├── input/            # Human-like mouse/keyboard
│   │   ├── capture/          # VNC screen capture
│   │   └── agent/            # Decision orchestration
│   ├── models/               # Downloaded AI models
│   ├── config/               # Configuration files
│   └── tests/                # Unit and integration tests
│
└── w10-drivers/              # Windows 10 Target VM
    ├── setup/                # Installation scripts
    ├── hardening/            # Security and anti-detection
    └── emergency/            # RDP/recovery access
```

---

## FOLDER 1: HOST (Proxmox Host Agent)

### Responsibilities
- Create virtual input devices that appear as Logitech hardware
- Route input commands from Ubuntu VM to Windows VM
- Configure internal VM network bridge
- Manage systemd services for virtual HID
- Handle USB passthrough configuration

### Files Owned
```
host/
├── virtual-hid/
│   ├── create_virtual_hid.py      # Creates /dev/input/eventX devices
│   ├── hid_controller.py          # Listens for commands, sends events
│   ├── device_descriptors.py      # USB HID report descriptors
│   └── logitech_spoofing.py       # Vendor/product ID spoofing
│
├── network/
│   ├── vmbr1_config.sh            # Internal bridge setup
│   └── firewall_rules.sh          # VM-to-VM communication
│
├── services/
│   ├── virtual-hid.service        # Systemd unit file
│   ├── input-router.service       # Command routing service
│   └── vnc-bridge.service         # Screen capture bridge
│
├── scripts/
│   ├── install.sh                 # Full installation script
│   ├── start_all.sh               # Start all services
│   ├── status.sh                  # Check system health
│   └── passthrough_usb.sh         # Configure USB passthrough
│
├── vm-configs/
│   ├── 100.conf.example           # Windows VM config template
│   └── 101.conf.example           # Ubuntu VM config template
│
└── tests/
    ├── test_virtual_device.py     # Verify device creation
    └── test_event_routing.py      # Verify command flow
```

### Interface Contract (What other agents depend on)

```python
# host/virtual-hid/hid_controller.py exposes:

# TCP Socket Interface (port 8888 for mouse, 8889 for keyboard)
# Ubuntu VM sends JSON commands to these ports

# Mouse Command Format:
{
    "type": "mouse_move",
    "x": int,          # Target X coordinate
    "y": int,          # Target Y coordinate
    "timestamp": str   # ISO format timestamp
}

{
    "type": "mouse_button",
    "button": str,     # "left", "right", "middle"
    "action": str,     # "down", "up"
    "timestamp": str
}

{
    "type": "mouse_wheel",
    "delta": int,      # Positive = down, negative = up
    "timestamp": str
}

# Keyboard Command Format:
{
    "type": "keyboard",
    "key": str,        # Key name or character
    "action": str,     # "down", "up", "press"
    "timestamp": str
}
```

### Development Tasks

1. **Virtual HID Device Creation**
   - Implement `/dev/uhid` device creation with Logitech vendor ID (0x046d)
   - Create proper USB HID report descriptors for mouse and keyboard
   - Ensure devices appear in `/dev/input/by-id/` with realistic names

2. **Command Router Service**
   - TCP socket listener on ports 8888 (mouse) and 8889 (keyboard)
   - Parse JSON commands from Ubuntu VM
   - Convert to evdev events and inject into virtual device
   - Add configurable jitter (1-5ms random delay) for human-like timing

3. **Network Bridge Configuration**
   - Create `vmbr1` internal bridge (192.168.100.0/24)
   - Configure firewall rules allowing VM-to-VM traffic only
   - Block external access to internal bridge

4. **USB Passthrough Setup**
   - Generate VM config snippets for USB device passthrough
   - Script to find and assign virtual devices to Windows VM

### Testing Without Other VMs
```bash
# Test virtual device creation
python3 host/virtual-hid/create_virtual_hid.py
ls -la /dev/input/by-id/ | grep -i logitech
# Expected: virtual device appears

# Test event injection
echo '{"type":"mouse_move","x":100,"y":100}' | nc localhost 8888
evtest /dev/input/eventX  # Watch for movement events

# Test device appears correctly
lsusb | grep -i logitech
# Expected: Logitech device with correct vendor ID
```

---

## FOLDER 2: UBU-CONT (Ubuntu AI Controller Agent)

### Responsibilities
- Capture Windows VM screen via VNC/Spice
- Run vision AI (OmniParser V2, Qwen-VL) to understand screen
- Generate human-like mouse trajectories with Fitts's Law timing
- Simulate human typing with realistic WPM and error patterns
- Make decisions about what actions to take
- Send commands to Proxmox host's virtual HID service

### Files Owned
```
ubu-cont/
├── src/
│   ├── __init__.py
│   │
│   ├── capture/
│   │   ├── __init__.py
│   │   ├── vnc_capturer.py        # VNC screen capture
│   │   ├── spice_capturer.py      # Spice protocol capture
│   │   └── frame_buffer.py        # Frame queue management
│   │
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── omniparser.py          # UI element detection
│   │   ├── qwen_vl.py             # Vision-language model
│   │   ├── ocr.py                 # Text extraction
│   │   └── element_tracker.py     # Track elements across frames
│   │
│   ├── input/
│   │   ├── __init__.py
│   │   ├── human_mouse.py         # Bezier curves, Fitts's Law
│   │   ├── human_keyboard.py      # WPM variation, typos
│   │   ├── trajectory_gen.py      # Movement path generation
│   │   ├── personal_profile.py    # Learn from user recordings
│   │   └── remote_sender.py       # Send to host HID service
│   │
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── main_agent.py          # Main orchestration loop
│   │   ├── task_manager.py        # Task queue and priorities
│   │   ├── decision_engine.py     # What to click/type next
│   │   └── state_machine.py       # Workflow state tracking
│   │
│   └── utils/
│       ├── __init__.py
│       ├── config.py              # Configuration loading
│       └── logging.py             # Structured logging
│
├── models/
│   ├── omniparser_v2.pt           # Downloaded model weights
│   └── .gitkeep
│
├── config/
│   ├── config.yaml                # Main configuration
│   ├── personal_profile.yaml      # Learned user behavior
│   └── credentials.yaml.example   # VNC/account credentials template
│
├── recordings/                     # Human demonstration recordings
│   ├── mouse_movements/           # Raw mouse trajectory captures
│   ├── typing_patterns/           # Keystroke timing data
│   └── .gitkeep
│
├── tests/
│   ├── test_capture.py
│   ├── test_vision.py
│   ├── test_human_mouse.py
│   ├── test_human_keyboard.py
│   └── test_agent.py
│
├── scripts/
│   ├── record_human.py            # Record real human for training
│   ├── install_models.sh          # Download AI models
│   └── start_agent.sh             # Launch agent
│
└── requirements.txt
```

### Interface Contract (What this agent provides)

```python
# src/capture/vnc_capturer.py
class VNCCapturer:
    def connect(host: str, port: int, password: str) -> None: ...
    def capture_frame() -> np.ndarray: ...  # Returns BGR numpy array
    def get_resolution() -> Tuple[int, int]: ...
    def disconnect() -> None: ...

# src/vision/omniparser.py
class OmniParser:
    def detect_elements(frame: np.ndarray) -> List[UIElement]: ...
    # UIElement has: type, label, bbox, center, confidence

# src/input/human_mouse.py
class HumanMouse:
    def move_to(x: int, y: int, duration: float = None) -> None: ...
    def click(button: str = "left", clicks: int = 1) -> None: ...
    def scroll(amount: int, direction: str = "down") -> None: ...
    def drag(start: Tuple, end: Tuple) -> None: ...

# src/input/human_keyboard.py
class HumanKeyboard:
    def type_text(text: str, wpm: int = 40) -> None: ...
    def press_key(key: str) -> None: ...
    def hotkey(*keys: str) -> None: ...

# src/agent/main_agent.py
class AIComputerAgent:
    def start() -> None: ...
    def stop() -> None: ...
    def add_task(task: Task) -> str: ...  # Returns task ID
    def get_status() -> Dict: ...
```

### Development Tasks

1. **VNC Screen Capture**
   - Connect to Windows VM VNC server (192.168.100.100:5900)
   - Capture frames at 30 FPS into a queue
   - Handle reconnection on disconnect
   - Convert to numpy arrays for vision processing

2. **Vision Processing Pipeline**
   - Integrate OmniParser V2 for UI element detection
   - Set up Ollama with Qwen-VL for complex reasoning
   - Extract text with EasyOCR for reading content
   - Track elements across frames for stability

3. **Human-Like Mouse Movement**
   - Implement Bezier curve trajectories
   - Apply Fitts's Law timing (harder targets = slower)
   - Add micro-jitter (±2-5 pixels) simulating muscle tremor
   - Include overshoot and correction near targets
   - Direction-specific acceleration (arm mechanics)

4. **Human-Like Keyboard Input**
   - Variable WPM (30-60 depending on text complexity)
   - Occasional typos with realistic backspace correction
   - Pauses between words and sentences
   - Burst typing for familiar patterns

5. **Personal Profile Learning**
   - Record real human mouse movements
   - Learn individual typing patterns (WPM, error rate)
   - Extract movement signature for replay
   - Store profiles in `config/personal_profile.yaml`

6. **Decision Engine**
   - Task-based action planning
   - Handle unexpected popups and dialogs
   - Recovery from errors (wrong page, missed click)
   - Rate limiting to avoid suspicious speed

### Testing Without Windows VM
```python
# Test human mouse trajectory generation (no VM needed)
from src.input.human_mouse import HumanMouse
mouse = HumanMouse(dry_run=True)  # Doesn't send commands
trajectory = mouse.plan_trajectory((0, 0), (500, 300))
assert len(trajectory) > 50  # Many points
assert trajectory[-1] == (500, 300)  # Reaches target

# Test vision with sample screenshot
from src.vision.omniparser import OmniParser
parser = OmniParser()
elements = parser.detect_elements(cv2.imread("test_screenshot.png"))
assert len(elements) > 0
```

---

## FOLDER 3: W10-DRIVERS (Windows 10 Target Agent)

### Responsibilities
- Clean Windows 10 installation with realistic user fingerprint
- VNC server configuration for screen capture
- Chrome with human browsing history and logged-in accounts
- Anti-detection hardening (disable telemetry, automation flags)
- Emergency RDP access for human intervention

### Files Owned
```
w10-drivers/
├── setup/
│   ├── base_install.ps1           # Post-install configuration
│   ├── install_vnc.ps1            # TightVNC setup
│   ├── install_chrome.ps1         # Chrome with extensions
│   └── create_accounts.ps1        # Set up user accounts
│
├── hardening/
│   ├── disable_telemetry.ps1      # Windows telemetry off
│   ├── disable_updates.ps1        # Prevent auto-updates
│   ├── anti_automation.ps1        # Remove automation indicators
│   ├── realistic_settings.ps1     # Timezone, locale, etc.
│   └── browser_hardening.ps1      # Chrome anti-fingerprinting
│
├── emergency/
│   ├── enable_rdp.ps1             # Emergency RDP access
│   ├── quick_recovery.ps1         # Fix common issues
│   └── snapshot_guide.md          # When to snapshot
│
├── fingerprint/
│   ├── browsing_history.md        # Guide to create history
│   ├── account_setup.md           # Account login guide
│   └── human_usage.md             # How to "season" the VM
│
├── drivers/
│   ├── virtio/                    # VirtIO driver ISOs
│   └── install_drivers.ps1        # Driver installation
│
├── tests/
│   ├── test_vnc_connection.ps1    # Verify VNC works
│   ├── test_input_devices.ps1     # Verify virtual HID
│   └── test_detection.ps1         # Check for automation leaks
│
└── checklists/
    ├── fresh_install.md           # New VM checklist
    └── pre_production.md          # Before running agent
```

### Development Tasks

1. **Base Windows Installation**
   - Windows 10 Pro 22H2 installation
   - VirtIO drivers for disk, network, display
   - QEMU guest agent for Proxmox integration
   - Set realistic computer name (not "DESKTOP-ABC123")

2. **VNC Server Setup**
   - Install TightVNC in service mode
   - Configure port 5900, password protection
   - Disable file transfers and remote input (capture only)
   - Firewall rule allowing only Ubuntu VM IP

3. **Chrome Configuration**
   - Install Chrome stable (not Chromium)
   - Extensions: uBlock Origin, Privacy Badger
   - Disable "controlled by automated software" flag
   - Log into Google account (creates trust score)

4. **Anti-Detection Hardening**
   - Disable WebRTC IP leak
   - Remove automation registry keys
   - Disable game mode (interferes with input)
   - Set realistic timezone and locale
   - Create human-like browsing history

5. **Emergency Access**
   - Enable RDP with Network Level Authentication
   - Create emergency admin account
   - Document snapshot/restore procedures

### Checklist Scripts
```powershell
# test_detection.ps1 - Check for automation indicators
$checks = @{
    "WebDriver flag" = !(Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Edge" -Name WebDriver -ErrorAction SilentlyContinue)
    "Chrome automation" = !(Test-Path "HKLM:\SOFTWARE\Policies\Google\Chrome\CommandLineFlagSecurityWarningsEnabled")
    "VNC running" = (Get-Service "tvnserver" -ErrorAction SilentlyContinue).Status -eq "Running"
    "Updates disabled" = (Get-Service "wuauserv").StartType -eq "Disabled"
}

$checks.GetEnumerator() | ForEach-Object {
    Write-Host "$($_.Key): $(if ($_.Value) { 'PASS' } else { 'FAIL' })"
}
```

---

## Communication Between Agents

### Runtime Data Flow
```
┌─────────────────┐     VNC/Spice      ┌─────────────────┐
│  Windows 10 VM  │ ───────────────────▶│  Ubuntu AI VM   │
│  (w10-drivers)  │     Screen          │  (ubu-cont)     │
└─────────────────┘                     └────────┬────────┘
        ▲                                        │
        │                                        │
        │  Virtual HID Events                    │ JSON Commands
        │  (USB mouse/keyboard)                  │ (TCP socket)
        │                                        │
        └────────────────────────────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Proxmox Host      │
              │   (host/)           │
              │                     │
              │   hid_controller.py │
              │   port 8888 (mouse) │
              │   port 8889 (kbd)   │
              └─────────────────────┘
```

### Development-Time Independence

During development, agents work independently:

| Agent | Can Develop Without | Uses Mock/Stub |
|-------|---------------------|----------------|
| Host | Ubuntu VM, Windows VM | Local evtest for verification |
| Ubuntu AI | Windows VM | Sample screenshots, dry-run mode |
| Windows 10 | Ubuntu VM, Host | Manual verification |

---

## Safety and Detection Avoidance

### Human Behavior Parameters

```yaml
# config/personal_profile.yaml (learned from real user)
mouse:
  min_movement_duration_ms: 100
  max_movement_duration_ms: 800
  overshoot_probability: 0.15
  jitter_pixels: 3
  fitts_law_a: 50    # Intercept
  fitts_law_b: 150   # Slope

keyboard:
  base_wpm: 45
  wpm_variance: 10
  typo_rate: 0.02
  backspace_correction_delay_ms: 200
  burst_pattern_words: ["the", "and", "is", "to"]

timing:
  min_think_time_ms: 300
  max_think_time_ms: 2000
  double_click_interval_ms: 100
  scroll_pause_ms: 50
```

### Detection Vectors to Avoid

| Detection Method | Our Solution |
|------------------|--------------|
| Mouse device ID check | Virtual device uses Logitech vendor ID (0x046d) |
| Polling rate analysis | Set to 125Hz (standard), not 1000Hz (gaming) |
| Movement trajectory | Bezier curves with Fitts's Law timing |
| Click timing | Random delays (50-200ms) between actions |
| Typing speed | Variable WPM with realistic pauses |
| Input stack inspection | Virtual USB indistinguishable from physical |
| Browser automation flags | No automation tools on Windows VM |
| CDP artifacts | No Chrome DevTools Protocol used |

---

## Startup Sequence

### 1. Start Proxmox Host Services
```bash
# On Proxmox host
cd /opt/proxmox-computer-control/host
./scripts/start_all.sh
# Expected: Virtual HID service running on ports 8888, 8889
```

### 2. Start Windows VM
```bash
qm start 100
# Wait 2-3 minutes for full boot
# Verify VNC accessible
```

### 3. Start Ubuntu AI Controller
```bash
qm start 101
ssh ubuntu@192.168.100.101
cd ~/proxmox-computer-control/ubu-cont
source venv/bin/activate
python -m src.agent.main_agent
```

### 4. Monitor System
```bash
# On host
journalctl -u virtual-hid -f

# On Ubuntu VM
tail -f logs/agent.log

# On Windows VM (via RDP if needed)
# Just observe - no automation tools visible
```

---

## Quick Reference: Who Owns What

| Component | Owner Agent | Others Can |
|-----------|-------------|------------|
| `/dev/input/eventX` creation | Host | Read events |
| TCP socket protocol | Host | Send commands |
| VNC capture | Ubuntu AI | Read only |
| Vision models | Ubuntu AI | N/A |
| Mouse trajectory generation | Ubuntu AI | N/A |
| Windows configuration | Windows 10 | View via VNC |
| Chrome accounts | Windows 10 | Control via AI |

---

## Parallel Development Schedule

### Week 1: Foundation
| Day | Host Agent | Ubuntu AI Agent | Windows Agent |
|-----|------------|-----------------|---------------|
| 1-2 | Virtual HID device creation | VNC capture | Base Windows install |
| 3-4 | Socket command router | Human mouse lib | VNC server setup |
| 5 | USB passthrough config | Human keyboard lib | Chrome install |

### Week 2: Integration
| Day | Integration Task |
|-----|------------------|
| 1 | Host → Ubuntu: Verify command routing |
| 2 | Ubuntu → Windows: Verify VNC capture |
| 3 | Full loop: Capture → Decide → Act |
| 4 | Personal profile recording |
| 5 | End-to-end testing |

---

## Emergency Procedures

### Windows VM Flagged/Banned
1. Stop Ubuntu AI agent
2. Create Proxmox snapshot
3. Analyze what triggered detection
4. Restore to clean snapshot
5. Adjust behavior parameters
6. Re-season with human usage

### Ubuntu VM Crash
1. Check journalctl logs
2. Verify Ollama is running
3. Restart agent service
4. If persistent, restore snapshot

### Host Service Failure
1. Check virtual device exists: `ls /dev/input/by-id/`
2. Verify socket listening: `netstat -tlnp | grep 888`
3. Restart service: `systemctl restart virtual-hid`

---

## File Ownership Rules

Each agent has **exclusive write access** to their owned directories:

- **Host Agent**: Only modifies files in `host/`
- **Ubuntu AI Agent**: Only modifies files in `ubu-cont/`
- **Windows Agent**: Only modifies files in `w10-drivers/`

**Shared files** (read-only for all):
- `AGENTS.md` (this file)
- `README.md`

Changes to shared files require coordination between agents.

# CRITICAL: Windows PowerShell Compatibility

This project runs on Windows PowerShell 5.1 which does NOT support `&&` for command chaining.

**ALWAYS use semicolons (;) instead of && when chaining commands:**
- ❌ `git add -A && git commit -m "msg"`  
- ✅ `git add -A; git commit -m "msg"`

Or use pwsh explicitly:
- ✅ `pwsh -Command "git add -A && git commit -m 'msg'"`