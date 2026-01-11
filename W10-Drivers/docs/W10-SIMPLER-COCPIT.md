# WINDOWS10-AGENT-INSTRUCTIONS.md
# Windows 10 VM - Simplified Cockpit Role

## What Changed: A Learning Moment

### The Original Vision (Overly Ambitious)
We built an elaborate system hoping that:
- A computer vision model running on Windows 10 could read on-screen instructions
- The On-Screen Prompter (OSP) would display guidance that the AI would "understand"
- Windows 10 would have local AI intelligence making decisions about what to click
- The Chrome extension overlays would serve as a communication channel to the AI

### What We Learned
**Computer vision models are "eyes" not "brains."** They excel at:
- Identifying UI elements (buttons, text fields, links)
- Reading text from images (OCR)
- Describing what's on screen
- Finding specific visual elements when asked

They do NOT excel at:
- Reading instructions and deciding to follow them
- Understanding context of a multi-step workflow
- Maintaining state about "what step am I on"
- Autonomously reasoning about next actions

**The OSP overlays were solving the wrong problem.** We created visual prompts hoping the AI would read them, but the AI needs to be told what to find, not shown instructions to interpret.

---

## New Role: Windows 10 as Passive Cockpit

```
┌─────────────────────────────────────────────────────────────────┐
│                    BEFORE (Complex)                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Windows 10 VM                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Local AI + Vision Model                                │   │
│   │  Chrome Extension with OSP Overlays                     │   │
│   │  Python Orchestrator                                    │   │
│   │  Fetcher polling for tasks                              │   │
│   │  Decision-making about what to click                    │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

                              ↓ SIMPLIFY ↓

┌─────────────────────────────────────────────────────────────────┐
│                    AFTER (Simple)                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Windows 10 VM                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  Chrome browser (logged into social media accounts)     │   │
│   │  VNC server (so Ubuntu can see the screen)              │   │
│   │  Input receiver (accepts mouse/keyboard from Ubuntu)    │   │
│   │  Content staging folder (C:\PostQueue\)                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   That's it. No AI. No decision-making. Just a remote desktop.  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## What to Keep

### 1. VNC Server
**Status: KEEP - Essential**

Ubuntu needs to see the Windows 10 screen. VNC provides this visibility.

```
Current Setup:
- VNC Server running on Windows 10
- Accessible at 192.168.100.20:5900 (or configured port)
- Ubuntu captures screenshots via VNC
```

**Verification:**
```powershell
# Check VNC service is running
Get-Service -Name "*vnc*" | Format-Table Name, Status
# Expected: Running

# Verify VNC port is listening
netstat -an | findstr ":5900"
# Expected: LISTENING
```

### 2. Content Staging Folder
**Status: KEEP - Essential**

Media files need to be accessible for upload dialogs.

```
C:\PostQueue\
├── pending\          # New content placed here
│   ├── image1.jpg
│   ├── video1.mp4
│   └── ...
├── processing\       # Currently being posted (moved here during workflow)
└── completed\        # Successfully posted (archived)
```

**Verification:**
```powershell
# Verify folder structure exists
Test-Path C:\PostQueue\pending
Test-Path C:\PostQueue\processing
Test-Path C:\PostQueue\completed
# Expected: True for all
```

### 3. Chrome Browser with Saved Logins
**Status: KEEP - Essential**

All social media accounts should be logged in and sessions saved.

**Required logins:**
- Instagram (instagram.com)
- Facebook (facebook.com)
- TikTok (tiktok.com)
- Skool (skool.com)

**Verification:**
- Manually open Chrome
- Navigate to each platform
- Confirm you're logged in
- Ensure "Remember me" / stay logged in is enabled

### 4. QMP/Input Receiver (Proxmox Side)
**Status: KEEP - Essential**

The input pipeline from Ubuntu → Proxmox → Windows 10 must remain functional.

```
Ubuntu (192.168.100.10)
    │
    │ HTTP POST to port 8888
    ▼
