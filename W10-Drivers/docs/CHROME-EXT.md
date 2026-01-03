# Chrome Extension: Element Blocker & Color Picker

## Overview

A Chrome extension that provides two powerful features:
1. **Element Blocker** - Click to hide any element on a webpage (persisted per-site)
2. **Color Picker** - Extract colors from any element on the page

Perfect for customizing your social media experience (Facebook, Instagram, TikTok) and extracting brand colors for development work.

---

## Features

### 1. Element Blocker
- **Click-to-hide mode**: Activate, then click any element to hide it
- **Element highlighting**: Visual preview before blocking
- **Persistent blocking**: Hidden elements stay hidden across page loads
- **Site-specific rules**: Each website has its own blocked element list
- **Undo/restore**: Easily restore accidentally hidden elements
- **CSS selector storage**: Stores robust selectors that survive page updates
- **Bulk management**: View and manage all blocked elements per site

### 2. Color Picker (Eye Dropper)
- **Click any element** to extract its colors
- **Shows multiple color values**:
  - Background color
  - Text color
  - Border color
  - Gradient colors
- **Copy in multiple formats**: HEX, RGB, HSL
- **Color history**: Recent picks saved per session
- **Works on images**: Extract colors from image pixels

### 3. Site Presets
- Pre-configured blocking rules for common annoyances:
  - Facebook: Suggested posts, Reels, Marketplace sidebar
  - Instagram: Suggested posts, Shop tab
  - TikTok: Live streams, Shopping
  - YouTube: Shorts shelf, Comments

---

## Technical Architecture

### Manifest V3 Structure

```
element-blocker-extension/
├── manifest.json
├── background/
│   └── service-worker.js      # Background service worker
├── content/
│   ├── content.js             # Main content script
│   ├── element-picker.js      # Element selection logic
│   ├── color-picker.js        # Color extraction logic
│   └── styles.css             # Overlay and highlight styles
├── popup/
│   ├── popup.html             # Extension popup UI
│   ├── popup.js               # Popup logic
│   └── popup.css              # Popup styles
├── options/
│   ├── options.html           # Full settings page
│   ├── options.js
│   └── options.css
├── lib/
│   ├── selector-generator.js  # Generate robust CSS selectors
│   ├── storage-manager.js     # Chrome storage wrapper
│   └── color-utils.js         # Color conversion utilities
├── icons/
│   ├── icon-16.png
│   ├── icon-32.png
│   ├── icon-48.png
│   └── icon-128.png
└── _locales/
    └── en/
        └── messages.json
```

---

## Core Files

### manifest.json

```json
{
  "manifest_version": 3,
  "name": "Element Blocker & Color Picker",
  "version": "1.0.0",
  "description": "Hide annoying elements and extract colors from any webpage",
  
  "permissions": [
    "storage",
    "activeTab",
    "scripting",
    "contextMenus"
  ],
  
  "host_permissions": [
    "<all_urls>"
  ],
  
  "background": {
    "service_worker": "background/service-worker.js"
  },
  
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": [
        "lib/selector-generator.js",
        "lib/storage-manager.js",
        "content/content.js"
      ],
      "css": ["content/styles.css"],
      "run_at": "document_end"
    }
  ],
  
  "action": {
    "default_popup": "popup/popup.html",
    "default_icon": {
      "16": "icons/icon-16.png",
      "32": "icons/icon-32.png",
      "48": "icons/icon-48.png",
      "128": "icons/icon-128.png"
    }
  },
  
  "options_page": "options/options.html",
  
  "icons": {
    "16": "icons/icon-16.png",
    "32": "icons/icon-32.png",
    "48": "icons/icon-48.png",
    "128": "icons/icon-128.png"
  },
  
  "commands": {
    "toggle-element-picker": {
      "suggested_key": {
        "default": "Alt+Shift+B"
      },
      "description": "Toggle element blocker mode"
    },
    "toggle-color-picker": {
      "suggested_key": {
        "default": "Alt+Shift+C"
      },
      "description": "Toggle color picker mode"
    }
  }
}
```

### background/service-worker.js

