# OSP Companion - Quick Start Guide
## For Cursor Agent

### 🎯 Your Mission in 3 Sentences
1. Remove all Python/WebSocket integration code from this Chrome extension
2. Add static green rectangle highlights around UI elements on Skool.com (and other platforms)
3. Make it easy for computer vision models to find clickable elements by reading your green labels

---

## 📋 Files to Modify (Priority Order)

| File | Action | Lines | Effort |
|------|--------|-------|--------|
| `content/content.js` | **REWRITE** | ~350 | 🔴 High |
| `content/styles.css` | **UPDATE** | ~100 | 🟡 Medium |
| `background/background.js` | **DELETE or MINIMIZE** | ~10 | 🟢 Low |
| `manifest.json` | **UPDATE** | Update permissions | 🟢 Low |
| `popup/*` | **OPTIONAL** | Defer | ⚪ Optional |

---

## 🚀 Quick Implementation Path

### Step 1: Start Fresh (5 minutes)
```bash
# Create new files instead of modifying old ones
cd content/
cp content.js content-OLD-BACKUP.js
cp styles.css styles-OLD-BACKUP.css
```

### Step 2: Core Logic (30 minutes)
Copy this skeleton into **`content/content.js`**:

```javascript
(function() {
    'use strict';

    const PLATFORMS = {
        'skool.com': {
            urlPatterns: ['/posts/new'],
            elements: [
                {
                    name: 'title',
                    selectors: ['p[data-placeholder*="Write something"]'],
                    label: 'Click here to edit title'
                },
                {
                    name: 'body',
                    selectors: ['[contenteditable="true"]'],
                    label: 'Click here to enter body text and click here to paste media files'
                },
                {
                    name: 'post-button',
                    selectors: ['button[type="submit"]'],
                    label: 'Click here to post'
                },
                {
                    name: 'email-toggle',
                    selectors: ['input[type="checkbox"]'],
                    label: 'Email toggle button'
                }
            ]
        }
    };

    function init() {
        const platform = Object.keys(PLATFORMS).find(p =>
            window.location.hostname.includes(p)
        );
        if (platform) applyHighlights(PLATFORMS[platform]);
    }

    function applyHighlights(config) {
        config.elements.forEach(rule => {
            const el = findElement(rule.selectors);
            if (el) createHighlight(el, rule.label);
        });
    }

    function findElement(selectors) {
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) return el;
        }
        return null;
    }

    function createHighlight(element, label) {
        const box = document.createElement('div');
        box.className = 'osp-highlight';
        box.innerHTML = `<div class="osp-label">${label}</div>`;
        document.body.appendChild(box);

        const update = () => {
            const rect = element.getBoundingClientRect();
            box.style.left = rect.left + window.scrollX + 'px';
            box.style.top = rect.top + window.scrollY + 'px';
            box.style.width = rect.width + 'px';
            box.style.height = rect.height + 'px';
        };

        update();
        window.addEventListener('scroll', update, true);
        window.addEventListener('resize', update);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
```

### Step 3: Styling (10 minutes)
Replace **`content/styles.css`** with:

```css
.osp-highlight {
    position: absolute;
    z-index: 9999999;
    pointer-events: none;
    border: 3px solid #10b981;
    background: rgba(16, 185, 129, 0.05);
    border-radius: 4px;
}

.osp-label {
    position: absolute;
    top: -28px;
    left: 0;
    background: #10b981;
    color: white;
    padding: 4px 10px;
    border-radius: 4px;
    font: 700 12px system-ui;
    white-space: nowrap;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
```

### Step 4: Clean Background (2 minutes)
**`background/background.js`** → Delete everything or replace with:

```javascript
// Minimal background - just lifecycle management
chrome.runtime.onInstalled.addListener(() => {
    console.log('[OSP Vision Helper] Installed');
});
```

### Step 5: Test (5 minutes)
1. Go to `chrome://extensions`
2. Enable Developer Mode
3. Click "Load unpacked"
4. Select `W10-Drivers/extensions/osp-companion-extension`
5. Navigate to Skool.com post creation page
6. **VERIFY:** See 4 green rectangles with labels