Proxmox Host (192.168.100.1)
    │
    │ QMP commands to VM
    ▼
Windows 10 VM (192.168.100.20)
    │
    │ Virtual HID input
    ▼
Mouse/Keyboard actions in VM
```

---

## What to Disable/Remove

### 1. Local AI/Ollama (if installed)
**Status: DISABLE - Not needed**

Windows 10 no longer needs to run AI models. All inference happens on Ubuntu.

```powershell
# Stop Ollama if running
Stop-Service Ollama -ErrorAction SilentlyContinue

# Disable auto-start
Set-Service Ollama -StartupType Disabled -ErrorAction SilentlyContinue

# Optional: Uninstall to free resources
# winget uninstall Ollama
```

### 2. Python Fetcher/Orchestrator Scripts
**Status: DISABLE - Not needed**

The Windows fetcher that polls the API is no longer needed. Ubuntu handles all orchestration.

```powershell
# Stop any running Python automation scripts
Get-Process python* | Stop-Process -Force -ErrorAction SilentlyContinue

# Remove from startup if configured
# Check Task Scheduler for automation tasks
Get-ScheduledTask | Where-Object {$_.TaskName -like "*fetcher*" -or $_.TaskName -like "*automation*"}
```

**Don't delete the code** - keep it archived in case we need to reference it later.

```powershell
# Archive the old code
$archiveDate = Get-Date -Format "yyyy-MM-dd"
Rename-Item C:\Automation C:\Automation-archived-$archiveDate -ErrorAction SilentlyContinue
```

### 3. On-Screen Prompter (OSP) System
**Status: DISABLE - Not needed in current form**

The OSP overlays were designed for an AI to read. Since AI doesn't read instructions this way, the overlays serve no purpose.

**Chrome Extension:**
```
1. Open Chrome
2. Go to chrome://extensions/
3. Find the OSP/automation extension
4. Toggle OFF (disable) but don't remove yet
```

**Python OSP Coordinator:**
```powershell
# Stop OSP processes
Get-Process | Where-Object {$_.ProcessName -like "*osp*"} | Stop-Process -Force
```

### 4. Local Vision Processing
**Status: REMOVE - Moved to Ubuntu**

Any screen capture or vision processing on Windows 10 is now redundant.

```powershell
# Stop BetterCam or screen capture processes
Get-Process | Where-Object {$_.ProcessName -like "*capture*" -or $_.ProcessName -like "*screen*"} | Stop-Process -Force
```

---

## Minimal Windows 10 Configuration

After cleanup, Windows 10 should have:

### Running Services
| Service | Purpose | Port |
|---------|---------|------|
| VNC Server | Screen sharing to Ubuntu | 5900 |
| RDP (optional) | Manual admin access | 3389 |

### Running Applications
| Application | State |
|-------------|-------|
| Chrome | Running, logged into all platforms |
| Explorer | Open to C:\PostQueue\pending |

### Startup Programs
| Program | Should Auto-Start |
|---------|-------------------|
| VNC Server | Yes |
| Chrome | Optional (Ubuntu can launch it) |
| Ollama | No - disabled |
| Python scripts | No - disabled |

---

## How Ubuntu Controls Windows 10

Windows 10 is now a **remote desktop** controlled entirely by Ubuntu. Here's the flow:

### 1. Ubuntu Captures Screen
```
Ubuntu → VNC → Screenshot of Windows 10 desktop
```

### 2. Ubuntu Analyzes with Vision
```
Ubuntu runs Qwen2.5-VL on the screenshot
"Find the blue Post button" → Returns coordinates (x=500, y=300)
```

### 3. Ubuntu Sends Input Commands
```
Ubuntu → HTTP → Proxmox (port 8888) → QMP → Windows 10 VM
Result: Mouse moves to (500, 300) and clicks
```

### 4. Ubuntu Verifies Result
```
Ubuntu → VNC → New screenshot
Ubuntu runs vision check: "Is the upload dialog visible?" → Yes/No
```

**Windows 10 has no awareness of this.** It just receives input as if a human was using it.

---

## Testing the Simplified Setup

### Test 1: VNC Screenshot Works
From Ubuntu:
```bash
# Using vncsnapshot or similar tool
vncsnapshot 192.168.100.20:0 /tmp/test_capture.png

