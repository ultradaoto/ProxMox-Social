# OSP Companion Extension - V2.0
# Computer Vision UI Element Highlighter

## MISSION: Static UI Element Visualization for Computer Vision

**Old Mission**: Dynamic overlays for AI to read instructions
**New Mission**: Static green rectangles and text labels to help computer vision identify clickable areas

---

## Core Concept

This Chrome extension **permanently highlights** specific UI elements on social media platforms with:
- **Green rectangles** around clickable areas
- **Clear text labels** like "Click here to edit title"
- **Static positioning** - always visible, never changes
- **No AI communication** - just visual aids for computer vision

### Why This Works

Computer vision models (like Qwen2.5-VL) can easily detect:
- Bright green rectangles (high contrast, unique color)
- Clear text labels in predictable positions
- Consistent visual patterns across pages

---

## Platform-Specific Highlighting Rules

### Skool.com (Primary Example)

**Page Detection**: `skool.com/groups/*/posts/new`

**Elements to Highlight:**

1. **Title Entry Area**
   - **Selector**: The hidden title input (usually first text field when "Write something..." is clicked)
   - **Visual**: Green rectangle around the clickable "Write something..." area
   - **Text Label**: "Click here to edit title"
   - **Position**: Top-left corner of the rectangle

2. **Body Entry Area**
   - **Selector**: The hidden body input (usually second text field)
   - **Visual**: Green rectangle around the body text area
   - **Text Label**: "Click here to enter body text and click here to paste media files"
   - **Position**: Top-left corner of the rectangle

3. **Post Button**
   - **Selector**: The main submit/post button (usually at bottom of form)
   - **Visual**: Green rectangle around the button
   - **Text Label**: "Click here to post"
   - **Position**: Center of button

4. **Email Toggle**
   - **Selector**: Checkbox to send post to group email
   - **Visual**: Green rectangle around the toggle area
   - **Text Label**: "Email toggle button"
   - **Position**: Right side of toggle

### Instagram.com

**Page Detection**: `instagram.com/*`

**Elements to Highlight:**

1. **Create Post Button**
   - **Selector**: Plus icon or "Create" button in left sidebar
   - **Visual**: Green circle around the icon
   - **Text Label**: "Click here to create post"

2. **Upload Area**
   - **Selector**: Drag & drop area or "Select from computer" button
   - **Visual**: Green rectangle around upload area
   - **Text Label**: "Click here to select media"

3. **Caption Field**
   - **Selector**: "Write a caption..." text area
   - **Visual**: Green rectangle around text input
   - **Text Label**: "Click here to enter caption"

4. **Share Button**
   - **Selector**: Blue "Share" button
   - **Visual**: Green rectangle around button
   - **Text Label**: "Click here to share post"

### Facebook.com

**Page Detection**: `facebook.com/*`

**Elements to Highlight:**

1. **Create Post Button**
   - **Selector**: "What's on your mind?" box or Create Post button
   - **Visual**: Green rectangle around clickable area
   - **Text Label**: "Click here to create post"

2. **Text Input Area**
   - **Selector**: Main post text area
   - **Visual**: Green rectangle around text field
   - **Text Label**: "Click here to enter post text"

3. **Photo/Video Button**
   - **Selector**: Photo/video upload button
   - **Visual**: Green rectangle around button
   - **Text Label**: "Click here to add media"

4. **Post Button**
   - **Selector**: Main post/submit button
   - **Visual**: Green rectangle around button
   - **Text Label**: "Click here to post"

### TikTok.com

**Page Detection**: `tiktok.com/*`

**Elements to Highlight:**

1. **Upload Button**
   - **Selector**: Main upload/create button
   - **Visual**: Green rectangle around button
   - **Text Label**: "Click here to upload video"

2. **Caption Field**
   - **Selector**: Video description text area
   - **Visual**: Green rectangle around text field
   - **Text Label**: "Click here to enter caption"

3. **Post Button**
   - **Selector**: Publish/upload button
   - **Visual**: Green rectangle around button
   - **Text Label**: "Click here to post video"

---

## Technical Implementation

### Architecture

