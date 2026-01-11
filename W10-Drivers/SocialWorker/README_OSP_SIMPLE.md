# Simplified On-Screen Prompter (OSP)

## Overview

The Simplified OSP is a **dumb control panel** - a simple Python GUI that provides clipboard services and status reporting for social media posting. It displays static buttons in predictable locations that the Ubuntu AI controller uses vision to find and click.

## What It Does

1. **Fetches** post data from the Social Dashboard API
2. **Displays** static buttons (labels never change)
3. **Handles** clipboard operations when buttons are clicked
4. **Reports** success/failure back to the API

## What It Does NOT Do

- ❌ Make decisions about posting workflow
- ❌ Change button labels dynamically
- ❌ Use WebSockets or Chrome extensions
- ❌ Track state machines or posting steps
- ❌ Have any "intelligence"

**The Ubuntu controller uses vision to find and click these buttons. The OSP just provides services.**

## Installation

### 1. Install Dependencies

```powershell
cd C:\Users\ultra\Development\ProxMox\W10-Drivers\SocialWorker
pip install -r requirements_osp_simple.txt
```

### 2. Verify Installation

```powershell
python -c "import tkinter; import pyperclip; import requests; from PIL import Image; print('All dependencies OK')"
```

## Running the OSP

### Manual Start

```powershell
python osp_simple.py
```

The window will appear on the right edge of your screen with all buttons visible.

### Auto-Start with Windows

Run the provided PowerShell script to create a startup shortcut:

```powershell
.\setup_osp_autostart.ps1
```

Or manually create a shortcut:
1. Press `Win+R` and type `shell:startup`
2. Right-click → New → Shortcut
3. Target: `pythonw.exe C:\Users\ultra\Development\ProxMox\W10-Drivers\SocialWorker\osp_simple.py`
4. Name it "OSP Simple"

## GUI Layout

```
┌──────────────────────────────────┐
│         SOCIAL POSTER            │  ← Title bar
├──────────────────────────────────┤
│  Platform: Instagram             │  ← Current platform
│  Post ID: abc123                 │  ← Post identifier
├──────────────────────────────────┤
│                                  │
│  ┌────────────────────────────┐  │
│  │       OPEN URL             │  │  ← Opens platform URL
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY TITLE           │  │  ← Copies title
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY BODY            │  │  ← Copies body
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY IMAGE           │  │  ← Copies image
│  └────────────────────────────┘  │
│                                  │
│  ☐ Send Email Notification       │
│                                  │
│  ┌────────────────────────────┐  │
│  │          POST              │  │  ← Signals ready
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────┐ ┌────────────┐   │
│  │  SUCCESS   │ │   FAILED   │   │  ← Status buttons
│  │     ✓      │ │     ✗      │   │
│  └────────────┘ └────────────┘   │
│                                  │
├──────────────────────────────────┤
│  Status: Waiting for action...   │
└──────────────────────────────────┘
```

## Button Specifications

| Button | Label (NEVER CHANGES) | Color | Action |
|--------|----------------------|-------|--------|
| Open URL | "OPEN URL" | Blue | Opens platform URL in default browser |
| Copy Title | "COPY TITLE" | Blue | Copies title to clipboard |
| Copy Body | "COPY BODY" | Blue | Copies body text to clipboard |
| Copy Image | "COPY IMAGE" | Blue | Copies image to clipboard |
| Post | "POST" | Orange | Signals workflow ready for posting |
| Success | "✓ SUCCESS" | Green | Reports success to API |
| Failed | "✗ FAILED" | Red | Reports failure to API |

## Window Properties

