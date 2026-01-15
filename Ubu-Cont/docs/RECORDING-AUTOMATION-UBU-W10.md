# Recording-Based Automation Guide

## The Problem with Vision Models

The current approach uses Qwen 2.5-VL to identify UI elements on each action. Issues encountered:
- **2-pixel offset errors** on obvious buttons
- Slow inference time (~2-5 seconds per call)
- Expensive API costs at scale
- Unreliable on complex UIs like Instagram

## The Solution: Record Once, Replay Forever

Instead of asking "where is the button?" every time, we:
1. **Record** a human performing the workflow once (capturing clicks + timing)
2. **Save** the recording as a platform-specific workflow
3. **Replay** the exact sequence when posts are queued

This is deterministic, fast, and free.

---

## Current Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  YOUR DESKTOP (Ubuntu via XRDP)                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Chrome @ localhost:5555                                  │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │  Windows 10 Live Control                            │  │  │
│  │  │  ┌───────────────────────┐  ┌────────────────────┐  │  │  │
│  │  │  │  VNC Stream           │  │  Control Panel     │  │  │  │
│  │  │  │  (Windows 10 VM)      │  │  - OPEN URL        │  │  │  │
│  │  │  │                       │  │  - COPY TITLE      │  │  │  │
│  │  │  │  Pos: 1489, 1191      │  │  - COPY BODY       │  │  │  │
│  │  │  │                       │  │  - POST            │  │  │  │
│  │  │  └───────────────────────┘  │  - SUCCESS/FAILED  │  │  │  │
│  │  │                             └────────────────────┘  │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The web interface already shows mouse position. We just need to:
1. Add a "Record" mode that captures clicks with timestamps
2. Store recordings per platform
3. Add a "Playback" mode that replays the sequence

---

## Recording Format

Each recording is a JSON array of actions with timing:

```json
{
  "platform": "instagram",
  "created": "2026-01-14T18:00:00Z",
  "resolution": "1920x1080",
  "vm_offset": {"x": 47, "y": 282},
  "actions": [
    {
      "type": "click",
      "x": 1245,
      "y": 87,
      "delay_before_ms": 0,
      "description": "Click new post button"
    },
    {
      "type": "wait",
      "delay_ms": 2000,
      "description": "Wait for dialog to open"
    },
    {
      "type": "click",
      "x": 650,
      "y": 450,
      "delay_before_ms": 500,
      "description": "Click select from computer"
    },
    {
      "type": "paste",
      "delay_before_ms": 1000,
      "description": "Paste file path"
    },
    {
      "type": "key",
      "key": "Enter",
      "delay_before_ms": 500,
      "description": "Confirm file selection"
    },
    {
      "type": "wait",
      "delay_ms": 5000,
      "description": "Wait for image upload (slow VM)"
    }
  ]
}
```

### Action Types

| Type | Description | Fields |
|------|-------------|--------|
| `click` | Mouse click at coordinates | x, y, delay_before_ms |
| `double_click` | Double click | x, y, delay_before_ms |
| `right_click` | Right click | x, y, delay_before_ms |
| `type` | Type text | text, delay_before_ms |
| `paste` | Paste from clipboard | delay_before_ms |
| `key` | Press key | key (Enter, Tab, Escape, etc.) |
| `wait` | Fixed delay | delay_ms |
| `wait_for_change` | Wait for screen to change | timeout_ms, threshold |

---

## Web Interface Enhancements

### New UI Elements Needed

```
┌─────────────────────────────────────────────────────────────────┐
│  Windows 10 Live Control                                        │
│  ┌─────────────────────────────┐  ┌──────────────────────────┐  │
│  │                             │  │  Platform: INSTAGRAM ▼   │  │
│  │                             │  │  Queue: 1/1              │  │
│  │     VNC Stream              │  │                          │  │
│  │                             │  │  [📷 Preview Image]      │  │
│  │                             │  ├──────────────────────────┤  │
│  │                             │  │  === RECORDING ===       │  │
│  │                             │  │  [🔴 START RECORDING]    │  │
│  │                             │  │  [⏹️ STOP RECORDING]     │  │
│  │                             │  │  [▶️ PLAYBACK]           │  │
│  │                             │  │  [💾 SAVE RECORDING]     │  │
│  │                             │  │                          │  │
│  │  Pos: 1489, 1191            │  │  === ACTIONS ===         │  │
│  │                             │  │  [OPEN URL]              │  │
│  └─────────────────────────────┘  │  [COPY TITLE]            │  │
│                                   │  [COPY BODY]             │  │
│  Recording: 5 actions captured    │  [COPY IMAGE]            │  │
│  Last click: 1489, 1191 @ 2.3s   │  [POST] [✓] [✗]          │  │
│                                   └──────────────────────────┘  │
│  [Ctrl+Alt+Del]  [Ref Snap]  [Reconnect]                       │
└─────────────────────────────────────────────────────────────────┘
```

