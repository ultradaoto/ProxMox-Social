# OSP Companion Extension - Cursor Agent Instructions
# Static Computer Vision UI Highlighter System

## 🎯 MISSION OVERVIEW

You are transforming the OSP Companion Chrome extension from a **Python-driven sequential workflow tool** into a **static computer vision helper** that permanently highlights UI elements on social media platforms.

### What Changed (Critical Context)

**OLD APPROACH (Remove This):**
- Python sent WebSocket commands to highlight elements sequentially
- Extension waited for Python instructions to show/hide highlights
- Highlights changed dynamically as workflow progressed
- Complex state management between Python and extension

**NEW APPROACH (Build This):**
- Extension **permanently** highlights specific UI elements with green rectangles
- Text labels describe what each element does (for computer vision to read)
- **No WebSocket connection to Python** - purely static visual aids
- Computer vision models (Qwen2.5-VL on Ubuntu) analyze screenshots to find coordinates
- Works immediately on page load - no external triggers needed

---

## 🧠 WHY THIS MATTERS

### The Computer Vision Workflow

```
┌──────────────────────────────────────────────────────────────┐
│  Ubuntu (Brain) - Deterministic Python Orchestration        │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. Capture screenshot via VNC from Windows 10 VM       │  │
│  │ 2. Feed screenshot to Qwen2.5-VL vision model          │  │
│  │ 3. Ask: "Where is the green rectangle labeled          │  │
│  │    'Click here to edit title'?"                        │  │
│  │ 4. Vision model returns coordinates (x=500, y=300)     │  │
│  │ 5. Send mouse click to Proxmox → Windows 10 VM         │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                         ↓
┌──────────────────────────────────────────────────────────────┐
│  Windows 10 VM (Cockpit) - Passive Browser Display          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ Chrome with OSP Extension loaded                       │  │
│  │ ┌────────────────────────────────────────────────────┐ │  │
│  │ │ Skool.com page with GREEN RECTANGLES:              │ │  │
│  │ │                                                      │ │  │
│  │ │ ╔═══════════════════════════════════════════╗      │ │  │
│  │ │ ║ Click here to edit title                  ║      │ │  │
│  │ │ ╚═══════════════════════════════════════════╝      │ │  │
│  │ │ [Write something............................]      │ │  │
│  │ │                                                      │ │  │
│  │ │ ╔═══════════════════════════════════════════╗      │ │  │
│  │ │ ║ Click here to enter body text and paste   ║      │ │  │
│  │ │ ║ media files                                ║      │ │  │
│  │ │ ╚═══════════════════════════════════════════╝      │ │  │
│  │ │ [                                           ]      │ │  │
│  │ │                                                      │ │  │
│  │ │            ╔═════════════════════╗                  │ │  │
│  │ │            ║ Click here to post  ║                  │ │  │
│  │ │            ╚═════════════════════╝                  │ │  │
│  │ │            [      Post          ]                  │ │  │
│  │ └────────────────────────────────────────────────────┘ │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Key Insight:** The green rectangles and text labels make it TRIVIAL for computer vision to identify elements. Without these visual aids, finding hidden UI elements (like Skool's title/body fields) would be extremely unreliable.

---

## 📁 FILES YOU NEED TO MODIFY

### Priority 1: Core Functionality (MUST CHANGE)

#### 1. `content/content.js` - Complete Rewrite Required
**Current State:** 600 lines handling WebSocket messages, dynamic highlighting, Python integration
**Target State:** ~350 lines of static element detection and permanent highlighting

**What to Remove:**
- All WebSocket message handling (`handleOSPMessage`, `highlightElement` with Python triggers)
- Recording mode functionality (`toggleRecording`, `onGlobalClick`)
- Dynamic highlight clearing (`clearHighlights` triggered by Python)
- Instruction banner system (`showInstruction`, `hideInstruction`)
- All `sendToBackground` calls to Python
- `content_ready` signal to background script

**What to Add:**
- Platform detection (detect Skool.com, Instagram.com, etc.)
- Element finder system (CSS selectors for each platform's UI elements)
- Permanent highlight renderer (create green rectangles on page load)
- Position tracking (update rectangle positions on scroll/resize)
- Multi-platform support structure (easy to add new platforms)

#### 2. `content/styles.css` - Significant Changes
**Current State:** Pulsing outlines, dynamic overlay positioning
**Target State:** Static green rectangles with clear text labels

**What to Change:**
- `.osp-highlight-overlay` → permanent green border rectangles
- `.osp-highlight-label` → always-visible text labels (not just on hover)
- Remove pulsing animations (causes visual noise for screenshots)
- Add sharp, high-contrast borders (easier for vision models to detect)
- Ensure labels never occlude important UI (position above elements)

#### 3. `background/background.js` - Simplified or Removed
**Current State:** 187 lines managing WebSocket connection to Python
**Target State:** Either empty (minimal lifecycle) or completely removed

**Decision Point:**
- **Option A (Recommended):** Keep minimal background script for extension lifecycle, remove all WebSocket code
- **Option B:** Remove background service worker entirely if not needed (test if content scripts work without it)

**What to Remove:**
- All WebSocket connection logic (`connectToOSP`, `scheduleReconnect`)
- Message passing to Python (`sendToOSP`, `handleOSPMessage`)
- Recording state management
- Tab update listeners that notify Python

**What to Keep (if Option A):**
- Basic extension install handler (optional logging)
- Potentially: popup communication (if popup becomes a config UI)

#### 4. `manifest.json` - Permission Updates
**Current State:** Broad `<all_urls>` permissions, background service worker
**Target State:** Specific host permissions, optional background worker

**What to Change:**
```json
{
  "host_permissions": [
    "*://*.skool.com/*",
    "*://*.instagram.com/*",
    "*://*.facebook.com/*",
    "*://*.tiktok.com/*"
  ]
}
```

**Consider Removing:**
- `"background"` key (if going with Option B above)
- `"tabs"` permission (not needed without Python communication)

### Priority 2: Optional Enhancements

#### 5. `popup/popup.html` & `popup.js` - Repurpose or Simplify
**Current State:** Shows WebSocket connection status, recording controls
**Target State:** Configuration UI or simple status display

**Options:**
- **Simple:** Show list of detected platforms and highlighted element count
- **Advanced:** Allow users to toggle which platforms/elements to highlight
- **Minimal:** Remove popup entirely (extension works silently)

---

## 🎨 IMPLEMENTATION DETAILS

### Core JavaScript Architecture (content.js)

```javascript
(function() {
    'use strict';

    // ===== PLATFORM CONFIGURATION =====
    const PLATFORM_RULES = {
        'skool.com': {
            // Match URLs containing these paths
            urlPatterns: ['/posts/new', '/groups/'],

            // Elements to highlight (in priority order)
            elements: [
                {
                    name: 'title-entry',
                    // Try selectors in order until one works
                    selectors: [
                        'p[data-placeholder*="Write something"]',
                        '[data-placeholder*="Write"]',
                        '.editor-container p:first-of-type',
                        'div[contenteditable="true"]:first-of-type'
                    ],
                    label: 'Click here to edit title',
                    style: 'rectangle',
                    color: '#10b981' // Green
                },
                {
                    name: 'body-entry',
                    selectors: [
                        'p[data-placeholder*="Write something"]',
                        '[contenteditable="true"]',
                        'div[role="textbox"]',
                        '.editor-content'
                    ],
                    label: 'Click here to enter body text and click here to paste media files',
                    style: 'rectangle',
                    color: '#10b981'
                },
                {
                    name: 'post-button',
                    selectors: [
                        'button:has-text("Post")',
                        'button[type="submit"]',
                        '.post-button',
                        'button.primary'
                    ],
                    label: 'Click here to post',
                    style: 'rectangle',
                    color: '#10b981'
                },
                {
                    name: 'email-toggle',
                    selectors: [
                        'input[type="checkbox"]',
                        '[role="checkbox"]',
                        '.email-toggle'
                    ],
                    label: 'Email toggle button',
                    style: 'rectangle',
                    color: '#10b981'
                }
            ]
        },

        'instagram.com': {
            urlPatterns: ['*'], // All Instagram pages
            elements: [
                {
                    name: 'create-post',
                    selectors: [
                        'a[href="#"]>svg[aria-label*="New post"]',
                        '[aria-label="New post"]',
                        'svg[aria-label*="Create"]'
                    ],
                    label: 'Click here to create post',
                    style: 'circle',
                    color: '#10b981'
                },
                {
                    name: 'upload-media',
                    selectors: [
                        'button:has-text("Select from computer")',
                        'input[type="file"][accept*="image"]',
                        '[aria-label*="Drag photos"]'
                    ],
                    label: 'Click here to select media',
                    style: 'rectangle',
                    color: '#10b981'
                },
                {
                    name: 'caption-field',
                    selectors: [
                        'textarea[aria-label*="Write a caption"]',
                        '[placeholder*="Write a caption"]',
                        'textarea[placeholder*="caption"]'
                    ],
                    label: 'Click here to enter caption',
                    style: 'rectangle',
                    color: '#10b981'
                },
                {
                    name: 'share-button',
                    selectors: [
                        'button:has-text("Share")',
                        '[aria-label="Share"]',
                        'button[type="button"]:has-text("Share")'
                    ],
                    label: 'Click here to share post',
                    style: 'rectangle',
                    color: '#10b981'
                }
            ]
        }

        // Add Facebook, TikTok, LinkedIn later...
    };

    // ===== INITIALIZATION =====
    function init() {
        console.log('[OSP Vision Helper] Initializing...');

        const platform = detectPlatform();
        if (!platform) {
            console.log('[OSP Vision Helper] No supported platform detected');
            return;
        }

        console.log('[OSP Vision Helper] Platform detected:', platform);
        applyHighlights(platform);

        // Re-apply highlights on navigation (for SPAs)
        observeNavigation(() => applyHighlights(platform));
    }

    function detectPlatform() {
        const hostname = window.location.hostname;
        const pathname = window.location.pathname;

        for (const [domain, config] of Object.entries(PLATFORM_RULES)) {
            if (hostname.includes(domain)) {
                // Check if URL pattern matches
                const matches = config.urlPatterns.some(pattern => {
                    if (pattern === '*') return true;
                    return pathname.includes(pattern);
                });

                if (matches) return domain;
            }
        }

        return null;
    }

    // ===== HIGHLIGHT APPLICATION =====
    function applyHighlights(platform) {
        // Clear existing highlights first
        document.querySelectorAll('.osp-static-highlight').forEach(el => el.remove());

        const config = PLATFORM_RULES[platform];
        if (!config) return;

        config.elements.forEach(elementRule => {
            // Try to find element using selectors
            const element = findElement(elementRule.selectors);

            if (element) {
                console.log('[OSP Vision Helper] Found:', elementRule.name);
                createHighlight(element, elementRule);
            } else {
                console.warn('[OSP Vision Helper] Not found:', elementRule.name);
                // Retry after 2 seconds (element might load late)
                setTimeout(() => {
                    const retryElement = findElement(elementRule.selectors);
                    if (retryElement) {
                        console.log('[OSP Vision Helper] Found on retry:', elementRule.name);
                        createHighlight(retryElement, elementRule);
                    }
                }, 2000);
            }
        });
    }

    function findElement(selectors) {
        for (const selector of selectors) {
            try {
                const element = document.querySelector(selector);
                if (element && isVisible(element)) {
                    return element;
                }
            } catch (e) {
                // Invalid selector, continue
                console.warn('[OSP Vision Helper] Invalid selector:', selector);
            }
        }
        return null;
    }

    function isVisible(element) {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    // ===== HIGHLIGHT RENDERING =====
    function createHighlight(element, rule) {
        const highlight = document.createElement('div');
        highlight.className = 'osp-static-highlight';
        highlight.setAttribute('data-element-name', rule.name);

        // Add style class
        if (rule.style === 'circle') {
            highlight.classList.add('osp-circle');
        } else {
            highlight.classList.add('osp-rectangle');
        }

        // Create label
        const label = document.createElement('div');
        label.className = 'osp-highlight-label';
        label.textContent = rule.label;
        label.style.backgroundColor = rule.color;
        highlight.appendChild(label);

        // Position the highlight
        document.body.appendChild(highlight);
        updateHighlightPosition(highlight, element);

        // Track position on scroll/resize
        const updatePosition = () => updateHighlightPosition(highlight, element);
        window.addEventListener('scroll', updatePosition, true);
        window.addEventListener('resize', updatePosition);

        // Store cleanup function
        highlight._cleanup = () => {
            window.removeEventListener('scroll', updatePosition, true);
            window.removeEventListener('resize', updatePosition);
        };
    }

    function updateHighlightPosition(highlight, element) {
        const rect = element.getBoundingClientRect();

        // Position highlight box
        highlight.style.left = `${rect.left + window.scrollX}px`;
        highlight.style.top = `${rect.top + window.scrollY}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;

        // Ensure label is visible (position above element)
        const label = highlight.querySelector('.osp-highlight-label');
        if (label) {
            // Check if there's room above
            if (rect.top < 30) {
                // Position inside top of element
                label.style.top = '2px';
                label.style.bottom = 'auto';
            } else {
                // Position above element
                label.style.top = '-28px';
                label.style.bottom = 'auto';
            }
        }
    }

    // ===== NAVIGATION OBSERVER (for SPAs) =====
    function observeNavigation(callback) {
        let lastUrl = window.location.href;

        const observer = new MutationObserver(() => {
            const currentUrl = window.location.href;
            if (currentUrl !== lastUrl) {
                lastUrl = currentUrl;
                console.log('[OSP Vision Helper] Navigation detected');
                // Wait for page to stabilize
                setTimeout(callback, 500);
            }
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    // ===== START =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
```

### CSS Styling (content/styles.css)

```css
/* ============================================
   OSP Static Highlight Styles
   Computer Vision Optimized
   ============================================ */

.osp-static-highlight {
    position: absolute;
    z-index: 2147483647; /* Maximum z-index */
    pointer-events: none; /* Don't interfere with clicking */

    /* Bright green border - high contrast for vision models */
    border: 3px solid #10b981;
    background-color: rgba(16, 185, 129, 0.05); /* Very subtle fill */

    /* Sharp corners for clear detection */
    border-radius: 4px;

    /* No animations - static for screenshots */
    transition: none;
}

.osp-static-highlight.osp-circle {
    border-radius: 50%;
}

.osp-static-highlight.osp-rectangle {
    border-radius: 4px;
}

/* Label styling */
.osp-highlight-label {
    position: absolute;
    top: -28px;
    left: 0;

    background-color: #10b981; /* Bright green background */
    color: #ffffff;

    padding: 4px 10px;
    border-radius: 4px;

    font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
    font-size: 12px;
    font-weight: 700;
    line-height: 1.4;

    white-space: nowrap;
    max-width: 400px;
    overflow: hidden;
    text-overflow: ellipsis;

    /* High contrast shadow for readability */
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);

    /* Always visible - no fading */
    opacity: 1 !important;

    /* Prevent accidental interaction */
    pointer-events: none !important;
}

/* Ensure no interference with page elements */
.osp-static-highlight * {
    pointer-events: none !important;
}

/* Hide highlights when printing */
@media print {
    .osp-static-highlight {
        display: none !important;
    }
}

/* Ensure highlights stay on top of modals */
.osp-static-highlight {
    z-index: 2147483647 !important;
}
```

---

## 🎯 PLATFORM-SPECIFIC ELEMENT DETECTION

### Skool.com - Detailed Selector Strategy

**Challenge:** Skool hides the title and body fields behind a generic "Write something..." placeholder.

#### Element 1: Title Entry Field
**Visual Behavior:**
- Initially shows as "Write something..." in a subtle gray
- When clicked, reveals a title input field at the top
- Field is `contenteditable="true"` div or paragraph

**Selector Strategy:**
```javascript
selectors: [
    // Try data attribute first (most reliable)
    'p[data-placeholder*="Write something"]',
    '[data-placeholder*="Write"]',

    // Try by position (first editable element)
    '.editor-container p:first-of-type',
    'div[contenteditable="true"]:first-of-type',

    // Try by class patterns (inspect Skool's DOM)
    '.post-editor__title',
    '.title-field',

    // Generic fallback
    '[contenteditable="true"]'
]
```

**Label:** `"Click here to edit title"`

**Visual Placement:**
- Green rectangle around the entire "Write something..." clickable area
- Label positioned at top-left corner of rectangle

#### Element 2: Body Entry Field
**Visual Behavior:**
- Appears below title after clicking "Write something..."
- Larger contenteditable area for main post content
- **Critical:** Must be clicked TWICE to paste media (first to focus, second to paste)

**Selector Strategy:**
```javascript
selectors: [
    // Try finding body specifically (after title is filled)
    'p[data-placeholder*="Write something"]:nth-of-type(2)',
    '.editor-container [contenteditable="true"]:nth-of-type(2)',

    // Try by class
    '.post-editor__body',
    '.body-field',

    // Generic body patterns
    'div[role="textbox"]',
    'textarea',
    '[contenteditable="true"]'
]
```

**Label:** `"Click here to enter body text and click here to paste media files"`

**Visual Placement:**
- Green rectangle around body text area
- Longer label to explain the two-click paste requirement

#### Element 3: Post Button
**Visual Behavior:**
- Usually at bottom-right of compose area
- Often labeled "Post" or "Publish"
- May be disabled until content is entered

**Selector Strategy:**
```javascript
selectors: [
    // Try by text content
    'button:has-text("Post")', // Note: :has-text() is non-standard, may need polyfill

    // Try by type
    'button[type="submit"]',

    // Try by class
    '.post-button',
    'button.primary',
    '.submit-button',

    // Try by ARIA
    '[aria-label="Post"]',
    '[aria-label*="Publish"]'
]
```

**Label:** `"Click here to post"`

#### Element 4: Email Toggle
**Visual Behavior:**
- Checkbox or toggle switch
- Usually near post button
- Text like "Send to email" or "Notify members"

**Selector Strategy:**
```javascript
selectors: [
    // Try by input type
    'input[type="checkbox"]',

    // Try by role
    '[role="checkbox"]',
    '[role="switch"]',

    // Try by class/label patterns
    '.email-toggle',
    '.notification-toggle',

    // Try by nearby text
    'label:has-text("email") input',
    'label:has-text("Send") input'
]
```

**Label:** `"Email toggle button"`

### Instagram.com - Workflow Highlights

#### Create Post Flow
1. **Home page:** Highlight "+" icon in sidebar
2. **After click:** Highlight upload area
3. **After upload:** Highlight caption field
4. **After caption:** Highlight Share button

**Implementation Note:** Use navigation observer to detect workflow progression and show relevant highlights.

### Generic Fallback Strategy

If primary selectors fail, implement a "smart search" that:
1. Searches for elements with relevant ARIA labels
2. Looks for buttons with text containing keywords ("post", "share", "upload")
3. Identifies textboxes by role or contenteditable
4. Ranks results by visibility and position

---

## 🔧 TESTING & VALIDATION

### Development Testing Checklist

#### Phase 1: Skool.com
- [ ] Load extension in Chrome (`chrome://extensions` → Developer mode → Load unpacked)
- [ ] Navigate to `skool.com/groups/[YOUR_GROUP]/posts/new`
- [ ] Verify 4 green rectangles appear:
  - [ ] Title entry area with "Click here to edit title"
  - [ ] Body entry area with paste instructions
  - [ ] Post button
  - [ ] Email toggle
- [ ] Test scroll behavior - highlights stay positioned
- [ ] Test window resize - highlights adjust correctly
- [ ] Click through workflow - highlights don't interfere with normal usage

#### Phase 2: Instagram.com
- [ ] Navigate to `instagram.com`
- [ ] Verify "Create post" button is highlighted
- [ ] Click create button
- [ ] Verify upload area gets highlighted
- [ ] Upload an image
- [ ] Verify caption field gets highlighted
- [ ] Enter caption
- [ ] Verify Share button gets highlighted

#### Phase 3: Computer Vision Test (Critical!)
This is the REAL test - can computer vision find the elements?

**Setup:**
1. Take a screenshot of Skool post page with highlights visible
2. Send to a vision model (GPT-4V, Claude 3, or Qwen2.5-VL)
3. Ask: "Where is the green rectangle labeled 'Click here to edit title'? Provide X,Y coordinates."

**Success Criteria:**
- Vision model correctly identifies the labeled rectangle
- Coordinates are accurate (within 10px of actual element center)
- Model can distinguish between multiple green rectangles by reading labels

**Example Test Prompt:**
```
You are analyzing a screenshot of a social media posting interface.
Find the green rectangle with the label "Click here to enter body text and click here to paste media files".
Return the X,Y coordinates of the CENTER of this rectangle.
```

### Manual Inspection Checklist
- [ ] No console errors when extension loads
- [ ] Highlights appear within 1 second of page load
- [ ] Labels are fully readable (not cut off or overlapping)
- [ ] Green color is distinct from page elements (#10b981)
- [ ] Highlights don't block important UI elements
- [ ] Extension works on both HTTP and HTTPS
- [ ] Works in Chrome, Edge, and other Chromium browsers

---

## 🚨 COMMON PITFALLS & SOLUTIONS

### Problem: Element Not Found
**Symptoms:** Console shows "Not found: [element-name]"

**Solutions:**
1. **Inspect the actual DOM** - Skool and other platforms frequently change class names
2. **Add more selector variations** - Try multiple approaches (data attributes, classes, position)
3. **Wait longer** - Some elements load via AJAX, increase retry delay
4. **Check for Shadow DOM** - Some frameworks use Shadow DOM (requires different API)

### Problem: Highlights Appear in Wrong Position
**Symptoms:** Green rectangles offset from actual elements

**Solutions:**
1. **Check for transforms** - CSS transforms affect positioning, account for them
2. **Account for scroll offset** - Use `window.scrollX/Y` in calculations
3. **Handle fixed/sticky elements** - Use different positioning strategy
4. **Debounce position updates** - Too frequent updates cause jank

### Problem: Highlights Disappear on Navigation
**Symptoms:** Highlights gone after clicking links (SPAs)

**Solutions:**
1. **Implement MutationObserver** - Detect DOM changes and re-apply
2. **Listen for history events** - `popstate`, `pushState` changes
3. **Use navigation observer pattern** - See implementation above

### Problem: Labels Cut Off or Overlapping
**Symptoms:** Text labels truncated or overlapping with other elements

**Solutions:**
1. **Dynamic label positioning** - Check available space above element
2. **Fallback to inside placement** - If no room above, place inside top of rectangle
3. **Truncate long labels** - Use `text-overflow: ellipsis`
4. **Abbreviate labels** - "Click here to..." → "Click to..."

---

## 📚 RESOURCES & REFERENCES

### Current Files to Study
1. **`README-NEW-OSP.md`** - Vision system architecture overview
2. **`W10-DRIVERS/docs/W10-SIMPLER-COCPIT.md`** - Windows 10 passive cockpit role
3. **`AGENT-TRACKER/1-10-2026.md`** - Overall project roadmap and agent responsibilities

### Chrome Extension Documentation
- [Manifest V3 Guide](https://developer.chrome.com/docs/extensions/mv3/)
- [Content Scripts](https://developer.chrome.com/docs/extensions/mv3/content_scripts/)
- [Match Patterns](https://developer.chrome.com/docs/extensions/mv3/match_patterns/)

### Selector Techniques
- [CSS Selectors Reference](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Selectors)
- [querySelector vs querySelectorAll](https://developer.mozilla.org/en-US/docs/Web/API/Document/querySelector)

### Testing Vision Models
- Qwen2.5-VL (running on Ubuntu via Ollama)
- GPT-4V (for validation testing)
- Claude 3 Opus (for validation testing)

---

## ✅ SUCCESS CRITERIA

### Milestone 1: Skool.com Working (First Priority)
- [ ] Extension loads without errors on `skool.com`
- [ ] All 4 elements highlighted correctly on `/posts/new` page
- [ ] Labels clearly readable in screenshots
- [ ] Highlights don't interfere with posting workflow
- [ ] Computer vision model can identify elements from screenshot

### Milestone 2: Multi-Platform Support
- [ ] Instagram highlighting implemented and tested
- [ ] Easy to add new platforms (config-driven approach)
- [ ] Consistent visual style across platforms

### Milestone 3: Production Ready
- [ ] No performance issues (smooth scrolling, no lag)
- [ ] Works across different screen sizes
- [ ] Handles edge cases (slow loading, missing elements)
- [ ] Clean console (no errors or warnings)

### Ultimate Success Test
**The Ubuntu Python script can:**
1. Capture a VNC screenshot of Windows 10 Chrome
2. Feed it to Qwen2.5-VL
3. Ask "Where is [element label]?"
4. Get accurate X,Y coordinates
5. Click that position successfully
6. Complete a full posting workflow WITHOUT human intervention

---

## 🎬 GETTING STARTED - ACTION ITEMS

### Step 1: Clean Up (Remove Old Code)
- [ ] Open `background/background.js`
- [ ] Delete all WebSocket code (lines 1-187)
- [ ] Leave only basic extension lifecycle (or delete file entirely)
- [ ] Update `manifest.json` to remove background worker (if deleted)

### Step 2: Rewrite Content Script
- [ ] Open `content/content.js`
- [ ] Delete all existing code (it's for the old approach)
- [ ] Copy the implementation skeleton from this document
- [ ] Start with Skool.com platform rules
- [ ] Test on actual Skool page

### Step 3: Update Styles
- [ ] Open `content/styles.css`
- [ ] Replace with computer vision optimized styles
- [ ] Test label positioning and visibility
- [ ] Ensure no visual conflicts

### Step 4: Test & Iterate
- [ ] Load extension in Chrome
- [ ] Visit Skool.com post creation page
- [ ] Take screenshot
- [ ] Test with vision model
- [ ] Refine selectors based on results

### Step 5: Expand Platforms
- [ ] Add Instagram rules
- [ ] Add Facebook rules
- [ ] Add TikTok rules
- [ ] Document selector patterns for future platforms

---

## 💬 QUESTIONS TO ASK IF STUCK

1. **Can't find an element?**
   - Inspect the actual DOM in Chrome DevTools
   - Check if element is in Shadow DOM
   - Try querying in console: `document.querySelector('[your-selector]')`

2. **Highlights in wrong position?**
   - Check element's `getBoundingClientRect()`
   - Verify you're adding `window.scrollX/Y`
   - Look for CSS transforms on parent elements

3. **Extension not loading?**
   - Check console for errors in `chrome://extensions`
   - Verify `manifest.json` is valid JSON
   - Ensure all file paths are correct

4. **Vision model can't find elements?**
   - Increase border thickness (try 5px instead of 3px)
   - Make label text larger (try 14px instead of 12px)
   - Use brighter green (#00ff00) for higher contrast

---

## 📝 FINAL NOTES

This is a **complete architectural shift** from the old extension. Don't try to modify the existing code - you'll spend more time removing old logic than writing new code.

**Recommended approach:**
1. Create new files: `content/vision-helper.js` and `content/vision-styles.css`
2. Build the new system from scratch using this document
3. Test thoroughly on Skool.com
4. Once working, replace old files entirely

**Remember:** The goal is to make computer vision's job EASY. Bright green, clear labels, static positioning. If a human can instantly see where to click, the vision model will too.

**Good luck!** 🚀

---

**Document Version:** 1.0
**Last Updated:** 2026-01-10
**Author:** System Architect (for Cursor Agent)