- **Size:** 300px × 550px (not resizable)
- **Position:** Right edge of screen
- **Always on top:** Yes
- **Background:** Dark gray (#2d2d2d)
- **Button height:** 50px each
- **Button font:** Bold, 12-14pt, White

## API Configuration

The OSP connects to: `https://social.sterlingcooley.com/api`

Endpoints used:
- `GET /gui_post_queue/pending` - Fetch next post (polled every 10 seconds)
- `POST /gui_post_queue/{id}/posting` - Signal posting started
- `POST /gui_post_queue/{id}/complete` - Report success
- `POST /gui_post_queue/{id}/failed` - Report failure

## Directory Structure

```
C:\PostQueue\
├── temp_image.png         # Temp file for clipboard operations
└── (other queue files)
```

## Testing

### Test 1: Window Appears Correctly
```powershell
python osp_simple.py
# Expected: Window on right side with all buttons visible
```

### Test 2: Clipboard Operations
Click each button manually and verify:
- Title copies to clipboard
- Body copies to clipboard
- Image copies to clipboard (paste in Paint to verify)

### Test 3: API Integration
```powershell
# Create a test post via the API
# OSP should pick it up within 10 seconds
```

## Troubleshooting

### Window Not Visible
```powershell
# Check if process is running
Get-Process python* | Select-Object Id, ProcessName, MainWindowTitle

# Kill and restart
Get-Process python* | Stop-Process -Force
python osp_simple.py
```

### Clipboard Not Working
```powershell
# Test clipboard manually
python -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"
# Expected: test
```

### Image Copy Failing
```powershell
# Verify PowerShell can copy images
Add-Type -AssemblyName System.Windows.Forms
$image = [System.Drawing.Image]::FromFile("C:\path\to\test.jpg")
[System.Windows.Forms.Clipboard]::SetImage($image)
# Should not throw error
```

### API Connection Issues
```powershell
# Test API endpoint
curl "https://social.sterlingcooley.com/api/gui_post_queue/pending"
# Expected: JSON response (may be empty array)
```

## How Ubuntu Uses the OSP

The Ubuntu AI controller:
1. Uses **vision** to find OSP buttons by their labels
2. **Clicks** buttons to trigger clipboard operations
3. **Pastes** content into platform fields
4. **Clicks** SUCCESS or FAILED to complete the workflow

Example workflow:
```python
# Ubuntu controller (simplified)
vision.find_and_click("OPEN URL blue button")
time.sleep(3)

vision.find_and_click("COPY TITLE blue button")
vision.find_and_click("Instagram title field")
keyboard.paste()

vision.find_and_click("COPY BODY blue button")
vision.find_and_click("Instagram caption field")
keyboard.paste()

vision.find_and_click("COPY IMAGE blue button")
vision.find_and_click("Instagram upload button")
keyboard.paste()

vision.find_and_click("POST orange button")
vision.find_and_click("Instagram Share button")

# Wait and verify
if post_successful:
    vision.find_and_click("SUCCESS green button")
else:
    vision.find_and_click("FAILED red button")
```

## Differences from Old OSP

| Old OSP | New Simplified OSP |
|---------|-------------------|
| PyQt6 with complex UI | Simple tkinter |
| WebSocket to Chrome extension | No WebSocket |
| Dynamic button labels | Static labels (never change) |
| Step-by-step state machine | No state tracking |
| "Smart" decision making | "Dumb" control panel |
| Auto-advance workflow | Independent button actions |

## Key Design Principles

1. **Static Labels** - Button text NEVER changes
2. **Independent Actions** - Each button does ONE thing
3. **No State Tracking** - OSP doesn't know what step we're on
4. **Dumb Panel** - Zero decision-making logic
5. **Vision-Friendly** - High contrast, predictable layout

## Emergency Procedures

### Kill OSP
```powershell
Get-Process python* | Where-Object {$_.MainWindowTitle -like "*Social Poster*"} | Stop-Process
```

### Reset OSP
```powershell
# Delete any stuck temp files
Remove-Item C:\PostQueue\temp_image.png -ErrorAction SilentlyContinue

# Restart
python osp_simple.py
```

## Support

For issues or questions, refer to:
- Main documentation: `W10-Drivers/docs/WS10-OSP-PYTHON-FIX.md`
- Project overview: `AGENTS.md`
