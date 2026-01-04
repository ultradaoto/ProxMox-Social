/**
 * Content Script - Focus Mode & HUD
 * Implements Safe Zones, Blur Overlay, Spotlight, and Interactive Guides
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

    // HUD State
    let activeGuide = null;
    let currentStepIndex = 0;
    let hudRunner = null;

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

    // Auto-restore state
    storage.getActiveMode().then(savedMode => {
        if (savedMode && savedMode !== 'NONE') {
            setMode(savedMode);
        }
    });

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
            case 'startGuide':
                startGuide(request.guide);
                break;
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
        if (e.key === 'Escape') {
            if (mode !== 'NONE') setMode('NONE');
            if (hudRunner) stopGuide();
        }
    }, true);

    /* =============================================================================
       HUD Runner Logic
       ============================================================================= */

    class HudRunner {
        constructor(guide, onComplete) {
            this.guide = guide;
            this.stepIndex = 0;
            this.onComplete = onComplete;
            this.overlay = null;
            this.tooltip = null;
            this.highlight = null;
            this.cleanupStepListener = null;
        }

        start() {
            this.renderBaseUI();
            this.showStep(0);
        }

        renderBaseUI() {
            // Container for HUD elements
            if (!container) setupContainer();

            this.overlay = document.createElement('div');
            this.overlay.className = 'hud-overlay'; // Dim background
            container.appendChild(this.overlay);

            this.highlight = document.createElement('div');
            this.highlight.className = 'hud-highlight'; // Ring/Spotlight
            container.appendChild(this.highlight);

            this.tooltip = document.createElement('div');
            this.tooltip.className = 'hud-tooltip';
            container.appendChild(this.tooltip);
        }

        async showStep(index) {
            if (this.cleanupStepListener) this.cleanupStepListener();
            this.stepIndex = index;

            if (index >= this.guide.steps.length) {
                this.finish();
                return;
            }

            const step = this.guide.steps[index];
            const target = document.querySelector(step.targetSelector);

            if (!target) {
                console.warn('[HUD] Target not found:', step.targetSelector);
                // Auto-skip or show error? For now auto-skip after delay
                setTimeout(() => this.showStep(index + 1), 1000);
                return;
            }

            // Scroll to view
            target.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Update UI
            this.positionHighlight(target);
            this.updateTooltip(target, step, index);

            // Listen for Action
            if (step.action === 'click') {
                const handler = (e) => {
                    // Allow the click!
                    // Verify it's the target
                    if (e.target.closest(step.targetSelector)) {
                        // Good!
                        setTimeout(() => this.showStep(index + 1), 200);
                    }
                };
                document.addEventListener('click', handler, true); // Capture to detect before bubbling?
                this.cleanupStepListener = () => document.removeEventListener('click', handler, true);
            } else if (step.action === 'input') {
                const handler = (e) => {
                    if (e.target.matches(step.targetSelector)) {
                        // Advance on blur or delayed input?
                        // Let's allow typing, advance on 'change' or 'blur'
                    }
                };
                target.addEventListener('change', () => this.showStep(index + 1));
                // Fallback: Next button in tooltip
            }
        }

        positionHighlight(target) {
            const rect = target.getBoundingClientRect();
            // We need fixed coordinates
            this.highlight.style.left = (rect.left - 5) + 'px';
            this.highlight.style.top = (rect.top - 5) + 'px';
            this.highlight.style.width = (rect.width + 10) + 'px';
            this.highlight.style.height = (rect.height + 10) + 'px';

            // Ensure overlay has hole? Or just highlight on top
            // If we want "Dim everything else", we need masking like Focus Mode.
            // For now, let's just use a high-z-index ring.
        }

        updateTooltip(target, step, index) {
            const rect = target.getBoundingClientRect();

            this.tooltip.innerHTML = `
                <div class="hud-step-count">Step ${index + 1}/${this.guide.steps.length}</div>
                <div class="hud-step-text">${step.text}</div>
                <div class="hud-step-controls">
                    <button class="hud-btn-skip">Skip</button>
                    ${step.action !== 'click' ? '<button class="hud-btn-next">Next</button>' : ''}
                </div>
            `;

            // Position (Simple logic: Bottom if room, else Top)
            let top = rect.bottom + 15;
            let left = rect.left;

            if (top + 150 > window.innerHeight) {
                top = rect.top - 150; // Go above
            }

            this.tooltip.style.top = top + 'px';
            this.tooltip.style.left = left + 'px';

            // Handlers
            this.tooltip.querySelector('.hud-btn-skip').onclick = () => this.finish();
            const nextBtn = this.tooltip.querySelector('.hud-btn-next');
            if (nextBtn) nextBtn.onclick = () => this.showStep(index + 1);
        }

        finish() {
            if (this.cleanupStepListener) this.cleanupStepListener();
            this.overlay.remove();
            this.highlight.remove();
            this.tooltip.remove();
            if (this.onComplete) this.onComplete();
        }
    }

    function startGuide(guide) {
        if (hudRunner) hudRunner.finish();
        hudRunner = new HudRunner(guide, () => {
            hudRunner = null;
            showNotification('Guide Completed! 🎉');
        });
        hudRunner.start();
    }

    function stopGuide() {
        if (hudRunner) hudRunner.finish();
        hudRunner = null;
    }

    /* =============================================================================
       Existing Logic (Mode Switching, etc)
       ============================================================================= */

    /**
     * Mode Switching
     */
    async function setMode(newMode) {
        cleanupUI();
        mode = newMode;

        // Save state
        await storage.setActiveMode(mode);

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
        // Idempotent check
        if (container) return;

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

        // Keep container for HUD if active? No, HUD creates its own elements inside container.
        // If we switch modes, we generally want to clear everything.
        if (hudRunner) stopGuide();

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

/* =============================================================================
   OSP CONTENT SCRIPT
   ============================================================================= */
(function() {
    console.log('[OSP] Content Script Initialized');

    let highlightedElement = null;
    let highlightOverlay = null;

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'OSP_MESSAGE') {
            const { ospType, payload } = message;
            handleOSPMessage(ospType, payload);
        }
    });

    function handleOSPMessage(type, payload) {
        console.log('[OSP] Msg:', type, payload);
        switch (type) {
            case 'highlight_element':
                highlightElement(payload.selector, payload.label);
                break;
            case 'clear_highlights':
                clearHighlights();
                break;
        }
    }

    function highlightElement(selector, label) {
        clearHighlights();
        let element = document.querySelector(selector);
        if (!element) {
            console.warn('[OSP] Element not found:', selector);
            return;
        }
        
        highlightedElement = element;
        highlightOverlay = document.createElement('div');
        highlightOverlay.className = 'osp-highlight-overlay';
        
        let extraClass = '';
        if (label.toLowerCase().includes('paste')) extraClass = 'paste';
        if (label.toLowerCase().includes('post') || label.toLowerCase().includes('submit')) extraClass = 'submit';
        if (extraClass) highlightOverlay.classList.add(extraClass);

        highlightOverlay.innerHTML = \<div class='osp-highlight-label'>\</div><div class='osp-highlight-arrow'>?</div>\;
        
        document.body.appendChild(highlightOverlay);
        positionOverlay(element);
        
        window.addEventListener('scroll', updateOverlayPosition, true);
        window.addEventListener('resize', updateOverlayPosition);
        
        element.classList.add('osp-highlighted-element');
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        element.addEventListener('click', onHighlightedElementClick);
        element.addEventListener('focus', onHighlightedElementFocus);
    }

    function updateOverlayPosition() {
        if (highlightedElement && highlightOverlay) positionOverlay(highlightedElement);
    }

    function positionOverlay(element) {
        const rect = element.getBoundingClientRect();
        highlightOverlay.style.position = 'fixed';
        highlightOverlay.style.left = \\px\;
        highlightOverlay.style.top = \\px\;
        highlightOverlay.style.transform = 'translateX(-50%)';
    }

    function clearHighlights() {
        if (highlightOverlay) {
            highlightOverlay.remove();
            highlightOverlay = null;
        }
        window.removeEventListener('scroll', updateOverlayPosition, true);
        window.removeEventListener('resize', updateOverlayPosition);
        if (highlightedElement) {
            highlightedElement.classList.remove('osp-highlighted-element');
            highlightedElement.removeEventListener('click', onHighlightedElementClick);
            highlightedElement.removeEventListener('focus', onHighlightedElementFocus);
            highlightedElement = null;
        }
        document.querySelectorAll('.osp-highlighted-element').forEach(el => el.classList.remove('osp-highlighted-element'));
        document.querySelectorAll('.osp-highlight-overlay').forEach(el => el.remove());
    }

    function onHighlightedElementClick(event) {
        sendToBackground('element_clicked', {
            selector: getSelector(event.target),
            element_type: event.target.tagName.toLowerCase(),
            element_id: event.target.id
        });
    }

    function onHighlightedElementFocus(event) {
        sendToBackground('element_focused', {
            selector: getSelector(event.target),
            element_type: event.target.tagName.toLowerCase()
        });
        
        const placeholder = event.target.getAttribute('data-placeholder') || 
                            event.target.getAttribute('placeholder') || '';
        
        if (placeholder.toLowerCase().includes('title')) {
            sendToBackground('request_copy', { field: 'title' });
        } else if (placeholder.toLowerCase().includes('write') || 
                   placeholder.toLowerCase().includes('body')) {
            sendToBackground('request_copy', { field: 'body' });
        }
    }

    document.addEventListener('paste', (event) => {
        const target = event.target;
        if (target.matches('input, textarea, [contenteditable]')) {
             setTimeout(() => {
                const content = target.value || target.textContent || '';
                sendToBackground('paste_detected', {
                    selector: getSelector(target),
                    content_length: content.length,
                    element_type: target.tagName.toLowerCase()
                });
            }, 100);
        }
    });

    function getSelector(element) {
        if (element.id) return '#' + element.id;
        if (element.getAttribute('data-placeholder')) return \[data-placeholder='\']\;
        if (element.className && typeof element.className === 'string') {
            const classes = element.className.split(' ').filter(c => c).slice(0, 2);
            if (classes.length) return '.' + classes.join('.');
        }
        return element.tagName.toLowerCase();
    }

    function sendToBackground(type, payload) {
        try {
            chrome.runtime.sendMessage({
                action: 'OSP_SEND',
                type: type,
                payload: payload
            });
        } catch (e) {
            console.log('Stats connection lost:', e);
        }
    }
})();