### Recording Mode Behavior

**When "START RECORDING" is clicked:**
1. Clear any previous recording
2. Start a timer from 0
3. Every click on the VNC stream area captures:
   - X, Y coordinates (relative to VM window)
   - Time since last action (becomes `delay_before_ms` for next action)
4. Show live action count: "Recording: 5 actions captured"
5. Show last click info: "Last click: 1489, 1191 @ 2.3s"

**When "STOP RECORDING" is clicked:**
1. Stop capturing
2. Show the recorded actions in a list (editable)
3. Allow adding descriptions to each action
4. Allow inserting manual waits

**When "PLAYBACK" is clicked:**
1. Replay the recording step by step
2. Show current step being executed
3. Allow pause/resume

**When "SAVE RECORDING" is clicked:**
1. Save to `recordings/{platform}.json`
2. This becomes the workflow for that platform

---

## Coordinate System

**Important:** The VNC stream is embedded in the web page. We need to translate:

```
Web Page Click (absolute)     →     VM Coordinates (relative)
      ↓                                    ↓
Click at (1536, 473)          →     VM click at (1489, 191)
                                    (after subtracting VM offset)
```

The VM window offset from your screenshot appears to be approximately:
- **X offset:** ~47 pixels (left edge of VM stream)
- **Y offset:** ~282 pixels (top edge of VM stream)

These offsets should be calibrated once and stored.

---

## Platform-Specific Recordings

Each platform needs its own recording:

### Instagram Recording (estimated ~15-20 actions)
1. Click new post icon
2. Wait for dialog
3. Click "Select from computer"
4. Wait for file dialog
5. Paste file path
6. Press Enter
7. Wait for upload (LONG - 5-10 seconds for images, 15-30 for video)
8. Click "Next"
9. Wait for filters page
10. Click "Next"
11. Wait for caption page
12. Click caption field
13. Paste caption
14. Click "Share"
15. Wait for confirmation

### Skool Recording (estimated ~8-10 actions)
1. Navigate to community
2. Click new post
3. Click body field
4. Paste content
5. Click image upload (if applicable)
6. Select file
7. Click post

### Facebook Recording (estimated ~10-12 actions)
1. Navigate to page
2. Click "Create post"
3. Click text area
4. Paste content
5. Click photo/video button
6. Select file
7. Wait for upload
8. Click "Post"

---

## Timing Considerations (Slow VM)

Your Windows 10 VM runs on 4 CPUs and is slow. Critical timing adjustments:

| Action | Minimum Wait |
|--------|--------------|
| Dialog open | 2000ms |
| File dialog open | 1500ms |
| Image upload (Instagram) | 5000-10000ms |
| Video upload (Instagram) | 15000-30000ms |
| Page transition | 3000ms |
| Button becomes clickable | 1000ms |

**Pro tip:** When recording, wait longer than necessary. You can always speed up later, but too-fast playback will fail.

---

## Implementation Plan

### Phase 1: Recording Mode
- [ ] Add recording state to web interface
- [ ] Capture clicks with timestamps on VNC area
- [ ] Display live recording status
- [ ] Export recording as JSON

### Phase 2: Playback Mode
- [ ] Load recording from JSON
- [ ] Execute actions sequentially with timing
- [ ] Show current step indicator
- [ ] Handle errors gracefully

### Phase 3: Integration
- [ ] Connect to existing queue system
- [ ] Auto-select recording based on platform
- [ ] Pre-populate clipboard before playback (title, body, image path)
- [ ] Report success/failure back to API

### Phase 4: Polish
- [ ] Recording editor (add/remove/reorder actions)
- [ ] Timing adjustment sliders
- [ ] Test mode (highlight where clicks will go without clicking)
- [ ] Multiple recordings per platform (variants for different post types)

---

## File Structure

```
localhost-5555-app/
├── index.html
├── app.js
├── styles.css
├── recordings/
│   ├── instagram.json
│   ├── instagram_video.json
│   ├── skool.json
│   ├── facebook.json
│   └── tiktok.json
└── config.json          # VM offsets, timing multipliers
```

---

## Why This Is Better Than Vision

| Aspect | Vision Model | Recording-Based |
|--------|--------------|-----------------|
| Speed | 2-5 sec/action | 0ms overhead |
| Cost | $0.001-0.01/action | Free |
| Accuracy | 70-95% | 100% (if UI unchanged) |
| Debugging | "Why did it click there?" | Exact coordinates logged |
| Timing | Guessing | Human-verified delays |

**The only downside:** If Instagram changes their UI, you need to re-record. But that takes 2 minutes vs. debugging vision model prompts for hours.

---

## Next Steps

1. Show me the current code for localhost:5555 web interface
2. We'll add the recording mode UI
3. Test recording a simple workflow
4. Build playback functionality
5. Integrate with your posting queue

Want to start with the web interface code?