```
┌─────────────────┐
│ Content Script  │ ← Detects current page URL
│                 │ ← Finds elements using selectors
│                 │ ← Draws persistent green overlays
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Background      │ ← Manages extension lifecycle
│ Service Worker  │ ← Handles page navigation
└─────────────────┘
```

### Key Files to Modify

#### 1. `manifest.json` - Update Permissions
```json
{
  "manifest_version": 3,
  "name": "OSP Vision Helper",
  "description": "Highlights UI elements for computer vision",
  "permissions": [
    "activeTab",
    "scripting"
  ],
  "host_permissions": [
    "*://*.skool.com/*",
    "*://*.instagram.com/*",
    "*://*.facebook.com/*",
    "*://*.tiktok.com/*"
  ],
  "content_scripts": [
    {
      "matches": [
        "*://*.skool.com/*",
        "*://*.instagram.com/*",
        "*://*.facebook.com/*",
        "*://*.tiktok.com/*"
      ],
      "js": ["content/content.js"],
      "css": ["content/styles.css"],
      "run_at": "document_end"
    }
  ]
}
```

#### 2. `content/content.js` - Main Logic

**Page Detection & Element Highlighting:**
```javascript
(function() {
    'use strict';

    // Platform-specific highlighting rules
    const PLATFORM_RULES = {
        'skool.com': {
            pages: ['/posts/new'],
            elements: [
                {
                    name: 'title-entry',
                    selectors: ['[placeholder*="Write something"]', '.write-something-input'],
                    label: 'Click here to edit title',
                    style: 'rectangle'
                },
                {
                    name: 'body-entry',
                    selectors: ['.body-input', '[contenteditable="true"]'],
                    label: 'Click here to enter body text and click here to paste media files',
                    style: 'rectangle'
                },
                {
                    name: 'post-button',
                    selectors: ['button[type="submit"]', '.post-button', '[aria-label="Post"]'],
                    label: 'Click here to post',
                    style: 'rectangle'
                },
                {
                    name: 'email-toggle',
                    selectors: ['input[type="checkbox"]', '.email-toggle'],
                    label: 'Email toggle button',
                    style: 'rectangle'
                }
            ]
        },
        'instagram.com': {
            pages: ['*'],
            elements: [
                {
                    name: 'create-button',
                    selectors: ['[aria-label="New post"]', '.create-button'],
                    label: 'Click here to create post',
                    style: 'circle'
                }
                // ... more Instagram elements
            ]
        }
        // ... other platforms
    };

    function initHighlights() {
        const hostname = window.location.hostname;
        const pathname = window.location.pathname;

        // Find matching platform
        for (const [domain, rules] of Object.entries(PLATFORM_RULES)) {
            if (hostname.includes(domain)) {
                // Check if page matches
                const pageMatches = rules.pages.some(page =>
                    pathname.includes(page) || page === '*'
                );

                if (pageMatches) {
                    console.log(`[OSP] Applying ${domain} highlights`);
                    applyHighlights(rules.elements);
                    return;
                }
            }
        }
    }

    function applyHighlights(elements) {
        elements.forEach(elementRule => {
            const element = findElement(elementRule.selectors);
            if (element) {
                createHighlight(element, elementRule);
            }
        });
    }

    function findElement(selectors) {
        for (const selector of selectors) {
            try {
                const element = document.querySelector(selector);
                if (element) return element;
            } catch (e) {
                // Invalid selector, continue
            }
        }
        return null;
    }

    function createHighlight(element, rule) {
        // Create highlight overlay
        const overlay = document.createElement('div');
        overlay.className = `osp-highlight osp-${rule.style}`;
        overlay.setAttribute('data-element', rule.name);

        // Position overlay
        const rect = element.getBoundingClientRect();
        overlay.style.left = `${rect.left + window.scrollX}px`;
        overlay.style.top = `${rect.top + window.scrollY}px`;
        overlay.style.width = `${rect.width}px`;
        overlay.style.height = `${rect.height}px`;

        // Add label
        const label = document.createElement('div');
        label.className = 'osp-label';
        label.textContent = rule.label;
        overlay.appendChild(label);

        document.body.appendChild(overlay);

        // Update position on scroll/resize
        const updatePosition = () => {
            const newRect = element.getBoundingClientRect();
            overlay.style.left = `${newRect.left + window.scrollX}px`;
            overlay.style.top = `${newRect.top + window.scrollY}px`;
        };

        window.addEventListener('scroll', updatePosition);
        window.addEventListener('resize', updatePosition);
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHighlights);
    } else {
        initHighlights();
    }

    // Re-apply highlights on navigation (SPA support)
    let currentPath = window.location.pathname;
    const observer = new MutationObserver(() => {
        if (window.location.pathname !== currentPath) {
            currentPath = window.location.pathname;
            // Clear existing highlights
            document.querySelectorAll('.osp-highlight').forEach(el => el.remove());
            // Re-apply after short delay
            setTimeout(initHighlights, 500);
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();
```