```javascript
/**
 * Background Service Worker
 * Handles message routing, context menus, and storage coordination
 */

// Initialize context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'block-element',
    title: 'Block this element',
    contexts: ['all']
  });
  
  chrome.contextMenus.create({
    id: 'pick-color',
    title: 'Pick color from element',
    contexts: ['all']
  });
  
  // Initialize storage structure
  chrome.storage.local.get(['sites'], (result) => {
    if (!result.sites) {
      chrome.storage.local.set({ sites: {} });
    }
  });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === 'block-element') {
    chrome.tabs.sendMessage(tab.id, { 
      action: 'startBlockerMode',
      clickCoords: { x: info.x, y: info.y }
    });
  } else if (info.menuItemId === 'pick-color') {
    chrome.tabs.sendMessage(tab.id, {
      action: 'startColorPickerMode',
      clickCoords: { x: info.x, y: info.y }
    });
  }
});

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener((command, tab) => {
  if (command === 'toggle-element-picker') {
    chrome.tabs.sendMessage(tab.id, { action: 'toggleBlockerMode' });
  } else if (command === 'toggle-color-picker') {
    chrome.tabs.sendMessage(tab.id, { action: 'toggleColorPickerMode' });
  }
});

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  switch (request.action) {
    case 'getBlockedElements':
      getBlockedElements(request.hostname).then(sendResponse);
      return true;
      
    case 'blockElement':
      blockElement(request.hostname, request.selector, request.description)
        .then(sendResponse);
      return true;
      
    case 'unblockElement':
      unblockElement(request.hostname, request.selector).then(sendResponse);
      return true;
      
    case 'getColorHistory':
      getColorHistory().then(sendResponse);
      return true;
      
    case 'saveColor':
      saveColor(request.color).then(sendResponse);
      return true;
  }
});

// Storage functions
async function getBlockedElements(hostname) {
  const result = await chrome.storage.local.get(['sites']);
  const sites = result.sites || {};
  return sites[hostname]?.blockedElements || [];
}

async function blockElement(hostname, selector, description) {
  const result = await chrome.storage.local.get(['sites']);
  const sites = result.sites || {};
  
  if (!sites[hostname]) {
    sites[hostname] = { blockedElements: [], settings: {} };
  }
  
  // Check if already blocked
  const exists = sites[hostname].blockedElements.some(
    el => el.selector === selector
  );
  
  if (!exists) {
    sites[hostname].blockedElements.push({
      selector,
      description,
      createdAt: new Date().toISOString(),
      enabled: true
    });
    
    await chrome.storage.local.set({ sites });
  }
  
  return { success: true };
}

async function unblockElement(hostname, selector) {
  const result = await chrome.storage.local.get(['sites']);
  const sites = result.sites || {};
  
  if (sites[hostname]) {
    sites[hostname].blockedElements = sites[hostname].blockedElements.filter(
      el => el.selector !== selector
    );
    await chrome.storage.local.set({ sites });
  }
  
  return { success: true };
}

async function getColorHistory() {
  const result = await chrome.storage.local.get(['colorHistory']);
  return result.colorHistory || [];
}

async function saveColor(color) {
  const result = await chrome.storage.local.get(['colorHistory']);
  let history = result.colorHistory || [];
  
  // Add to front, remove duplicates, limit to 50
  history = history.filter(c => c.hex !== color.hex);
  history.unshift(color);
  history = history.slice(0, 50);
  
  await chrome.storage.local.set({ colorHistory: history });
  return { success: true };
}
```

### lib/selector-generator.js

