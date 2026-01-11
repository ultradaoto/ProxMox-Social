# Migration from Old OSP to Simplified OSP

## Overview

The On-Screen Prompter has been simplified from a complex PyQt6 application with WebSockets and state machines to a simple tkinter-based "dumb control panel" with static buttons.

## Files

### New Files (Use These)
- **`osp_simple.py`** - The new simplified OSP application
- **`requirements_osp_simple.txt`** - Dependencies for simplified version
- **`test_osp_simple.py`** - Test suite
- **`setup_osp_autostart.ps1`** - Auto-start setup script
- **`README_OSP_SIMPLE.md`** - Full documentation
- **`QUICK_START_OSP.md`** - Quick start guide

### Old Files (Preserved for Reference)
- **`osp_gui.py`** - The old complex OSP (1523 lines, PyQt6)
- **`requirements.txt`** - Original dependencies (includes PyQt6, websockets, etc.)
- **`setup_osp.ps1`** - Old setup script

## Key Differences

| Aspect | Old OSP | New Simplified OSP |
|--------|---------|-------------------|
| **UI Framework** | PyQt6 | tkinter (built-in) |
| **Lines of Code** | 1,523 | ~500 |
| **Communication** | WebSocket to Chrome extension | Direct API polling |
| **Button Behavior** | Dynamic labels (wizard-style) | Static labels (never change) |
| **State Management** | Complex state machine | No state tracking |
| **Intelligence** | "Smart" workflow automation | "Dumb" control panel |
| **Dependencies** | 9 packages | 3 packages |
| **Installation** | Complex | Simple |

## Why Simplify?

### Problems with Old OSP

1. **Dynamic buttons confuse vision AI**
   - Button labels changed during workflow
   - Vision system couldn't reliably find buttons
   - Needed constant re-detection

2. **Intelligence in wrong place**
   - OSP tried to orchestrate workflow
   - Ubuntu controller should make all decisions
   - Conflicting control logic

3. **Over-engineered**
   - WebSocket server for Chrome extension
   - Not needed - OSP can just use clipboard
   - Added complexity without benefit

4. **Hard to maintain**
   - 1,523 lines of code
   - Complex state machines
   - Many failure points

### Benefits of New OSP

1. **Vision-friendly**
   - Static button labels
   - Predictable layout
   - High contrast colors
   - Always in same location

2. **Clear responsibility**
   - OSP: provides services (clipboard, status reporting)
   - Ubuntu: makes all decisions (what to click, when)
   - No confusion about control flow

3. **Simple and reliable**
   - 500 lines vs 1,523
   - No WebSockets, no state machines
   - Each button does ONE thing
   - Easy to test and debug

4. **Easy to install**
   - Only 3 dependencies
   - tkinter is built-in
   - No system-level packages

## Migration Steps

### For Manual Testing

1. **Stop old OSP** (if running)
   ```powershell
   Get-Process python* | Where-Object {$_.MainWindowTitle -like "*OSP*"} | Stop-Process
   ```

2. **Install new dependencies**
   ```powershell
   pip install -r requirements_osp_simple.txt
   ```

3. **Test new OSP**
   ```powershell
   python test_osp_simple.py
   ```

4. **Run new OSP**
   ```powershell
   python osp_simple.py
   ```

### For Ubuntu AI Controller

Update the Ubuntu controller to use vision to find static button labels:

**Old approach (don't use):**
```python
# Old: WebSocket commands
await websocket.send(json.dumps({"action": "next_step"}))
```

**New approach (use this):**
```python
# New: Vision-based button finding
button = vision.find_element(screenshot, "COPY TITLE blue button")
mouse.click(button.x, button.y)
```

## API Compatibility

The simplified OSP uses the same API endpoints:
- `GET /gui_post_queue/pending`
- `POST /gui_post_queue/{id}/posting`
- `POST /gui_post_queue/{id}/complete`
- `POST /gui_post_queue/{id}/failed`

**No backend changes required.**

## Data Format

### Post Data Structure (Same)
```json
{
  "id": "abc123",
  "platform": "instagram",
  "url": "https://instagram.com",
  "title": "Post title",
  "body": "Post body text",
  "image_path": "C:/PostQueue/image.jpg",
  "image_base64": null,
  "send_email": false
}
```

## Testing Checklist

- [ ] Install dependencies: `pip install -r requirements_osp_simple.txt`
- [ ] Run test suite: `python test_osp_simple.py` (all pass)
- [ ] Launch OSP: `python osp_simple.py` (window appears)
- [ ] Window position: Right edge of screen
- [ ] Window always on top: Yes
- [ ] All 7 buttons visible: Yes
- [ ] Test COPY TITLE: Clipboard works
- [ ] Test COPY BODY: Clipboard works
- [ ] Test COPY IMAGE: Image in clipboard (paste to Paint)
- [ ] Test SUCCESS: Status updates, post clears
- [ ] Test FAILED: Status updates, post clears
- [ ] API connection: Polls every 10 seconds
- [ ] Auto-start setup: `setup_osp_autostart.ps1` works

## Rollback (If Needed)

If you need to go back to the old OSP:

```powershell
# Install old dependencies
pip install -r requirements.txt

# Run old OSP
python osp_gui.py
```

**However, the old OSP won't work well with vision-based automation.**

## Support

- **Quick start:** `QUICK_START_OSP.md`
- **Full docs:** `README_OSP_SIMPLE.md`
- **Architecture:** `W10-Drivers/docs/WS10-OSP-PYTHON-FIX.md`
- **Project overview:** `AGENTS.md`

## Decision

✅ **Use `osp_simple.py` for all new work**
- Simpler, more reliable
- Vision-friendly
- Easier to maintain

📦 **Keep `osp_gui.py` for reference only**
- Historical record
- Contains useful patterns
- Don't use for production

---

**The simplified OSP is now the official version.**
