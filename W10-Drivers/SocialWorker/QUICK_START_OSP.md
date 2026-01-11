# Quick Start Guide - Simplified OSP

## What is the Simplified OSP?

A **simple Python GUI** with static buttons that:
- Displays post data from the Social Dashboard API
- Provides clipboard copy services (title, body, image)
- Reports success/failure back to the API
- Is controlled by the Ubuntu AI using computer vision

**It's a "dumb control panel" - no intelligence, no state machine, just services.**

## Installation (5 Minutes)

### Step 1: Install Dependencies

```powershell
cd C:\Users\ultra\Development\ProxMox\W10-Drivers\SocialWorker
pip install -r requirements_osp_simple.txt
```

### Step 2: Test Installation

```powershell
python test_osp_simple.py
```

Expected output: All tests pass ✓

### Step 3: Run OSP

```powershell
python osp_simple.py
```

The window will appear on the right side of your screen.

## What You'll See

```
┌──────────────────────────────────┐
│      SOCIAL POSTER               │
│  Platform: --                    │
│  Post ID: --                     │
├──────────────────────────────────┤
│  [ OPEN URL ]         (blue)     │
│  [ COPY TITLE ]       (blue)     │
│  [ COPY BODY ]        (blue)     │
│  [ COPY IMAGE ]       (blue)     │
│  ☐ Send Email Notification       │
│  [ POST ]             (orange)   │
│  [ ✓ SUCCESS ] [ ✗ FAILED ]      │
│  (green)       (red)              │
├──────────────────────────────────┤
│  Status: Waiting for post...     │
└──────────────────────────────────┘
```

## Button Guide

| Button | What It Does | When to Click |
|--------|--------------|---------------|
| **OPEN URL** | Opens the platform URL in your browser | First - opens Instagram/Facebook/etc |
| **COPY TITLE** | Copies post title to clipboard | When you need the title |
| **COPY BODY** | Copies post body/caption to clipboard | When you need the body text |
| **COPY IMAGE** | Copies image to clipboard | When you need the image |
| **POST** | Signals you're ready to post | Before clicking platform's Post button |
| **✓ SUCCESS** | Reports successful post to API | After post is live |
| **✗ FAILED** | Reports failed post to API | If post failed |

## How It Works

### 1. OSP Polls for New Posts
Every 10 seconds, the OSP checks the API for new posts to make.

### 2. Post Loads into OSP
When a post is available:
- Platform name displays (e.g., "Instagram")
- Post ID displays
- All buttons become enabled
- Status shows "Post loaded - ready for action"

### 3. You (or Ubuntu AI) Click Buttons
- Click **OPEN URL** → Browser opens to platform
- Click **COPY TITLE** → Title is in clipboard (Ctrl+V to paste)
- Click **COPY BODY** → Body is in clipboard
- Click **COPY IMAGE** → Image is in clipboard (paste into image upload)
- Click **POST** → Signals you're ready
- After posting on the platform, click **SUCCESS** or **FAILED**

### 4. Post Completes
- Success/failure reported to API
- OSP clears the post
- Status returns to "Waiting for post..."

## Testing Manually

### Test Clipboard Copy
1. Start OSP: `python osp_simple.py`
2. Create a test post via API (or wait for one)
3. Click **COPY TITLE**
4. Open Notepad and press Ctrl+V
5. You should see the title text

### Test Image Copy
1. Click **COPY IMAGE** in OSP
2. Open Paint
3. Press Ctrl+V
4. Image should appear

### Test Status Reporting
1. Click **SUCCESS** or **FAILED**
2. Check status bar - should show "Success reported!" or "Failure reported"
3. Post should clear from OSP

## Auto-Start on Windows Boot

Run this once:
```powershell
.\setup_osp_autostart.ps1
```

This creates a startup shortcut. OSP will launch automatically when Windows starts.

## Troubleshooting

### "Module not found" error
```powershell
pip install -r requirements_osp_simple.txt
```

### Window not appearing
```powershell
# Check if already running
Get-Process python* | Where-Object {$_.MainWindowTitle -like "*Social*"}

# Kill and restart
Get-Process python* | Stop-Process -Force
python osp_simple.py
```

### Clipboard not working
```powershell
# Test clipboard manually
python -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"
```

### Image copy failing
Make sure `C:\PostQueue` directory exists:
```powershell
New-Item -ItemType Directory -Path C:\PostQueue -Force
```

### API not connecting
```powershell
# Test API manually
curl https://social.sterlingcooley.com/api/gui_post_queue/pending
```

## Differences from Old OSP

| Old OSP (osp_gui.py) | New OSP (osp_simple.py) |
|----------------------|-------------------------|
| PyQt6 (complex) | tkinter (simple) |
| 1523 lines | 500 lines |
| WebSockets | No WebSockets |
| Chrome extension | No extension |
| Dynamic button labels | Static labels |
| Step-by-step wizard | Independent buttons |
| State machine | No state tracking |

## For Ubuntu AI Controller

The Ubuntu controller will:
1. Use **vision** (OmniParser, Qwen-VL) to find buttons by label
2. **Click** buttons with human-like mouse movement
3. **Navigate** between OSP and browser windows
4. **Verify** success and click appropriate status button

Example vision prompts:
- "Find the blue button that says COPY TITLE"
- "Find the orange POST button"
- "Find the green SUCCESS button"

## Configuration

### Change API URL
Edit `osp_simple.py`, line 43:
```python
API_BASE_URL = "https://your-api-url.com/api"
```

### Change Poll Interval
Edit `osp_simple.py`, line 44:
```python
POLL_INTERVAL = 10  # seconds between API checks
```

### Change Window Position
Edit `osp_simple.py`, line 77:
```python
# Change x_position calculation for different placement
x_position = screen_width - self.WINDOW_WIDTH - 10  # Right edge
```

## Files Created

```
SocialWorker/
├── osp_simple.py                   # Main OSP application
├── requirements_osp_simple.txt     # Dependencies
├── test_osp_simple.py              # Test suite
├── setup_osp_autostart.ps1         # Auto-start setup
├── README_OSP_SIMPLE.md            # Full documentation
└── QUICK_START_OSP.md              # This file
```

## Next Steps

1. ✅ Install dependencies
2. ✅ Run test suite
3. ✅ Launch OSP manually
4. ✅ Test clipboard operations
5. ✅ Set up auto-start (optional)
6. 🔄 Integrate with Ubuntu AI controller

## Support Files

- **Full docs:** `README_OSP_SIMPLE.md`
- **Architecture:** `W10-Drivers/docs/WS10-OSP-PYTHON-FIX.md`
- **Project overview:** `AGENTS.md`

---

**That's it! The OSP is now a simple, vision-friendly control panel.** 🎉
