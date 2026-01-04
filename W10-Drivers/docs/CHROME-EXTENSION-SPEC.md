Document 2: CHROME-EXTENSION-SPEC.md
markdown# Chrome Extension - OSP Companion Specification

## Overview

This Chrome extension works with the Python OSP to guide an AI agent through posting workflows. It:
- Connects to the Python OSP via WebSocket
- Highlights elements the agent should click
- Detects when elements are clicked/focused
- Detects paste events
- Reports all interactions back to Python

---

## File Structure
```
osp-chrome-extension/
├── manifest.json
├── background.js
├── content.js
├── overlay.js
├── styles.css
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

---

## manifest.json
```json
{
    "manifest_version": 3,
    "name": "OSP Companion",
    "version": "1.0.0",
    "description": "Guides AI agents through posting workflows",
    
    "permissions": [
        "activeTab",
        "scripting",
        "tabs"
    ],
    
    "host_permissions": [
        ""
    ],
    
    "background": {
        "service_worker": "background.js"
    },
    
    "content_scripts": [
        {
            "matches": [""],
            "js": ["content.js", "overlay.js"],
            "css": ["styles.css"],
            "run_at": "document_idle"
        }
    ],
    
    "icons": {
        "16": "icons/icon16.png",
        "48": "icons/icon48.png",
        "128": "icons/icon128.png"
    }
}
```

---

## background.js
```javascript
/**
 * Background Service Worker
 * Manages WebSocket connection to Python OSP
 */

let socket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;
const WS_URL = 'ws://localhost:8765';

// Connect to Python OSP
function connectToOSP() {
    console.log('Connecting to OSP...');
    
    socket = new WebSocket(WS_URL);
    
    socket.onopen = () => {
        console.log('Connected to Python OSP');
        reconnectAttempts = 0;
        
        // Notify OSP we're ready
        sendToOSP('extension_ready', {
            timestamp: Date.now()
        });
        
        // Get current tab info
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                sendToOSP('extension_ready', {
                    tab_url: tabs[0].url,
                    tab_title: tabs[0].title
                });
            }
        });
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('From OSP:', data);
        handleOSPMessage(data);
    };
    
    socket.onclose = () => {
        console.log('Disconnected from OSP');
        socket = null;
        
        // Attempt reconnect
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            console.log(`Reconnecting in 3s (attempt ${reconnectAttempts})...`);
            setTimeout(connectToOSP, 3000);
        }
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

// Send message to Python OSP
function sendToOSP(type, payload = {}) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type, payload }));
    } else {
        console.warn('Cannot send - WebSocket not connected');
    }
}

// Handle messages from Python OSP
function handleOSPMessage(data) {
    const { type, payload } = data;
    
    // Forward to content script in active tab
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        if (tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, { type, payload });
        }
    });
    
    // Handle URL opening specially
    if (type === 'open_url') {
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.update(tabs[0].id, { url: payload.url });
            }
        });
    }
}

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target === 'background') {
        sendToOSP(message.type, message.payload);
    }
    return true;
});

// Listen for tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        // Detect platform from URL
        const platform = detectPlatform(tab.url);
        
        sendToOSP('page_loaded', {
            url: tab.url,
            title: tab.title,
            platform: platform
        });
    }
});

// Detect platform from URL
function detectPlatform(url) {
    if (url.includes('skool.com')) return 'skool';
    if (url.includes('instagram.com')) return 'instagram';
    if (url.includes('facebook.com')) return 'facebook';
    if (url.includes('tiktok.com')) return 'tiktok';
    if (url.includes('twitter.com') || url.includes('x.com')) return 'twitter';
    if (url.includes('linkedin.com')) return 'linkedin';
    return 'unknown';
}

// Start connection on load
connectToOSP();
```

---

## content.js
```javascript
/**
 * Content Script
 * Runs on every page to highlight elements and detect interactions
 */

// Current highlighted element
let highlightedElement = null;
let highlightOverlay = null;