```javascript
/**
 * Generates robust CSS selectors for elements
 * Prioritizes stable selectors that survive page updates
 */

class SelectorGenerator {
  
  /**
   * Generate the most robust selector for an element
   */
  static generate(element) {
    // Try strategies in order of robustness
    const strategies = [
      this.byDataAttribute,
      this.byAriaLabel,
      this.byRole,
      this.byId,
      this.byUniqueClass,
      this.byNthChild,
      this.byFullPath
    ];
    
    for (const strategy of strategies) {
      const selector = strategy.call(this, element);
      if (selector && this.isUnique(selector)) {
        return selector;
      }
    }
    
    // Fallback to full path
    return this.byFullPath(element);
  }
  
  /**
   * Check if selector uniquely identifies one element
   */
  static isUnique(selector) {
    try {
      const matches = document.querySelectorAll(selector);
      return matches.length === 1;
    } catch {
      return false;
    }
  }
  
  /**
   * Strategy: Use data-* attributes (very stable)
   */
  static byDataAttribute(element) {
    const dataAttrs = Array.from(element.attributes)
      .filter(attr => attr.name.startsWith('data-'))
      .filter(attr => attr.value && !attr.value.includes(' '));
    
    for (const attr of dataAttrs) {
      // Skip dynamic-looking values
      if (/^[0-9]+$/.test(attr.value)) continue;
      if (attr.value.length > 50) continue;
      
      const selector = `[${attr.name}="${CSS.escape(attr.value)}"]`;
      if (this.isUnique(selector)) return selector;
    }
    
    return null;
  }
  
  /**
   * Strategy: Use aria-label (stable for accessibility)
   */
  static byAriaLabel(element) {
    const ariaLabel = element.getAttribute('aria-label');
    if (ariaLabel && ariaLabel.length < 100) {
      return `[aria-label="${CSS.escape(ariaLabel)}"]`;
    }
    return null;
  }
  
  /**
   * Strategy: Use role attribute
   */
  static byRole(element) {
    const role = element.getAttribute('role');
    if (!role) return null;
    
    // Combine with other attributes for uniqueness
    const ariaLabel = element.getAttribute('aria-label');
    if (ariaLabel) {
      return `[role="${role}"][aria-label="${CSS.escape(ariaLabel)}"]`;
    }
    
    return null;
  }
  
  /**
   * Strategy: Use ID (careful - some IDs are dynamic)
   */
  static byId(element) {
    const id = element.id;
    if (!id) return null;
    
    // Skip dynamic-looking IDs
    if (/^[0-9]+$/.test(id)) return null;
    if (id.length > 50) return null;
    if (/[0-9]{4,}/.test(id)) return null; // Contains long numbers
    
    return `#${CSS.escape(id)}`;
  }
  
  /**
   * Strategy: Use unique class combination
   */
  static byUniqueClass(element) {
    const classes = Array.from(element.classList)
      .filter(c => !c.match(/^[0-9]/)) // Skip classes starting with numbers
      .filter(c => c.length < 50)       // Skip very long classes
      .filter(c => !c.includes(':'));   // Skip pseudo-selectors
    
    if (classes.length === 0) return null;
    
    // Try single classes first
    for (const cls of classes) {
      const selector = `.${CSS.escape(cls)}`;
      if (this.isUnique(selector)) return selector;
    }
    
    // Try combinations
    for (let i = 0; i < classes.length; i++) {
      for (let j = i + 1; j < classes.length; j++) {
        const selector = `.${CSS.escape(classes[i])}.${CSS.escape(classes[j])}`;
        if (this.isUnique(selector)) return selector;
      }
    }
    
    return null;
  }
  
  /**
   * Strategy: Use nth-child with parent context
   */
  static byNthChild(element) {
    const parent = element.parentElement;
    if (!parent) return null;
    
    const siblings = Array.from(parent.children);
    const index = siblings.indexOf(element) + 1;
    const tagName = element.tagName.toLowerCase();
    
    // Get parent selector
    let parentSelector = '';
    
    if (parent.id && !/[0-9]{4,}/.test(parent.id)) {
      parentSelector = `#${CSS.escape(parent.id)}`;
    } else {
      const parentClasses = Array.from(parent.classList)
        .filter(c => c.length < 30)
        .slice(0, 2);
      if (parentClasses.length > 0) {
        parentSelector = parentClasses.map(c => `.${CSS.escape(c)}`).join('');
      }
    }
    
    if (parentSelector) {
      return `${parentSelector} > ${tagName}:nth-child(${index})`;
    }
    
    return null;
  }
  
  /**
   * Strategy: Full path from closest stable ancestor
   */
  static byFullPath(element) {
    const path = [];
    let current = element;
    
    while (current && current !== document.body) {
      const parent = current.parentElement;
      if (!parent) break;
      
      const siblings = Array.from(parent.children).filter(
        el => el.tagName === current.tagName
      );
      
      let segment = current.tagName.toLowerCase();
      
      if (siblings.length > 1) {
        const index = siblings.indexOf(current) + 1;
        segment += `:nth-of-type(${index})`;
      }
      
      path.unshift(segment);
      current = parent;
      
      // Stop at stable anchor
      if (current.id && !/[0-9]{4,}/.test(current.id)) {
        path.unshift(`#${CSS.escape(current.id)}`);
        break;
      }
    }
    
    return path.join(' > ');
  }
  
  /**
   * Get human-readable description of element
   */
  static getDescription(element) {
    // Try various attributes for description
    const ariaLabel = element.getAttribute('aria-label');
    if (ariaLabel) return ariaLabel;
    
    const title = element.getAttribute('title');
    if (title) return title;
    
    const text = element.textContent?.trim();
    if (text && text.length < 50) return text;
    
    const placeholder = element.getAttribute('placeholder');
    if (placeholder) return placeholder;
    
    // Fallback to tag + class
    const classes = Array.from(element.classList).slice(0, 2).join(' ');
    return `${element.tagName.toLowerCase()}${classes ? ' (' + classes + ')' : ''}`;
  }
}