# Verify file was created
ls -la /tmp/test_capture.png
# Expected: File exists with recent timestamp
```

### Test 2: Input Injection Works
From Ubuntu:
```bash
# Send a test mouse move via your Proxmox API
curl -X POST http://192.168.100.1:8888/mouse/move \
  -H "Content-Type: application/json" \
  -d '{"x": 500, "y": 500}'

# Expected: Mouse cursor moves on Windows 10
```

### Test 3: Keyboard Input Works
From Ubuntu:
```bash
# Click on a text field first, then type
curl -X POST http://192.168.100.1:8888/keyboard/type \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Ubuntu"}'

# Expected: Text appears in focused field on Windows 10
```

### Test 4: Content Files Accessible
On Windows 10:
```powershell
# Place a test image
Copy-Item C:\Users\*\Pictures\sample.jpg C:\PostQueue\pending\test.jpg

# Verify
Get-ChildItem C:\PostQueue\pending\
# Expected: test.jpg listed
```

---

## Maintaining the System

### Daily Checks
1. **VNC running?** - Ubuntu can capture screenshots
2. **Chrome logged in?** - Sessions haven't expired
3. **Disk space OK?** - PostQueue folders not filling up

### Weekly Maintenance
1. Clear C:\PostQueue\completed\ of old files
2. Verify social media sessions still active
3. Check Windows Updates haven't broken anything

### If Something Breaks

**VNC stops working:**
```powershell
# Restart VNC service
Restart-Service *vnc*

# If service won't start, check firewall
Get-NetFirewallRule | Where-Object {$_.DisplayName -like "*VNC*"}
```

**Chrome logged out:**
- Manually log back in
- Enable "Remember me" options
- Consider using Chrome profiles for each platform

**Input not working:**
- Check Proxmox QMP service
- Verify network connectivity on vmbr1 bridge
- Test with simpler commands first

---

## Summary: Windows 10's New Identity

| Before | After |
|--------|-------|
| Running local AI | No AI - just a browser |
| Making decisions | Receiving commands |
| Complex Python orchestration | Simple VNC + input receiver |
| OSP overlays for AI | No overlays needed |
| Active participant | Passive display |

**Think of Windows 10 as a TV screen with a remote control.** Ubuntu is holding the remote. Windows 10 just displays what's on screen and responds to button presses. All the "thinking" happens on Ubuntu.

---

## Files to Archive (Don't Delete Yet)

Keep these in an archive folder in case we need to reference them:

```
C:\Archive-YYYYMMDD\
├── Automation\              # Old Python scripts
├── OSP\                     # On-Screen Prompter code
├── ChromeExtension\         # Extension source
└── Documentation\           # Any related docs
```

Archive command:
```powershell
$date = Get-Date -Format "yyyyMMdd"
New-Item -ItemType Directory -Path "C:\Archive-$date" -Force

Move-Item C:\Automation "C:\Archive-$date\Automation" -ErrorAction SilentlyContinue
Move-Item C:\OSP "C:\Archive-$date\OSP" -ErrorAction SilentlyContinue
# Add other paths as needed
```

---

## Final Checklist

Before considering Windows 10 "ready":

- [ ] VNC server running and accessible from Ubuntu
- [ ] Chrome open with all social accounts logged in
- [ ] C:\PostQueue\ folder structure exists
- [ ] Old automation scripts stopped/disabled
- [ ] Ollama disabled (if was installed)
- [ ] OSP/Chrome extension disabled
- [ ] Test screenshot from Ubuntu works
- [ ] Test mouse move from Ubuntu works
- [ ] Test keyboard input from Ubuntu works

Once complete, Windows 10 is ready to be the "cockpit" for Ubuntu's automated social media posting.