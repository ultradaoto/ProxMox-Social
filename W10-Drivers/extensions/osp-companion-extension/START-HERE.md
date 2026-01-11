# START HERE - Cursor Agent Orientation
## OSP Companion Chrome Extension Rebuild

---

## 📍 WHERE YOU ARE

You're working in: `W10-Drivers/extensions/osp-companion-extension/`

This Chrome extension runs on a **Windows 10 VM** that serves as a "passive cockpit" - a browser environment controlled remotely by an Ubuntu Python script via computer vision.

---

## 🎯 WHAT YOU'RE BUILDING

**In one sentence:** A Chrome extension that draws permanent green rectangles with text labels around UI elements on social media sites so computer vision models can easily find them.

**Visual Example (Skool.com post page):**
```
┌─────────────────────────────────────────────────┐
│ ╔═══════════════════════════════════════╗       │
│ ║ Click here to edit title              ║       │
│ ╚═══════════════════════════════════════╝       │
│ [Write something........................]       │
│                                                  │
│ ╔═══════════════════════════════════════╗       │
│ ║ Click here to enter body text and     ║       │
│ ║ click here to paste media files       ║       │
│ ╚═══════════════════════════════════════╝       │
│ [                                       ]       │
│                                                  │
│              ╔════════════════════╗              │
│              ║ Click here to post ║              │
│              ╚════════════════════╝              │
│              [      Post         ]              │
└─────────────────────────────────────────────────┘
```

Those green boxes (`╔═══╗`) are what you're adding!

---

## 📚 DOCUMENTATION STRUCTURE

### Start with these (in order):

1. **`QUICK-START.md`** ← Read this FIRST!
   - 5-minute overview
   - Minimal code skeleton
   - Testing checklist
   - ~200 lines

2. **`CURSOR-AGENT-INSTRUCTIONS.md`** ← Your comprehensive guide
   - Full implementation details
   - Platform-specific selectors
   - Troubleshooting guide
   - ~600 lines

3. **`README-NEW-OSP.md`** ← Architecture context
   - Why static highlights work
   - Platform examples (Skool, Instagram, Facebook, TikTok)
   - Integration with computer vision
   - ~460 lines

### Background reading (optional):

4. **`../../../AGENT-TRACKER/1-10-2026.md`**
   - Overall project roadmap
   - Agent responsibilities (Ubuntu brain, Windows cockpit, Proxmox host)

5. **`../../docs/W10-SIMPLER-COCPIT.md`**
   - Windows 10's role in the system
   - Why we removed Python/AI from Windows
   - VNC + input injection architecture

---

## 🗂️ FILE STRUCTURE

```
osp-companion-extension/
├── manifest.json              # Chrome extension config
├── background/
│   └── background.js          # DELETE WebSocket code (or remove file)
├── content/
│   ├── content.js             # REWRITE - Your main work here! (~600→350 lines)
│   └── styles.css             # UPDATE - Green rectangle styles (~100 lines)
├── popup/
│   ├── popup.html             # OPTIONAL - Can defer/simplify
│   ├── popup.js               # OPTIONAL - Can defer/simplify
│   └── popup.css              # OPTIONAL
├── icons/                     # Keep as-is
│   ├── icon-16.png
│   ├── icon-32.png
│   ├── icon-48.png
│   └── icon-128.png
├── CURSOR-AGENT-INSTRUCTIONS.md  # ← Your bible
├── QUICK-START.md                # ← Your TL;DR
├── README-NEW-OSP.md             # ← Your context
└── START-HERE.md                 # ← You are here!
```

---

## 🔧 WHAT TO DO

### Phase 1: Understand (15 minutes)
- [ ] Read `QUICK-START.md` completely
- [ ] Skim `CURSOR-AGENT-INSTRUCTIONS.md` (focus on "Implementation Details" section)
- [ ] Open Skool.com in Chrome, go to post creation page
- [ ] Inspect DOM to find actual selectors for title/body/post button

### Phase 2: Build Core (1 hour)
- [ ] Backup old files: `content.js` → `content-OLD.js`
- [ ] Implement new `content.js` with Skool.com platform rules
- [ ] Update `styles.css` with green rectangle styles
- [ ] Simplify/delete `background/background.js` (remove WebSocket code)

### Phase 3: Test (30 minutes)
- [ ] Load extension in Chrome (`chrome://extensions`)
- [ ] Visit Skool post page
- [ ] Verify 4 green rectangles appear
- [ ] Take screenshot
- [ ] Test with vision model (GPT-4V or Claude 3)

### Phase 4: Expand (Optional)
- [ ] Add Instagram support
- [ ] Add Facebook support
- [ ] Add TikTok support

---

## 🎨 THE KEY INSIGHT

### OLD WAY (Python controlled everything):
```
Python → WebSocket → Extension → Highlight element X
User clicks X
Python → WebSocket → Extension → Clear highlight, show element Y
User clicks Y
Python → WebSocket → Extension → Clear highlight, show element Z
...
```

