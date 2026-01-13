# INSTAGRAM_WORKFLOW.md

## Instagram Posting Workflow - OSP Guided

This workflow uses the On-Screen Prompter (OSP) system with colored boxes to guide the Qwen2.5-VL vision model through the Instagram posting process.

---

## Color Code Legend

| Color | Purpose | Examples |
|-------|---------|----------|
| 🟢 **GREEN** | Primary action buttons | New Post, SUCCESS |
| 🔴 **RED** | Selection/menu items | Post type, Resize, 4:5 ratio |
| 🔵 **BLUE** | Navigation buttons | Select from computer, Next, Share |
| ⬜ **RIGHT SIDE** | System control buttons | COPY FILE LOCATION, COPY BODY, SUCCESS, FAIL |

---

## Workflow Steps

### Step 1: Click New Post
- **Look for:** GREEN box surrounding a `+` button
- **Tag above:** "New Post"
- **Action:** Click center of GREEN box

### Step 2: Select Post Type
- **Look for:** RED box containing the word "Post"
- **Tag above:** "NEW POST"
- **Action:** Click center of RED box

### Step 3: Select From Computer
- **Look for:** BLUE box with text "Select from computer"
- **Action:** Click center of BLUE box
- **Wait:** File Explorer opens

### Step 4: Copy File Location
- **Look for:** Button on RIGHT side saying "COPY FILE LOCATION"
- **Action:** Click that button
- **Effect:** Media file path copied to clipboard

### Step 5: Paste Path in File Name
- **Look for:** Text box labeled "File name:"
- **Action:** Click in text box
- **Action:** Ctrl+V to paste

### Step 6: Click Open
- **Look for:** "Open" button in File Explorer
- **Action:** Click Open
- **Wait:** Image uploads to Instagram

### Step 7: Click Resize
- **Look for:** RED box with tag "RESIZE" above it
- **Action:** Click center of RED box (not the tag)

### Step 8: Select 4:5 Ratio
- **Look for:** RED box containing "4:5"
- **Tag above:** "4:5 RATIO SELECT"
- **Action:** Click center of RED box

### Step 9: Click Next (First)
- **Look for:** BLUE rectangle with text "Next"
- **Tag above:** "NEXT"
- **Action:** Click center of BLUE rectangle

### Step 10: Click Next (Second)
- **Look for:** Another BLUE rectangle with text "Next"
- **Action:** Click center of BLUE rectangle

### Step 11: Copy Body Text
- **Look for:** Button on RIGHT side saying "COPY BODY"
- **Action:** Click that button
- **Effect:** Caption text copied to clipboard

### Step 12: Paste Body Text
- **Look for:** Area saying "Click here and Paste BODY"
- **Action:** Click in that area
- **Action:** Ctrl+V to paste caption

### Step 13: Click Share
- **Look for:** BLUE rectangle with text "Share"
- **Tag above:** "NEXT"
- **Action:** Click center of BLUE rectangle
- **Wait:** Post uploads

### Step 14: Verify Success
- **Look for:** "SUCCESSFUL POST" message on screen
- **Determine:** SUCCESS or FAILED

### Step 15: Report Result
- **If SUCCESS:** Click GREEN "SUCCESS" button on RIGHT side
- **If FAILED:** Click "FAIL" button on RIGHT side
- **Effect:** Signals API that post completed/failed

---

## State Machine Diagram

```
START
  │
  ▼
CLICK_NEW_POST (GREEN box)
  │
  ▼
SELECT_POST_TYPE (RED box)
  │
  ▼
SELECT_FROM_COMPUTER (BLUE box)
  │
  ▼
FILE_EXPLORER_COPY_PATH (RIGHT side button)
  │
  ▼
FILE_EXPLORER_PASTE_PATH (File name box + Ctrl+V)
  │
  ▼
FILE_EXPLORER_OPEN (Open button)
  │
  ▼
CLICK_RESIZE (RED box)
  │
  ▼
SELECT_4_5_RATIO (RED box)
  │
  ▼
CLICK_NEXT_1 (BLUE box)
  │
  ▼
CLICK_NEXT_2 (BLUE box)
  │
  ▼
COPY_BODY_TEXT (RIGHT side button)
  │
  ▼
PASTE_BODY_TEXT (Caption area + Ctrl+V)
  │
  ▼
CLICK_SHARE (BLUE box)
  │
  ▼
VERIFY_SUCCESS
  │
  ├──► SUCCESS ──► Click GREEN "SUCCESS" button
  │
  └──► FAILED ──► Click "FAIL" button
  │
  ▼
COMPLETE
```

---

## Vision Model Prompts

For each step, the vision model receives a specific prompt. Example:

### For CLICK_NEW_POST:
```
Look at this screenshot of Instagram.
Find the GREEN box that surrounds a + button.
There should be a green tag above it saying "New Post".
Return the x,y coordinates of the CENTER of the GREEN box.
Format: x,y (e.g., 150,400)
If not found, return: NOT_FOUND
```

### For SELECT_4_5_RATIO:
```
Look at this screenshot.
Find the RED box that contains "4:5" text.
There should be a red tag above it saying "4:5 RATIO SELECT".
Return the x,y coordinates of the CENTER of the RED box.
Format: x,y
If not found, return: NOT_FOUND
```

---

## Error Handling

- Each step has **3 retry attempts**
- If element not found, wait 2 seconds and retry
- If max retries exceeded, workflow fails
- On failure, click "FAIL" button to report to API

---

## Timing

| Step | Wait After (ms) |
|------|-----------------|
| New Post click | 2000 |
| Post type select | 2000 |
| Select from computer | 2500 |
| Copy file location | 500 |
| Paste path | 500 |
| Open | 3000 |
| Resize | 1000 |
| 4:5 ratio | 1500 |
| Next buttons | 2000 |
| Copy body | 500 |
| Paste body | 1000 |
| Share | 5000 |
| Verify | 1000 |

---

## OSP Button Requirements (Windows 10 Side)

The On-Screen Prompter must provide these RIGHT SIDE buttons:

1. **COPY FILE LOCATION** - Copies the media file path to clipboard
2. **COPY BODY** - Copies the caption text to clipboard
3. **SUCCESS** (GREEN) - Reports successful post to API
4. **FAIL** - Reports failed post to API

---

## Integration Points

### Input (from PostQueue):
```json
{
  "id": "job_123",
  "platform": "instagram",
  "caption": "Check out this photo! #nature",
  "media": [{"local_path": "C:\\PostQueue\\pending\\job_123\\media_1.jpg"}]
}
```

### Output (to API):
- On success: `POST /api/queue/gui/complete` with `{"id": "job_123"}`
- On failure: `POST /api/queue/gui/failed` with `{"id": "job_123", "error": "..."}`