// Export for use in content script
if (typeof window !== 'undefined') {
  window.SelectorGenerator = SelectorGenerator;
}
```

### lib/storage-manager.js

```javascript
/**
 * Storage Manager
 * Wrapper for Chrome storage with caching
 */

class StorageManager {
  constructor() {
    this.cache = {};
    this.hostname = window.location.hostname;
  }
  
  async getBlockedSelectors() {
    if (this.cache.blocked) {
      return this.cache.blocked;
    }
    
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { action: 'getBlockedElements', hostname: this.hostname },
        (response) => {
          this.cache.blocked = response || [];
          resolve(this.cache.blocked);
        }
      );
    });
  }
  
  async blockElement(selector, description) {
    // Clear cache
    this.cache.blocked = null;
    
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'blockElement',
        hostname: this.hostname,
        selector,
        description
      }, resolve);
    });
  }
  
  async unblockElement(selector) {
    // Clear cache
    this.cache.blocked = null;
    
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'unblockElement',
        hostname: this.hostname,
        selector
      }, resolve);
    });
  }
  
  async saveColor(color) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({
        action: 'saveColor',
        color
      }, resolve);
    });
  }
  
  async getColorHistory() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { action: 'getColorHistory' },
        resolve
      );
    });
  }
}

if (typeof window !== 'undefined') {
  window.StorageManager = StorageManager;
}
```

### lib/color-utils.js

```javascript
/**
 * Color Utilities
 * Extract and convert colors
 */

class ColorUtils {
  
  /**
   * Get all colors from an element
   */
  static getElementColors(element) {
    const styles = window.getComputedStyle(element);
    
    const colors = {
      background: this.parseColor(styles.backgroundColor),
      text: this.parseColor(styles.color),
      border: this.parseColor(styles.borderColor),
    };
    
    // Check for gradient
    const bgImage = styles.backgroundImage;
    if (bgImage && bgImage !== 'none' && bgImage.includes('gradient')) {
      colors.gradient = this.extractGradientColors(bgImage);
    }
    
    return colors;
  }
  
  /**
   * Parse any CSS color to RGB
   */
  static parseColor(cssColor) {
    if (!cssColor || cssColor === 'transparent' || cssColor === 'rgba(0, 0, 0, 0)') {
      return null;
    }
    
    // Create temporary element to parse color
    const temp = document.createElement('div');
    temp.style.color = cssColor;
    document.body.appendChild(temp);
    
    const computed = window.getComputedStyle(temp).color;
    document.body.removeChild(temp);
    
    // Parse rgb/rgba format
    const match = computed.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
    if (match) {
      return {
        r: parseInt(match[1]),
        g: parseInt(match[2]),
        b: parseInt(match[3]),
        hex: this.rgbToHex(parseInt(match[1]), parseInt(match[2]), parseInt(match[3])),
        rgb: `rgb(${match[1]}, ${match[2]}, ${match[3]})`,
        hsl: this.rgbToHsl(parseInt(match[1]), parseInt(match[2]), parseInt(match[3]))
      };
    }
    
    return null;
  }
  
  /**
   * Extract colors from gradient
   */
  static extractGradientColors(gradientStr) {
    const colorRegex = /#[0-9A-Fa-f]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\)/g;
    const matches = gradientStr.match(colorRegex);
    
    if (matches) {
      return matches.map(c => this.parseColor(c)).filter(Boolean);
    }
    
    return [];
  }
  
  /**
   * Get color at specific point in image
   */
  static getPixelColor(img, x, y) {
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth || img.width;
    canvas.height = img.naturalHeight || img.height;
    
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    
    // Calculate position relative to image
    const rect = img.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    const imgX = Math.floor((x - rect.left) * scaleX);
    const imgY = Math.floor((y - rect.top) * scaleY);
    
    const pixel = ctx.getImageData(imgX, imgY, 1, 1).data;
    
    return {
      r: pixel[0],
      g: pixel[1],
      b: pixel[2],
      hex: this.rgbToHex(pixel[0], pixel[1], pixel[2]),
      rgb: `rgb(${pixel[0]}, ${pixel[1]}, ${pixel[2]})`,
      hsl: this.rgbToHsl(pixel[0], pixel[1], pixel[2])
    };
  }
  
  /**
   * Convert RGB to HEX
   */
  static rgbToHex(r, g, b) {
    return '#' + [r, g, b].map(x => {
      const hex = x.toString(16);
      return hex.length === 1 ? '0' + hex : hex;
    }).join('').toUpperCase();
  }
  