// Listen for messages from background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const { type, payload } = message;
    
    switch (type) {
        case 'highlight_element':
            highlightElement(payload.selector, payload.label);
            break;
        
        case 'clear_highlights':
            clearHighlights();
            break;
        
        case 'request_page_info':
            sendPageInfo();
            break;
    }
    
    return true;
});

// Highlight an element with a label
function highlightElement(selector, label) {
    // Clear any existing highlight
    clearHighlights();
    
    // Find the element
    const element = document.querySelector(selector);
    if (!element) {
        console.warn(`Element not found: ${selector}`);
        // Try alternative selectors
        tryAlternativeSelectors(selector, label);
        return;
    }
    
    highlightedElement = element;
    
    // Create overlay
    highlightOverlay = document.createElement('div');
    highlightOverlay.className = 'osp-highlight-overlay';
    highlightOverlay.innerHTML = `
        ${label}
        ⬇
    `;
    
    // Position overlay
    positionOverlay(element);
    document.body.appendChild(highlightOverlay);
    
    // Add highlight to element
    element.classList.add('osp-highlighted-element');
    
    // Scroll element into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Add click listener
    element.addEventListener('click', onHighlightedElementClick);
    element.addEventListener('focus', onHighlightedElementFocus);
}

// Try alternative selectors if main one fails
function tryAlternativeSelectors(originalSelector, label) {
    const alternatives = {
        // Skool selectors
        "[data-placeholder='Title']": [
            'input[placeholder*="title" i]',
            '.title-input',
            'input[name="title"]',
            '[contenteditable="true"]:first-of-type'
        ],
        "[data-placeholder='Write something...']": [
            'textarea',
            '.body-input',
            '[contenteditable="true"]',
            'div[role="textbox"]'
        ]
    };
    
    const altList = alternatives[originalSelector] || [];
    for (const alt of altList) {
        const element = document.querySelector(alt);
        if (element) {
            console.log(`Found element with alternative selector: ${alt}`);
            highlightElement(alt, label);
            return;
        }
    }
    
    console.error(`Could not find element with any selector for: ${originalSelector}`);
}

// Position the overlay above the element
function positionOverlay(element) {
    const rect = element.getBoundingClientRect();
    
    highlightOverlay.style.position = 'fixed';
    highlightOverlay.style.left = `${rect.left + rect.width / 2}px`;
    highlightOverlay.style.top = `${rect.top - 60}px`;
    highlightOverlay.style.transform = 'translateX(-50%)';
    highlightOverlay.style.zIndex = '999999';
}

// Clear all highlights
function clearHighlights() {
    if (highlightOverlay) {
        highlightOverlay.remove();
        highlightOverlay = null;
    }
    
    if (highlightedElement) {
        highlightedElement.classList.remove('osp-highlighted-element');
        highlightedElement.removeEventListener('click', onHighlightedElementClick);
        highlightedElement.removeEventListener('focus', onHighlightedElementFocus);
        highlightedElement = null;
    }
    
    // Remove any lingering highlights
    document.querySelectorAll('.osp-highlighted-element').forEach(el => {
        el.classList.remove('osp-highlighted-element');
    });
    document.querySelectorAll('.osp-highlight-overlay').forEach(el => {
        el.remove();
    });
}

// Handle click on highlighted element
function onHighlightedElementClick(event) {
    const selector = getSelector(event.target);
    
    sendToBackground('element_clicked', {
        selector: selector,
        element_type: event.target.tagName.toLowerCase(),
        element_id: event.target.id,
        element_class: event.target.className
    });
}

// Handle focus on highlighted element
function onHighlightedElementFocus(event) {
    const selector = getSelector(event.target);
    
    sendToBackground('element_focused', {
        selector: selector,
        element_type: event.target.tagName.toLowerCase()
    });
    
    // Request copy from Python based on which field
    const placeholder = event.target.getAttribute('data-placeholder') || 
                        event.target.getAttribute('placeholder') || '';
    
    if (placeholder.toLowerCase().includes('title')) {
        sendToBackground('request_copy', { field: 'title' });
    } else if (placeholder.toLowerCase().includes('write') || 
               placeholder.toLowerCase().includes('body')) {
        sendToBackground('request_copy', { field: 'body' });
    }
}

