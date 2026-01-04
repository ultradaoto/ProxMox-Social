/**
 * Content Script - Focus Mode
 * Implements Safe Zones, Blur Overlay, and Spotlight logic
 */

(function () {
    'use strict';

    // State
    let mode = 'NONE'; // 'FOCUS', 'EDIT', 'COLOR', 'NONE'
    let safeElements = [];
    let spotlightX = -1000;
    let spotlightY = -1000;
    let animationFrame = null;
    const SPOTLIGHT_RADIUS = 150;

    // DOM Elements
    let container = null;
    let statusLine = null; // 3px top bar
    let controlsPill = null; // Floating controls
    let backdrop = null; // Blur overlay for Focus Mode
    let editOverlay = null; // Red tint overlay for Edit Mode
    let hoverHighlight = null;
    let debugTooltip = null; // Tooltip to show element info
    let safeZoneHighlights = [];

    // Initialize
    const storage = new StorageManager();

    // Listen for messages
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        switch (request.action) {
            case 'toggleFocusMode':
                mode === 'FOCUS' ? setMode('NONE') : setMode('FOCUS');
                break;
            case 'toggleEditMode':
                mode === 'EDIT' ? setMode('NONE') : setMode('EDIT');
                break;
            case 'startEditMode':
                setMode('EDIT');
                break;
            case 'getMode':
                sendResponse({ mode: mode });
                return true;
        }

        sendResponse({ success: true, mode: mode });
    });

    // Global Event Listeners (Capture Phase)
    document.addEventListener('mousemove', (e) => {
        spotlightX = e.clientX;
        spotlightY = e.clientY;

        if (mode === 'FOCUS') {
            updateMask();
        }
    }, true);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mode !== 'NONE') {
            setMode('NONE');
        }
    }, true);

    /**
     * Mode Switching
     */
    async function setMode(newMode) {
        cleanupUI();
        mode = newMode;
        if (mode === 'NONE') return;

        safeElements = await storage.getSafeSelectors();
        setupContainer();

        if (mode === 'FOCUS') {
            startFocusMode();
        } else if (mode === 'EDIT') {
            startEditMode();
        }
    }

    function setupContainer() {
        container = document.createElement('div');
        container.className = 'focus-overlay-container';

        // 1. Status Line (3px top bar) - Always VISIBLE on top frame
        if (window.top === window) {
            statusLine = document.createElement('div');
            statusLine.className = `focus-status-line ${mode === 'EDIT' ? 'edit-mode' : ''}`;
            container.appendChild(statusLine);

            // 2. Floating Controls (Unobtrusive)
            controlsPill = document.createElement('div');
            controlsPill.className = 'focus-controls-pill';
            controlsPill.innerHTML = `
        <span class="focus-pill-label">
          ${mode === 'FOCUS' ? '🎯 Focus' : '✏️ Edit'}
        </span>
        <button class="focus-pill-close" title="Exit (ESC)">✕</button>
      `;
            controlsPill.querySelector('.focus-pill-close').onclick = () => setMode('NONE');

            // Allow clicking controls even if blocking
            controlsPill.addEventListener('mousedown', e => e.stopPropagation());
            controlsPill.addEventListener('click', e => e.stopPropagation());

            container.appendChild(controlsPill);
        }

        document.body.appendChild(container);
    }

    function cleanupUI() {
        document.removeEventListener('click', onCaptureClick, true);
        document.removeEventListener('mousemove', onCaptureMove, true);
        document.removeEventListener('mousedown', checkInteractionAllowed, true);
        document.removeEventListener('mouseup', checkInteractionAllowed, true);
        document.removeEventListener('click', checkInteractionAllowed, true);

        if (container) container.remove();
        container = null;
        backdrop = null;
        editOverlay = null;
        hoverHighlight = null;
        debugTooltip = null;
        statusLine = null;
        controlsPill = null;
        safeZoneHighlights = [];
        if (animationFrame) cancelAnimationFrame(animationFrame);

        document.body.style.cursor = '';
    }

    // Interaction Logic for Focus Mode
    function checkInteractionAllowed(e) {
        if (mode !== 'FOCUS') {
            if (mode === 'EDIT') {
                // Block everything in Edit Mode except toolbar
                if (e.target.closest && e.target.closest('.focus-overlay-container')) return;
                e.preventDefault();
                e.stopPropagation();
            }
            return;
        }

        // FOCUS MODE:
        // Allow if:
        // 1. Target is user controls (toolbar)
        if (e.target.closest && e.target.closest('.focus-overlay-container')) return;

        // 2. Target is inside Spotlight
        const dx = e.clientX - spotlightX;
        const dy = e.clientY - spotlightY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist <= SPOTLIGHT_RADIUS) {
            // Allow! Center of spotlight is interactive.
            return;
        }

        // 3. Target is a Safe Zone (or inside one)
        // We can check if it matches any safe selector
        const isSafe = safeElements.some(item => {
            try {
                return e.target.matches(item.selector) || e.target.closest(item.selector);
            } catch { return false; }
        });

        if (isSafe) return; // Allow

        // Otherwise, Block
        e.preventDefault();
        e.stopPropagation();
    }

    /**
     * Focus Mode
     */
    function startFocusMode() {
        backdrop = document.createElement('div');
        backdrop.className = 'focus-backdrop';
        container.insertBefore(backdrop, container.firstChild); // Behind controls

        updateMaskLoop();
        window.addEventListener('scroll', updateMask, { passive: true });
        window.addEventListener('resize', updateMask, { passive: true });

        // NEW: Smart blocking
        document.addEventListener('click', checkInteractionAllowed, true);
        document.addEventListener('mousedown', checkInteractionAllowed, true);
        document.addEventListener('mouseup', checkInteractionAllowed, true);
    }

    function updateMaskLoop() {
        if (mode !== 'FOCUS') return;
        updateMask();
        animationFrame = requestAnimationFrame(updateMaskLoop);
    }

    function updateMask() {
        if (!backdrop) return;
        applyMasking(backdrop, true);
    }

    /**
     * Edit Mode
     */
    async function startEditMode() {
        document.body.style.cursor = 'crosshair';

        editOverlay = document.createElement('div');
        editOverlay.className = 'edit-mode-overlay-bg';
        // Insert behind controls/status
        if (statusLine) {
            container.insertBefore(editOverlay, statusLine.nextSibling);
        } else {
            container.insertBefore(editOverlay, container.firstChild);
        }

        if (window.top === window) {
            debugTooltip = document.createElement('div');
            debugTooltip.className = 'focus-debug-tooltip';
            container.appendChild(debugTooltip);
        }

        document.addEventListener('click', onCaptureClick, true);
        document.addEventListener('mousemove', onCaptureMove, true);
        // Block interaction completely in edit mode (handled by capture click)
        document.addEventListener('mousedown', checkInteractionAllowed, true);
        document.addEventListener('mouseup', checkInteractionAllowed, true);

        updateEditVisuals();

        window.addEventListener('scroll', updateEditVisuals, { passive: true });
        window.addEventListener('resize', updateEditVisuals, { passive: true });
    }

    function getBestElementAtCursor(x, y) {
        const prevDisplay = container.style.display;
        container.style.display = 'none';

        const elements = document.elementsFromPoint(x, y);

        container.style.display = prevDisplay;

        for (const el of elements) {
            if (el === document.documentElement || el === document.body) continue;
            const style = window.getComputedStyle(el);
            if (style.pointerEvents === 'none') continue;
            return el;
        }
        return document.body;
    }

    function onCaptureMove(e) {
        if (mode !== 'EDIT') return;

        const target = getBestElementAtCursor(e.clientX, e.clientY);
        updateDebugTooltip(e.clientX, e.clientY, target);

        if (!target || target === document.body || target === document.documentElement) {
            if (hoverHighlight) hoverHighlight.remove();
            hoverHighlight = null;
            return;
        }

        renderHoverHighlight(target);
    }

    function updateDebugTooltip(x, y, target) {
        if (!debugTooltip) return;

        // Offset slightly
        debugTooltip.style.left = (x + 20) + 'px';
        debugTooltip.style.top = (y + 20) + 'px';

        if (target) {
            let name = target.tagName.toLowerCase();
            if (target.id) name += '#' + target.id;
            if (target.className && typeof target.className === 'string') {
                const classes = target.className.replace(/\s+/g, '.');
                if (classes.length < 30) name += '.' + classes;
                else name += '.' + classes.substring(0, 30) + '...';
            }
            debugTooltip.textContent = name;
        }
    }

    async function onCaptureClick(e) {
        if (mode !== 'EDIT') return;
        if (e.target.closest && e.target.closest('.focus-overlay-container')) return;

        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();

        visualTapFeedback(e.clientX, e.clientY);

        const target = getBestElementAtCursor(e.clientX, e.clientY);
        if (!target) return;

        await toggleSafeZone(target);
    }

    function visualTapFeedback(x, y) {
        if (window.top !== window) return; // Only visuals on top

        const ripple = document.createElement('div');
        ripple.style.position = 'fixed';
        ripple.style.left = (x - 10) + 'px';
        ripple.style.top = (y - 10) + 'px';
        ripple.style.width = '20px';
        ripple.style.height = '20px';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'white';
        ripple.style.zIndex = '2147483647';
        ripple.style.pointerEvents = 'none';
        ripple.style.opacity = '0.8';
        ripple.style.transition = 'transform 0.3s, opacity 0.3s';

        container.appendChild(ripple);

        requestAnimationFrame(() => {
            ripple.style.transform = 'scale(2)';
            ripple.style.opacity = '0';
        });

        setTimeout(() => ripple.remove(), 300);
    }

    async function updateEditVisuals() {
        if (!editOverlay) return;
        applyMasking(editOverlay, false);
        await refreshSafeZoneHighlights();
    }

    function applyMasking(element, includeSpotlight) {
        const safeRects = [];
        safeElements.forEach(item => {
            try {
                const els = document.querySelectorAll(item.selector);
                els.forEach(el => {
                    if (el.offsetParent === null) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        safeRects.push(rect);
                    }
                });
            } catch (e) { }
        });

        const layers = [];
        const sizes = [];
        const positions = [];
        const repeats = [];

        if (includeSpotlight) {
            // Matches SPOTLIGHT_RADIUS var above
            const spotlightRadius = 150;
            layers.push(`radial-gradient(circle ${spotlightRadius}px at ${spotlightX}px ${spotlightY}px, black 100%, transparent 100%)`);
            sizes.push('100% 100%');
            positions.push('0 0');
            repeats.push('no-repeat');
        }

        safeRects.forEach(r => {
            layers.push(`linear-gradient(black, black)`);
            sizes.push(`${r.width}px ${r.height}px`);
            positions.push(`${r.left}px ${r.top}px`);
            repeats.push('no-repeat');
        });

        layers.push(`linear-gradient(black, black)`);
        sizes.push('100% 100%');
        positions.push('0 0');
        repeats.push('no-repeat');

        element.style.maskImage = layers.join(', ');
        element.style.webkitMaskImage = layers.join(', ');
        element.style.maskSize = sizes.join(', ');
        element.style.webkitMaskSize = sizes.join(', ');
        element.style.maskPosition = positions.join(', ');
        element.style.webkitMaskPosition = positions.join(', ');
        element.style.maskRepeat = repeats.join(', ');
        element.style.webkitMaskRepeat = repeats.join(', ');

        element.style.maskComposite = 'exclude';
        element.style.webkitMaskComposite = 'destination-out';
    }

    async function refreshSafeZoneHighlights() {
        safeZoneHighlights.forEach(el => el.remove());
        safeZoneHighlights = [];

        safeElements.forEach(item => {
            try {
                const els = document.querySelectorAll(item.selector);
                els.forEach(el => {
                    if (el.offsetParent === null) return;
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0) return;

                    const hl = document.createElement('div');
                    hl.className = 'safe-zone-highlight';
                    hl.style.left = `${rect.left}px`;
                    hl.style.top = `${rect.top}px`;
                    hl.style.width = `${rect.width}px`;
                    hl.style.height = `${rect.height}px`;

                    container.appendChild(hl);
                    safeZoneHighlights.push(hl);
                });
            } catch (e) { }
        });
    }

    function renderHoverHighlight(target) {
        if (hoverHighlight) {
            hoverHighlight.remove();
            hoverHighlight = null;
        }

        const isSafe = safeElements.some(item => {
            try { return target.matches(item.selector) || target.closest(item.selector); }
            catch { return false; }
        });

        const rect = target.getBoundingClientRect();
        if (rect.width === 0) return;

        hoverHighlight = document.createElement('div');
        hoverHighlight.className = isSafe ? 'safe-hover-highlight' : 'unsafe-hover-highlight';
        hoverHighlight.style.left = `${rect.left}px`;
        hoverHighlight.style.top = `${rect.top}px`;
        hoverHighlight.style.width = `${rect.width}px`;
        hoverHighlight.style.height = `${rect.height}px`;

        const label = document.createElement('div');
        label.className = isSafe ? 'safe-hover-label' : 'unsafe-hover-label';
        label.textContent = isSafe ? 'Click to Remove' : 'Click to Mark Safe';
        hoverHighlight.appendChild(label);

        container.appendChild(hoverHighlight);
    }

    async function toggleSafeZone(target) {
        const existingSafeParentIndex = safeElements.findIndex(item => {
            try { return target.closest(item.selector); } catch { return false; }
        });

        let message = '';
        let type = 'success';

        if (existingSafeParentIndex >= 0) {
            const parentSelector = safeElements[existingSafeParentIndex].selector;
            await storage.toggleSafeElement(parentSelector);
            message = 'Removed Safe Zone';
            type = 'removed';
        } else {
            const selector = SelectorGenerator.generate(target);
            const description = SelectorGenerator.getDescription(target);
            await storage.toggleSafeElement(selector, description);
            message = 'Marked Safe ✅';
        }

        showNotification(message, type);
        safeElements = await storage.getSafeSelectors();
        updateEditVisuals();
        renderHoverHighlight(target);
    }

    function showNotification(text, type = 'success') {
        if (window.top !== window) return;
        const n = document.createElement('div');
        n.className = `focus-notification notification-${type}`;
        n.textContent = text;
        document.body.appendChild(n);
        setTimeout(() => n.remove(), 2000);
    }

})();