  /**
   * Convert RGB to HSL
   */
  static rgbToHsl(r, g, b) {
    r /= 255;
    g /= 255;
    b /= 255;
    
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h, s, l = (max + min) / 2;
    
    if (max === min) {
      h = s = 0;
    } else {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      
      switch (max) {
        case r: h = ((g - b) / d + (g < b ? 6 : 0)) / 6; break;
        case g: h = ((b - r) / d + 2) / 6; break;
        case b: h = ((r - g) / d + 4) / 6; break;
      }
    }
    
    return `hsl(${Math.round(h * 360)}°, ${Math.round(s * 100)}%, ${Math.round(l * 100)}%)`;
  }
}

if (typeof window !== 'undefined') {
  window.ColorUtils = ColorUtils;
}
```

### content/content.js

```javascript
/**
 * Content Script
 * Main entry point for page interaction
 */

(function() {
  'use strict';
  
  // State
  let isBlockerMode = false;
  let isColorPickerMode = false;
  let highlightedElement = null;
  let overlay = null;
  let tooltip = null;
  
  // Initialize
  const storage = new StorageManager();
  
  // Apply blocked elements on page load
  applyBlockedElements();
  
  // Watch for dynamic content
  const observer = new MutationObserver(() => {
    if (!isBlockerMode && !isColorPickerMode) {
      applyBlockedElements();
    }
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // Listen for messages from popup/background
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch (request.action) {
      case 'startBlockerMode':
        startBlockerMode();
        break;
      case 'toggleBlockerMode':
        isBlockerMode ? stopBlockerMode() : startBlockerMode();
        break;
      case 'startColorPickerMode':
        startColorPickerMode();
        break;
      case 'toggleColorPickerMode':
        isColorPickerMode ? stopColorPickerMode() : startColorPickerMode();
        break;
      case 'restoreElement':
        restoreElement(request.selector);
        break;
      case 'refreshBlocked':
        applyBlockedElements();
        break;
    }
    sendResponse({ success: true });
  });
  
  /**
   * Apply all blocked elements
   */
  async function applyBlockedElements() {
    const blocked = await storage.getBlockedSelectors();
    
    blocked.forEach(item => {
      if (!item.enabled) return;
      
      try {
        const elements = document.querySelectorAll(item.selector);
        elements.forEach(el => {
          el.style.setProperty('display', 'none', 'important');
          el.dataset.elementBlockerHidden = 'true';
        });
      } catch (e) {
        console.warn('Invalid selector:', item.selector);
      }
    });
  }
  
  /**
   * Restore a blocked element
   */
  async function restoreElement(selector) {
    await storage.unblockElement(selector);
    
    try {
      const elements = document.querySelectorAll(selector);
      elements.forEach(el => {
        el.style.removeProperty('display');
        delete el.dataset.elementBlockerHidden;
      });
    } catch (e) {
      console.warn('Could not restore:', selector);
    }
  }
  
  // ============================================
  // ELEMENT BLOCKER MODE
  // ============================================
  
  function startBlockerMode() {
    if (isColorPickerMode) stopColorPickerMode();
    
    isBlockerMode = true;
    createOverlay('blocker');
    document.body.style.cursor = 'crosshair';
    
    document.addEventListener('mouseover', onBlockerHover, true);
    document.addEventListener('click', onBlockerClick, true);
    document.addEventListener('keydown', onEscape);
  }
  
  function stopBlockerMode() {
    isBlockerMode = false;
    removeOverlay();
    document.body.style.cursor = '';
    unhighlightElement();
    
    document.removeEventListener('mouseover', onBlockerHover, true);
    document.removeEventListener('click', onBlockerClick, true);
    document.removeEventListener('keydown', onEscape);
  }
  
  function onBlockerHover(e) {
    if (!isBlockerMode) return;
    
    const target = e.target;
    
    // Don't highlight our own overlay
    if (target.closest('.element-blocker-overlay')) return;
    
    highlightElement(target, 'rgba(255, 0, 0, 0.3)');
    showTooltip(target, 'Click to block this element');
  }
  
  async function onBlockerClick(e) {
    if (!isBlockerMode) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const target = e.target;
    
    // Don't block our own overlay
    if (target.closest('.element-blocker-overlay')) return;
    
    const selector = SelectorGenerator.generate(target);
    const description = SelectorGenerator.getDescription(target);
    
    // Hide the element
    target.style.setProperty('display', 'none', 'important');
    target.dataset.elementBlockerHidden = 'true';
    
    // Save to storage
    await storage.blockElement(selector, description);
    
    // Show confirmation
    showNotification(`Blocked: ${description}`);
    
    // Stay in blocker mode for more blocking
    unhighlightElement();
  }
  
  // ============================================
  // COLOR PICKER MODE
  // ============================================
  
  function startColorPickerMode() {
    if (isBlockerMode) stopBlockerMode();
    
    isColorPickerMode = true;
    createOverlay('color');
    document.body.style.cursor = 'crosshair';
    
    document.addEventListener('mouseover', onColorHover, true);
    document.addEventListener('click', onColorClick, true);
    document.addEventListener('keydown', onEscape);
  }
  
  function stopColorPickerMode() {
    isColorPickerMode = false;
    removeOverlay();
    document.body.style.cursor = '';
    unhighlightElement();
    
    document.removeEventListener('mouseover', onColorHover, true);
    document.removeEventListener('click', onColorClick, true);
    document.removeEventListener('keydown', onEscape);
  }
  
  function onColorHover(e) {
    if (!isColorPickerMode) return;
    
    const target = e.target;
    if (target.closest('.element-blocker-overlay')) return;
    
    const colors = ColorUtils.getElementColors(target);
    highlightElement(target, 'rgba(0, 100, 255, 0.2)');
    
    let tooltipText = '';
    if (colors.background) {
      tooltipText += `BG: ${colors.background.hex}\n`;
    }
    if (colors.text) {
      tooltipText += `Text: ${colors.text.hex}`;
    }
    
    showTooltip(target, tooltipText || 'No color detected');
  }
  
  async function onColorClick(e) {
    if (!isColorPickerMode) return;
    
    e.preventDefault();
    e.stopPropagation();
    
    const target = e.target;
    if (target.closest('.element-blocker-overlay')) return;
    
    let color;
    
    // Check if clicking on image
    if (target.tagName === 'IMG') {
      color = ColorUtils.getPixelColor(target, e.clientX, e.clientY);
    } else {
      const colors = ColorUtils.getElementColors(target);
      color = colors.background || colors.text;
    }
    
    if (color) {
      // Copy to clipboard
      await navigator.clipboard.writeText(color.hex);
      
      // Save to history
      await storage.saveColor({
        hex: color.hex,
        rgb: color.rgb,
        hsl: color.hsl,
        pickedAt: new Date().toISOString()
      });
      
      showNotification(`Copied: ${color.hex}`);
    }
    
    unhighlightElement();
  }
  
  // ============================================
  // UI HELPERS
  // ============================================
  
  function createOverlay(mode) {
    removeOverlay();
    
    overlay = document.createElement('div');
    overlay.className = 'element-blocker-overlay';
    overlay.innerHTML = `
      <div class="element-blocker-toolbar">
        <span class="element-blocker-mode">
          ${mode === 'blocker' ? '🚫 Element Blocker' : '🎨 Color Picker'} Mode
        </span>
        <span class="element-blocker-hint">
          Click to ${mode === 'blocker' ? 'block' : 'pick'} | ESC to cancel
        </span>
        <button class="element-blocker-close">✕</button>
      </div>
    `;
    
    overlay.querySelector('.element-blocker-close').onclick = () => {
      if (mode === 'blocker') stopBlockerMode();
      else stopColorPickerMode();
    };
    
    document.body.appendChild(overlay);
  }
  
  function removeOverlay() {
    if (overlay) {
      overlay.remove();
      overlay = null;
    }
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
  }
  
  function highlightElement(element, color) {
    unhighlightElement();
    
    highlightedElement = element;
    element.dataset.originalOutline = element.style.outline;
    element.style.outline = `2px solid ${color}`;
    element.style.outlineOffset = '-2px';
  }
  
  function unhighlightElement() {
    if (highlightedElement) {
      highlightedElement.style.outline = highlightedElement.dataset.originalOutline || '';
      delete highlightedElement.dataset.originalOutline;
      highlightedElement = null;
    }
    
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
  }
  
  function showTooltip(element, text) {
    if (tooltip) tooltip.remove();
    
    tooltip = document.createElement('div');
    tooltip.className = 'element-blocker-tooltip';
    tooltip.textContent = text;
    
    const rect = element.getBoundingClientRect();
    tooltip.style.left = `${rect.left + window.scrollX}px`;
    tooltip.style.top = `${rect.top + window.scrollY - 30}px`;
    
    document.body.appendChild(tooltip);
  }
  
  function showNotification(text) {
    const notification = document.createElement('div');
    notification.className = 'element-blocker-notification';
    notification.textContent = text;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.remove(), 2000);
  }
  
  function onEscape(e) {
    if (e.key === 'Escape') {
      if (isBlockerMode) stopBlockerMode();
      if (isColorPickerMode) stopColorPickerMode();
    }
  }
  
})();
```

### content/styles.css

```css
/* Element Blocker Extension Styles */