// Detect paste events
document.addEventListener('paste', (event) => {
    const target = event.target;
    const selector = getSelector(target);
    
    // Wait a moment for paste to complete
    setTimeout(() => {
        const content = target.value || target.textContent || '';
        
        sendToBackground('paste_detected', {
            selector: selector,
            content_length: content.length,
            element_type: target.tagName.toLowerCase()
        });
    }, 100);
});

// Generate a selector for an element
function getSelector(element) {
    if (element.id) {
        return `#${element.id}`;
    }
    
    if (element.getAttribute('data-placeholder')) {
        return `[data-placeholder='${element.getAttribute('data-placeholder')}']`;
    }
    
    if (element.className && typeof element.className === 'string') {
        const classes = element.className.split(' ').filter(c => c).slice(0, 2);
        if (classes.length) {
            return `.${classes.join('.')}`;
        }
    }
    
    return element.tagName.toLowerCase();
}

// Send message to background script
function sendToBackground(type, payload) {
    chrome.runtime.sendMessage({
        target: 'background',
        type: type,
        payload: payload
    });
}

// Send page info
function sendPageInfo() {
    sendToBackground('page_info', {
        url: window.location.href,
        title: document.title,
        forms: document.querySelectorAll('form').length,
        inputs: document.querySelectorAll('input, textarea, [contenteditable]').length
    });
}

// Initialize
console.log('OSP Content Script loaded');
```

---

## styles.css
```css
/* Highlighted element style */
.osp-highlighted-element {
    outline: 4px solid #00ff00 !important;
    outline-offset: 2px !important;
    box-shadow: 0 0 20px rgba(0, 255, 0, 0.5) !important;
    animation: osp-pulse 1.5s ease-in-out infinite !important;
}

@keyframes osp-pulse {
    0%, 100% {
        box-shadow: 0 0 20px rgba(0, 255, 0, 0.5);
    }
    50% {
        box-shadow: 0 0 40px rgba(0, 255, 0, 0.8);
    }
}

/* Highlight overlay (label + arrow) */
.osp-highlight-overlay {
    position: fixed;
    z-index: 999999;
    display: flex;
    flex-direction: column;
    align-items: center;
    pointer-events: none;
    animation: osp-bounce 1s ease-in-out infinite;
}

@keyframes osp-bounce {
    0%, 100% {
        transform: translateX(-50%) translateY(0);
    }
    50% {
        transform: translateX(-50%) translateY(-10px);
    }
}

.osp-highlight-label {
    background: #00ff00;
    color: #000000;
    padding: 10px 20px;
    border-radius: 8px;
    font-family: Arial, sans-serif;
    font-size: 16px;
    font-weight: bold;
    white-space: nowrap;
    box-shadow: 0 4px 15px rgba(0, 255, 0, 0.4);
}

.osp-highlight-arrow {
    color: #00ff00;
    font-size: 30px;
    text-shadow: 0 0 10px rgba(0, 255, 0, 0.8);
    margin-top: -5px;
}

/* Different colors for different actions */
.osp-highlight-overlay.paste .osp-highlight-label {
    background: #00ffff;
    color: #000000;
}

.osp-highlight-overlay.paste .osp-highlight-arrow {
    color: #00ffff;
}

.osp-highlight-overlay.submit .osp-highlight-label {
    background: #ff6600;
    color: #ffffff;
}

.osp-highlight-overlay.submit .osp-highlight-arrow {
    color: #ff6600;
}
```

---

## overlay.js (Optional Enhanced Overlay)
```javascript
/**
 * Full-screen overlay for more prominent guidance
 * Can dim everything except the highlighted element
 */

class OSPOverlay {
    constructor() {
        this.overlay = null;
        this.spotlight = null;
    }
    