#### 3. `content/styles.css` - Visual Styling

```css
/* OSP Highlight Styles */
.osp-highlight {
    position: absolute;
    pointer-events: none;
    z-index: 999999;
    border: 3px solid #10b981; /* Bright green border */
    background-color: rgba(16, 185, 129, 0.1); /* Subtle green background */
    border-radius: 4px;
}

.osp-highlight.rectangle {
    /* Standard rectangle highlight */
}

.osp-highlight.circle {
    border-radius: 50%;
}

.osp-label {
    position: absolute;
    top: -28px;
    left: 0;
    background-color: #10b981;
    color: white;
    padding: 4px 8px;
    border-radius: 4px;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 12px;
    font-weight: 600;
    white-space: nowrap;
    max-width: 300px;
    word-wrap: break-word;
}

/* Ensure highlights don't interfere with interactions */
.osp-highlight * {
    pointer-events: none !important;
}

/* Hide highlights when printing */
@media print {
    .osp-highlight {
        display: none !important;
    }
}
```

#### 4. `background/background.js` - Lifecycle Management

```javascript
// Simple background script - just keep extension alive
chrome.runtime.onInstalled.addListener(() => {
    console.log('[OSP Vision Helper] Installed');
});

// Handle extension icon clicks (optional settings)
chrome.action.onClicked.addListener((tab) => {
    // Could open settings page in future
    console.log('[OSP Vision Helper] Icon clicked');
});
```

---

## Development Workflow

### 1. **Start with Skool.com**
   - Focus on the example you provided
   - Get title, body, post button, and email toggle working
   - Test that highlights appear consistently

### 2. **Add Instagram Support**
   - Implement create button, upload area, caption field, share button
   - Test on actual Instagram pages

### 3. **Expand to Other Platforms**
   - Facebook, TikTok, LinkedIn
   - Reuse patterns where possible

### 4. **Polish & Testing**
   - Handle dynamic content loading (SPAs)
   - Test across different screen sizes
   - Ensure highlights don't interfere with normal usage

---

## Key Technical Considerations

### Element Detection Strategy
1. **Primary**: Use reliable CSS selectors
2. **Fallback**: Look for common patterns (placeholder text, ARIA labels)
3. **Last Resort**: Position-based detection (nth-child, etc.)

### Performance
- Only run on supported domains
- Use efficient selectors
- Debounce position updates

### Maintenance
- Elements change frequently on social media platforms
- Plan for regular updates to selectors
- Consider user feedback mechanism for broken highlights

---

## Integration with Computer Vision

When Ubuntu takes a VNC screenshot, the vision model will see:
- **Clear green rectangles** around clickable areas
- **Readable text labels** explaining what each area does
- **Consistent positioning** across all pages

This makes it trivial for the vision model to answer questions like:
- "Where is the title input field?" → "Look for the green rectangle labeled 'Click here to edit title'"
- "Where is the post button?" → "Look for the green rectangle labeled 'Click here to post'"

---

## Success Criteria

✅ **Skool.com highlights work**: All 4 elements (title, body, post button, email toggle) are clearly marked
✅ **Instagram highlights work**: Create, upload, caption, and share elements are marked
✅ **No interference**: Normal browsing and posting still works
✅ **Computer vision friendly**: Clear, consistent visual patterns
✅ **Maintainable**: Easy to update when platforms change their UI

---

*This extension transforms social media platforms into computer-vision-friendly interfaces by permanently highlighting the elements that matter for automated posting.*