.element-blocker-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2147483647;
  pointer-events: none;
}

.element-blocker-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  pointer-events: auto;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.element-blocker-mode {
  font-weight: 600;
}

.element-blocker-hint {
  opacity: 0.8;
  font-size: 12px;
}

.element-blocker-close {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.element-blocker-close:hover {
  background: rgba(255, 255, 255, 0.3);
}

.element-blocker-tooltip {
  position: absolute;
  background: #1a1a2e;
  color: white;
  padding: 6px 12px;
  border-radius: 6px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 12px;
  white-space: pre-line;
  z-index: 2147483646;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}

.element-blocker-notification {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #10b981;
  color: white;
  padding: 12px 24px;
  border-radius: 8px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 14px;
  font-weight: 500;
  z-index: 2147483647;
  animation: slideIn 0.3s ease, fadeOut 0.3s ease 1.7s;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes fadeOut {
  from {
    opacity: 1;
  }
  to {
    opacity: 0;
  }
}
```

### popup/popup.html

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div class="popup-container">
    <header class="popup-header">
      <h1>🛡️ Element Blocker</h1>
      <span class="site-badge" id="current-site"></span>
    </header>
    
    <div class="button-group">
      <button id="block-mode-btn" class="primary-btn">
        🚫 Block Elements
      </button>
      <button id="color-mode-btn" class="primary-btn">
        🎨 Pick Colors
      </button>
    </div>
    
    <section class="section">
      <h2>Blocked on this site</h2>
      <div id="blocked-list" class="blocked-list">
        <p class="empty-state">No elements blocked yet</p>
      </div>
    </section>
    
    <section class="section">
      <h2>Recent Colors</h2>
      <div id="color-history" class="color-grid">
        <p class="empty-state">No colors picked yet</p>
      </div>
    </section>
    
    <footer class="popup-footer">
      <a href="#" id="options-link">⚙️ Settings</a>
      <span class="version">v1.0.0</span>
    </footer>
  </div>
  
  <script src="popup.js"></script>
</body>
</html>
```

### popup/popup.css

```css
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  width: 320px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f7;
}

.popup-container {
  padding: 16px;
}

.popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.popup-header h1 {
  font-size: 16px;
  font-weight: 600;
  color: #1a1a2e;
}

.site-badge {
  background: #e8e8ed;
  color: #666;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.button-group {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 16px;
}

.primary-btn {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.primary-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.primary-btn:active {
  transform: translateY(0);
}

.section {
  margin-bottom: 16px;
}

.section h2 {
  font-size: 12px;
  font-weight: 600;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.blocked-list {
  background: white;
  border-radius: 8px;
  max-height: 150px;
  overflow-y: auto;
}

.blocked-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.blocked-item:last-child {
  border-bottom: none;
}

.blocked-item-text {
  font-size: 13px;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.blocked-item-restore {
  background: none;
  border: none;
  color: #667eea;
  cursor: pointer;
  font-size: 12px;
  padding: 4px 8px;
}

.blocked-item-restore:hover {
  text-decoration: underline;
}

.color-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 6px;
  background: white;
  padding: 10px;
  border-radius: 8px;
}

.color-swatch {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  cursor: pointer;
  border: 2px solid transparent;
  transition: border-color 0.2s, transform 0.2s;
}

.color-swatch:hover {
  border-color: #667eea;
  transform: scale(1.1);
}

.empty-state {
  color: #999;
  font-size: 12px;
  text-align: center;
  padding: 20px;
}

.popup-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 12px;
  border-top: 1px solid #e8e8ed;
}

.popup-footer a {
  color: #667eea;
  text-decoration: none;
  font-size: 12px;
}

.popup-footer a:hover {
  text-decoration: underline;
}

.version {
  color: #999;
  font-size: 11px;
}
```

### popup/popup.js

```javascript
/**
 * Popup Script
 * Handles popup UI and communication with content script
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = new URL(tab.url);
  const hostname = url.hostname;
  
  // Display current site
  document.getElementById('current-site').textContent = hostname;
  
  // Load blocked elements
  loadBlockedElements(hostname);
  
  // Load color history
  loadColorHistory();
  
  // Button handlers
  document.getElementById('block-mode-btn').onclick = () => {
    chrome.tabs.sendMessage(tab.id, { action: 'startBlockerMode' });
    window.close();
  };
  
  document.getElementById('color-mode-btn').onclick = () => {
    chrome.tabs.sendMessage(tab.id, { action: 'startColorPickerMode' });
    window.close();
  };
  
  document.getElementById('options-link').onclick = (e) => {
    e.preventDefault();
    chrome.runtime.openOptionsPage();
  };
});

async function loadBlockedElements(hostname) {
  const response = await chrome.runtime.sendMessage({
    action: 'getBlockedElements',
    hostname
  });
  
  const container = document.getElementById('blocked-list');
  
  if (!response || response.length === 0) {
    container.innerHTML = '<p class="empty-state">No elements blocked yet</p>';
    return;
  }
  
  container.innerHTML = response.map(item => `
    <div class="blocked-item">
      <span class="blocked-item-text" title="${item.selector}">
        ${item.description || item.selector}
      </span>
      <button class="blocked-item-restore" data-selector="${encodeURIComponent(item.selector)}">
        Restore
      </button>
    </div>
  `).join('');
  
  // Add restore handlers
  container.querySelectorAll('.blocked-item-restore').forEach(btn => {
    btn.onclick = async () => {
      const selector = decodeURIComponent(btn.dataset.selector);
      
      // Send message to content script
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      chrome.tabs.sendMessage(tab.id, { action: 'restoreElement', selector });
      
      // Refresh list
      loadBlockedElements(hostname);
    };
  });
}

async function loadColorHistory() {
  const history = await chrome.runtime.sendMessage({
    action: 'getColorHistory'
  });
  
  const container = document.getElementById('color-history');
  
  if (!history || history.length === 0) {
    container.innerHTML = '<p class="empty-state">No colors picked yet</p>';
    return;
  }
  
  container.innerHTML = history.slice(0, 12).map(color => `
    <div 
      class="color-swatch" 
      style="background-color: ${color.hex};"
      data-hex="${color.hex}"
      title="${color.hex}"
    ></div>
  `).join('');
  
  // Add click handlers
  container.querySelectorAll('.color-swatch').forEach(swatch => {
    swatch.onclick = async () => {
      await navigator.clipboard.writeText(swatch.dataset.hex);
      
      // Visual feedback
      swatch.style.transform = 'scale(0.9)';
      setTimeout(() => {
        swatch.style.transform = '';
      }, 100);
    };
  });
}
```

---

## Installation

### Development Install

1. Clone/download the extension folder
2. Open Chrome and navigate to `chrome://extensions/`
3. Enable "Developer mode" (top right toggle)
4. Click "Load unpacked"
5. Select the `element-blocker-extension` folder

### Building for Production

```bash
# Install web-ext (optional, for packaging)
npm install -g web-ext

# Package extension
cd element-blocker-extension
web-ext build
```

---

## Usage

### Blocking Elements

1. Click extension icon → "Block Elements"
2. Or press `Alt+Shift+B`
3. Hover over elements to highlight them
4. Click to block (element immediately hides)
5. Press `ESC` to exit blocking mode

### Picking Colors

1. Click extension icon → "Pick Colors"
2. Or press `Alt+Shift+C`
3. Hover over elements to see colors
4. Click to copy color to clipboard
5. Press `ESC` to exit color mode

### Managing Blocked Elements

1. Click extension icon
2. See list of blocked elements for current site
3. Click "Restore" to unblock any element

---

## Site Presets (Future Enhancement)

Add preset blocking rules for common sites:

```javascript
// presets.js
const PRESETS = {
  'facebook.com': [
    '[data-pagelet="RightRail"]',           // Right sidebar
    '[data-pagelet="Stories"]',             // Stories
    '[aria-label="Suggested for you"]',     // Suggested posts
  ],
  'instagram.com': [
    '[aria-label="Suggested posts"]',
    '[aria-label="Shop"]',
  ],
  'youtube.com': [
    'ytd-rich-shelf-renderer',              // Shorts shelf
    '#secondary',                           // Sidebar recommendations
  ]
};
```

---

## Storage Schema

```javascript
{
  "sites": {
    "facebook.com": {
      "blockedElements": [
        {
          "selector": "[data-pagelet='RightRail']",
          "description": "Right sidebar",
          "createdAt": "2024-01-15T10:30:00Z",
          "enabled": true
        }
      ],
      "settings": {
        "autoApplyPresets": true
      }
    }
  },
  "colorHistory": [
    {
      "hex": "#667EEA",
      "rgb": "rgb(102, 126, 234)",
      "hsl": "hsl(228°, 74%, 66%)",
      "pickedAt": "2024-01-15T10:35:00Z"
    }
  ],
  "settings": {
    "theme": "auto",
    "defaultCopyFormat": "hex"
  }
}
```