---

## 🎨 Skool.com Specifics (CRITICAL!)

### The Challenge
Skool **hides** the title and body fields behind a single "Write something..." box.

**Visual Flow:**
1. Initial state: Shows `<p data-placeholder="Write something...">`
2. After click: Reveals title field (first contenteditable)
3. After typing: Shows body field (second contenteditable)

### Your Solution
Highlight the **"Write something..."** area with two labels:
- Top label: "Click here to edit title"
- Bottom label: "Click here to enter body text and paste media files"

Or highlight separately if you can reliably distinguish title from body.

### Selector Deep Dive

```javascript
// TITLE FIELD
// Try these in order:
selectors: [
    'p[data-placeholder*="Write something"]',
    '.editor-container p:first-of-type',
    'div[contenteditable="true"]:first-of-type'
]

// BODY FIELD
// Usually the second contenteditable:
selectors: [
    '.editor-container [contenteditable="true"]:nth-of-type(2)',
    'div[role="textbox"]',
    '[contenteditable="true"]'
]

// POST BUTTON
// Look for submit button:
selectors: [
    'button[type="submit"]',
    'button:has-text("Post")', // May need polyfill
    '.post-button'
]

// EMAIL TOGGLE
// Checkbox near post button:
selectors: [
    'input[type="checkbox"]',
    '[role="checkbox"]'
]
```

**Pro Tip:** Open Chrome DevTools on Skool post page, right-click "Write something..." and inspect. Look for stable data attributes.

---

## ✅ Testing Checklist

### Basic Functionality
- [ ] Extension loads without console errors
- [ ] Green rectangles appear on Skool.com `/posts/new`
- [ ] Labels are readable and positioned correctly
- [ ] Highlights stay aligned during scroll
- [ ] Can still click through highlights (pointer-events: none)

### Computer Vision Test (THE REAL TEST!)
- [ ] Take screenshot with highlights visible
- [ ] Feed to GPT-4V or Claude 3
- [ ] Ask: "Find the green box labeled 'Click here to edit title' and give me X,Y coordinates"
- [ ] Verify coordinates are accurate

### Edge Cases
- [ ] Works on different screen sizes (1920x1080, 1366x768, etc.)
- [ ] Highlights disappear/reappear correctly on SPA navigation
- [ ] No visual conflicts with Skool's UI

---

## 🚨 Troubleshooting

### "Element not found" in console
**Fix:** Inspect actual Skool DOM, update selectors. Skool changes their classes frequently.

### Highlights offset from elements
**Fix:** Check your positioning math:
```javascript
// CORRECT:
box.style.left = rect.left + window.scrollX + 'px';

// WRONG:
box.style.left = rect.left + 'px'; // Missing scroll offset!
```

### Labels cut off at top of screen
**Fix:** Add smart positioning:
```javascript
if (rect.top < 30) {
    label.style.top = '2px'; // Inside element
} else {
    label.style.top = '-28px'; // Above element
}
```

---

## 📚 Full Documentation

See **`CURSOR-AGENT-INSTRUCTIONS.md`** for:
- Complete code implementation
- Multi-platform support (Instagram, Facebook, TikTok)
- Advanced selector strategies
- Navigation observer for SPAs
- Comprehensive troubleshooting

---

## 🎯 Success = This Works

```
Ubuntu Python Script
    ↓
Captures screenshot via VNC
    ↓
Sends to Qwen2.5-VL: "Find the green rectangle labeled 'Click here to edit title'"
    ↓
Vision model returns: {x: 500, y: 300}
    ↓
Ubuntu sends click to Proxmox → Windows 10
    ↓
Title field gets focused
    ↓
REPEAT FOR BODY, POST BUTTON, etc.
    ↓
COMPLETE POST WITHOUT HUMAN INTERVENTION ✅
```

---

**Time Estimate:** 1-2 hours for full Skool.com implementation
**Difficulty:** Medium (mostly DOM inspection and selector refinement)
**Impact:** HIGH - This unblocks the entire automation pipeline!

Good luck! 🚀