**Problem:** Complex state management, timing issues, Python needs to know page structure.

### NEW WAY (Extension shows all hints always):
```
Extension loads → Highlights ALL elements with green rectangles
Python captures screenshot
Python asks vision model: "Where is green box labeled X?"
Vision model: "Coordinates: (500, 300)"
Python clicks (500, 300)
DONE - No complex communication needed!
```

**Benefit:** Simple, reliable, Python just needs to "see" and "click" - no page knowledge required!

---

## 🧪 SUCCESS CRITERIA

You're done when:

1. ✅ Extension loads on Skool.com without errors
2. ✅ 4 green rectangles appear with correct labels:
   - Title entry
   - Body entry (with paste instructions)
   - Post button
   - Email toggle
3. ✅ Labels are clearly readable in screenshots
4. ✅ Highlights don't interfere with normal page usage
5. ✅ Computer vision model can identify elements from screenshot and return accurate coordinates

**The ultimate test:**
```
Screenshot → Vision Model → "Find 'Click here to post'" → Returns {x: 850, y: 650}
→ Click works! ✅
```

---

## ❓ WHAT IF I'M STUCK?

### Can't find selectors for Skool elements?
1. Open Chrome DevTools on Skool post page
2. Right-click "Write something..." → Inspect
3. Look for `data-placeholder` attribute
4. Note the parent structure (likely `.editor-container` or similar)
5. Use multiple fallback selectors

### Highlights appearing in wrong position?
Check the math in `CURSOR-AGENT-INSTRUCTIONS.md` positioning section:
```javascript
box.style.left = rect.left + window.scrollX + 'px';  // ← Don't forget scrollX!
box.style.top = rect.top + window.scrollY + 'px';    // ← Don't forget scrollY!
```

### Vision model can't find green boxes?
- Make border thicker: `border: 5px solid #10b981;`
- Make label bigger: `font-size: 14px;`
- Use brighter green: `#00ff00`

### Extension not loading in Chrome?
- Check `chrome://extensions` for errors
- Verify `manifest.json` is valid JSON
- Make sure all file paths are correct

---

## 🚀 RECOMMENDED WORKFLOW

**Hour 1:**
1. Read `QUICK-START.md` (10 min)
2. Inspect Skool.com DOM (15 min)
3. Write minimal `content.js` with Skool platform rules (30 min)
4. Test basic highlighting (5 min)

**Hour 2:**
1. Refine selectors based on testing (20 min)
2. Polish styles (label positioning, colors) (15 min)
3. Add scroll/resize handlers (10 min)
4. Clean up background script (5 min)
5. Final testing (10 min)

**Hour 3 (if needed):**
1. Add Instagram support (30 min)
2. Handle edge cases (SPA navigation, late-loading elements) (20 min)
3. Documentation updates (10 min)

---

## 💡 PRO TIPS

1. **Don't modify old code** - Start fresh with the skeleton in `QUICK-START.md`
2. **Test early, test often** - Load extension after every major change
3. **Use Chrome DevTools Console** - Test selectors with `document.querySelector('[your-selector]')`
4. **Screenshot everything** - Visual verification is faster than debugging
5. **Read the full docs** - `CURSOR-AGENT-INSTRUCTIONS.md` has solutions to common problems

---

## 📞 NEED MORE CONTEXT?

**System Architecture:**
- Ubuntu VM (192.168.100.10) = Brain (Python workflows + vision models)
- Windows 10 VM (192.168.100.20) = Cockpit (Chrome + this extension)
- Proxmox Host (192.168.100.1) = Input pipeline (mouse/keyboard injection)

**Data Flow:**
1. Ubuntu captures screenshot from Windows via VNC
2. Vision model finds green rectangles in screenshot
3. Ubuntu sends click commands to Proxmox
4. Proxmox injects input to Windows VM
5. Windows VM executes the action
6. Repeat until post is complete

**Your extension's role:** Make step 2 (vision finding elements) trivially easy!

---

## ✨ YOU GOT THIS!

This is a well-defined task with clear success criteria. The hard design work is done - you just need to implement it.

**Remember:**
- Bright green rectangles (#10b981)
- Clear text labels
- Static (always visible)
- No Python communication needed

**Questions while coding?** Refer to `CURSOR-AGENT-INSTRUCTIONS.md` sections:
- "Implementation Details" for code examples
- "Platform-Specific Element Detection" for selector strategies
- "Common Pitfalls & Solutions" for troubleshooting

Good luck! 🎉

---

**Last Updated:** 2026-01-10
**Your Mission:** Transform this extension from Python-driven to vision-friendly
**Estimated Time:** 2-3 hours
**Difficulty:** Medium
**Impact:** Unblocks entire automation pipeline! 🚀