    show(targetElement, label) {
        this.hide();
        
        // Create full-screen overlay
        this.overlay = document.createElement('div');
        this.overlay.className = 'osp-fullscreen-overlay';
        this.overlay.innerHTML = `
            
            
                ${label}
            
        `;
        
        document.body.appendChild(this.overlay);
        
        // Position spotlight around target
        if (targetElement) {
            const rect = targetElement.getBoundingClientRect();
            const spotlight = this.overlay.querySelector('.osp-spotlight-container');
            
            spotlight.style.position = 'fixed';
            spotlight.style.left = `${rect.left - 10}px`;
            spotlight.style.top = `${rect.top - 50}px`;
            spotlight.style.width = `${rect.width + 20}px`;
            spotlight.style.height = `${rect.height + 60}px`;
        }
        
        // Click anywhere on overlay closes it and clicks through
        this.overlay.addEventListener('click', (e) => {
            if (targetElement && targetElement.contains(document.elementFromPoint(e.clientX, e.clientY))) {
                targetElement.focus();
                targetElement.click();
            }
            this.hide();
        });
    }
    
    hide() {
        if (this.overlay) {
            this.overlay.remove();
            this.overlay = null;
        }
    }
}

// Add styles for fullscreen overlay
const overlayStyles = document.createElement('style');
overlayStyles.textContent = `
    .osp-fullscreen-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        z-index: 999998;
        pointer-events: auto;
    }
    
    .osp-overlay-backdrop {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
    }
    
    .osp-spotlight-container {
        position: absolute;
        background: transparent;
        border: 4px solid #00ff00;
        border-radius: 8px;
        box-shadow: 0 0 0 9999px rgba(0, 0, 0, 0.7);
    }
    
    .osp-spotlight-label {
        position: absolute;
        top: -40px;
        left: 50%;
        transform: translateX(-50%);
        background: #00ff00;
        color: black;
        padding: 8px 16px;
        border-radius: 4px;
        font-weight: bold;
        white-space: nowrap;
    }
`;
document.head.appendChild(overlayStyles);

// Export for use in content.js
window.OSPOverlay = new OSPOverlay();
```

---

## Installation

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. Click "Load unpacked"
4. Select the `osp-chrome-extension` folder
5. The extension is now active

---

## Communication Flow Example
```
1. Agent sees "STEP 1: CLICK HERE" (green) on Python OSP
   └── Agent clicks it

2. Python lights up "OPEN URL" button (green)
   └── Agent clicks it
   └── Python sends: {"type": "open_url", "payload": {"url": "..."}}
   └── Chrome navigates to URL

3. Page loads, Chrome sends: {"type": "page_loaded", "payload": {...}}
   └── Python tells Chrome: {"type": "highlight_element", "payload": {...}}
   └── Chrome highlights the Title field with green box + "CLICK HERE - Title"

4. Agent clicks highlighted Title field in Chrome
   └── Chrome sends: {"type": "element_focused", "payload": {...}}
   └── Chrome sends: {"type": "request_copy", "payload": {"field": "title"}}
   └── Python lights up "COPY TITLE" button (green)

5. Agent clicks "COPY TITLE" in Python OSP
   └── Title copied to clipboard
   └── Python tells Chrome: {"type": "highlight_element", ...}
   └── Chrome shows "CLICK HERE & PASTE (Ctrl+V)"

6. Agent clicks and pastes (Ctrl+V)
   └── Chrome sends: {"type": "paste_detected", "payload": {...}}
   └── Flow continues to Body field...

... continues until post is submitted
```

---

## Platform-Specific Selectors
```javascript
const PLATFORM_SELECTORS = {
    skool: {
        title: "[data-placeholder='Title']",
        body: "[data-placeholder='Write something...']",
        submit: "button[type='submit']"
    },
    instagram: {
        caption: "textarea[aria-label='Write a caption...']",
        share: "button:contains('Share')"
    },
    facebook: {
        post_input: "[data-placeholder='What's on your mind']",
        post_button: "[aria-label='Post']"
    }
};
```