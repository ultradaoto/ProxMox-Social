/**
 * OSP Content Script
 * Highlights elements and reports interactions
 */
(function () {
    console.log('[OSP] Content Script Initialized');

    let highlightedElement = null;
    let highlightOverlay = null;

    let isRecording = false;

    // Notify background that content script is ready to receive messages
    // This is critical for timing - Python should wait for this before sending highlights
    setTimeout(() => {
        try {
            chrome.runtime.sendMessage({
                action: 'OSP_SEND',
                type: 'content_ready',
                payload: {
                    url: window.location.href,
                    timestamp: Date.now()
                }
            });
            console.log('[OSP] Sent content_ready signal');
        } catch (e) {
            console.log('[OSP] Could not send content_ready:', e);
        }
    }, 100); // Small delay to ensure everything is set up

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'OSP_MESSAGE') {
            const { ospType, payload } = message;
            handleOSPMessage(ospType, payload);
        }
    });

    // Toggle Recording Mode
    function toggleRecording(enabled) {
        if (isRecording === enabled) return;
        isRecording = enabled;
        console.log(`[OSP] Recording Mode: ${enabled ? 'ON' : 'OFF'}`);

        if (isRecording) {
            document.addEventListener('click', onGlobalClick, true);
            showRecordingIndicator();
        } else {
            document.removeEventListener('click', onGlobalClick, true);
            hideRecordingIndicator();
        }
    }

    // Visual indicator that recording is active
    function showRecordingIndicator() {
        let indicator = document.getElementById('osp-recording-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'osp-recording-indicator';
            indicator.innerHTML = '🔴 REC';
            indicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                background: rgba(239, 68, 68, 0.9);
                color: white;
                padding: 8px 12px;
                border-radius: 4px;
                font-family: system-ui, sans-serif;
                font-size: 12px;
                font-weight: bold;
                z-index: 999999;
                pointer-events: none;
                animation: osp-blink 1s infinite;
            `;
            // Add blink animation
            const style = document.createElement('style');
            style.textContent = `
                @keyframes osp-blink {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(indicator);
        }
        indicator.style.display = 'block';
    }

    function hideRecordingIndicator() {
        const indicator = document.getElementById('osp-recording-indicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
    }

    function onGlobalClick(event) {
        if (!isRecording) return;
        // Filter out programmatic clicks (e.g. from React/Scripts)
        if (!event.isTrusted) return;

        // Don't report clicks on our own overlay
        if (event.target.closest('.osp-highlight-overlay')) return;

        try {
            const selector = getSelector(event.target);
            console.log('[OSP] Click detected:', event.target.tagName, selector);
            sendToBackground('interaction_recorded', {
                type: 'click',
                selector: selector,
                element_type: event.target.tagName.toLowerCase(),
                x: event.clientX,
                y: event.clientY,
                timestamp: Date.now()
            });
        } catch (e) {
            console.error('[OSP] Failed to record click:', e);
        }
    }

    let lastHighlightTime = 0;
    let lastHighlightSelector = '';
    const SPAM_THRESHOLD_MS = 500;

    function handleOSPMessage(type, payload) {
        console.log('[OSP] Msg Received:', type, payload);
        switch (type) {
            case 'highlight_element':
                const now = Date.now();
                if (payload.selector === lastHighlightSelector && (now - lastHighlightTime < SPAM_THRESHOLD_MS)) {
                    console.log('[OSP] Ignoring duplicate highlight request');
                    return;
                }
                lastHighlightTime = now;
                lastHighlightSelector = payload.selector;
                highlightElement(payload.selector, payload.label);
                break;
            case 'clear_highlights':
                console.log('[OSP] Clear highlights requested by Python');
                clearHighlights('python_request');
                break;
            case 'start_recording':
                toggleRecording(true);
                break;
            case 'stop_recording':
                toggleRecording(false);
                break;
            case 'show_instruction':
                showInstruction(payload.text, payload.icon || '💡');
                break;
            case 'hide_instruction':
                hideInstruction();
                break;
            case 'suggest_field':
                suggestField(payload.field);
                break;
        }
    }

    async function highlightElement(selector, label) {
        console.log('[OSP] Attempting to highlight:', selector, 'Label:', label);
        clearHighlights('new_highlight');

        // Try to find the element with retries (up to 5s)
        let element = null;
        try {
            element = await waitForElement(selector, 5000);
        } catch (e) {
            // Timed out - try alternatives
        }

        // If not found, try alternative selectors based on the label
        if (!element) {
            console.log('[OSP] Primary selector failed, trying alternatives...');
            element = await tryAlternativeSelectors(selector, label);
        }

        if (!element) {
            console.warn('[OSP] Element not found (after all attempts):', selector);
            sendToBackground('element_not_found', { selector: selector });
            return;
        }

        console.log('[OSP] Element found, creating highlight overlay');
        highlightedElement = element;
        highlightOverlay = document.createElement('div');
        highlightOverlay.className = 'osp-highlight-overlay';

        let extraClass = '';
        if (label.toLowerCase().includes('paste')) extraClass = 'paste';
        if (label.toLowerCase().includes('post') || label.toLowerCase().includes('submit')) extraClass = 'submit';
        if (extraClass) highlightOverlay.classList.add(extraClass);

        highlightOverlay.innerHTML = `
            <div class="osp-highlight-label">${label}</div>
        `;

        document.body.appendChild(highlightOverlay);
        positionOverlay(element);

        window.addEventListener('scroll', onScroll, true);
        window.addEventListener('resize', onResize);

        element.classList.add('osp-highlighted-element');
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        element.addEventListener('click', onHighlightedElementClick);
        element.addEventListener('focus', onHighlightedElementFocus);

        // Notify Python that highlight is now visible
        console.log('[OSP] Highlight displayed successfully for:', selector);
        sendToBackground('highlight_displayed', {
            selector: selector,
            label: label,
            timestamp: Date.now()
        });
    }

    // Try alternative selectors when primary fails
    async function tryAlternativeSelectors(originalSelector, label) {
        const labelLower = label.toLowerCase();
        let alternatives = [];

        // Build alternatives based on what we're looking for
        if (labelLower.includes('title')) {
            alternatives = [
                "[placeholder='Title']",
                "input[placeholder*='title' i]",
                "input[placeholder*='Title']",
                "[data-placeholder='Title']",
                ".title-input",
                "input[name='title']",
                "[contenteditable='true']:first-of-type",
                "input[type='text']:first-of-type"
            ];
        } else if (labelLower.includes('body') || labelLower.includes('write') || labelLower.includes('content')) {
            alternatives = [
                "[placeholder*='Write' i]",
                "[data-placeholder*='Write' i]",
                "p[data-placeholder*='Write' i]",
                "p[data-placeholder*='something']",
                "textarea",
                ".body-input",
                "[contenteditable='true']",
                "div[role='textbox']",
                ".is-empty",
                "p[contenteditable='true']"
            ];
        } else if (labelLower.includes('post') || labelLower.includes('submit')) {
            alternatives = [
                "button[type='submit']",
                ".post-button",
                "button:contains('Post')",
                "[aria-label='Post']",
                "button.primary"
            ];
        }

        // Also try splitting comma-separated selectors and testing individually
        if (originalSelector.includes(',')) {
            const parts = originalSelector.split(',').map(s => s.trim());
            alternatives = [...parts, ...alternatives];
        }

        // Try each alternative
        for (const alt of alternatives) {
            try {
                const el = document.querySelector(alt);
                if (el) {
                    console.log('[OSP] Found element with alternative selector:', alt);
                    return el;
                }
            } catch (e) {
                // Invalid selector, skip
            }
        }

        // Last resort: wait a bit and try alternatives again (page might still be loading)
        await new Promise(resolve => setTimeout(resolve, 1000));
        for (const alt of alternatives) {
            try {
                const el = document.querySelector(alt);
                if (el) {
                    console.log('[OSP] Found element with alternative selector (after delay):', alt);
                    return el;
                }
            } catch (e) {
                // Invalid selector, skip
            }
        }

        return null;
    }

    function waitForElement(selector, timeout = 5000) {
        return new Promise((resolve, reject) => {
            if (document.querySelector(selector)) {
                return resolve(document.querySelector(selector));
            }

            const observer = new MutationObserver(mutations => {
                if (document.querySelector(selector)) {
                    observer.disconnect();
                    resolve(document.querySelector(selector));
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });

            setTimeout(() => {
                observer.disconnect();
                reject(new Error("Timeout"));
            }, timeout);
        });
    }

    let isTicking = false;
    function onScroll() {
        if (!isTicking) {
            window.requestAnimationFrame(() => {
                updateOverlayPosition();
                isTicking = false;
            });
            isTicking = true;
        }
    }

    function onResize() {
        onScroll();
    }

    function updateOverlayPosition() {
        if (highlightedElement && highlightOverlay) positionOverlay(highlightedElement);
    }

    function positionOverlay(element) {
        const rect = element.getBoundingClientRect();
        if (!highlightOverlay) return;

        // Position at the top-right corner of the element
        highlightOverlay.style.left = `${rect.right + window.scrollX}px`;
        highlightOverlay.style.top = `${rect.top + window.scrollY}px`;
        highlightOverlay.style.display = 'block';
    }

    function clearHighlights(reason = 'unknown') {
        const hadHighlight = highlightOverlay !== null || highlightedElement !== null;
        let selector = 'none';

        if (highlightOverlay) {
            highlightOverlay.remove();
            highlightOverlay = null;
        }

        if (highlightedElement) {
            try {
                selector = getSelector(highlightedElement);
            } catch (e) { }
            highlightedElement.classList.remove('osp-highlighted-element');
            highlightedElement.removeEventListener('click', onHighlightedElementClick);
            highlightedElement.removeEventListener('focus', onHighlightedElementFocus);
            highlightedElement = null;
        }

        const label = document.getElementById('osp-highlight-label');
        if (label) label.remove();

        // Log and notify when a highlight was actually removed
        if (hadHighlight) {
            console.log('[OSP] Highlight CLEARED - Reason:', reason, '- Selector was:', selector);
            sendToBackground('highlight_cleared', {
                reason: reason,
                selector: selector,
                timestamp: Date.now()
            });
        }
    }

    // Instruction Banner Logic
    function showInstruction(text, icon = '💡') {
        console.log('[OSP] Showing instruction:', text);
        let banner = document.getElementById('osp-instruction-banner');
        if (!banner) {
            banner = document.createElement('div');
            banner.id = 'osp-instruction-banner';
            banner.className = 'osp-instruction-banner';
            banner.innerHTML = `
                <span class="osp-instruction-icon">${icon}</span>
                <div class="osp-instruction-text"></div>
            `;
            document.body.appendChild(banner);
        }

        const textEl = banner.querySelector('.osp-instruction-text');
        textEl.textContent = text;
        banner.querySelector('.osp-instruction-icon').textContent = icon;

        // Animate in
        banner.classList.add('visible');
    }

    function hideInstruction() {
        console.log('[OSP] Hiding instruction banner');
        const banner = document.getElementById('osp-instruction-banner');
        if (banner) {
            banner.classList.remove('visible');
        }
    }

    async function suggestField(type) {
        console.log('[OSP] Auto-suggesting field highlight for:', type);
        let label = "ACTION NEEDED";
        if (type === 'title') label = "PASTE TITLE HERE";
        if (type === 'body') label = "PASTE BODY HERE";
        if (type === 'post') label = "CLICK TO POST";

        // Use our search engine to find the element
        const element = await tryAlternativeSelectors('', type);
        if (element) {
            const selector = getSelector(element);
            highlightElement(selector, label);
            showInstruction(`Please ${label.toLowerCase()}`, '👆');
        }
    }

    function onHighlightedElementClick(event) {
        const selector = getSelector(event.target);
        console.log('[OSP] Highlighted element CLICKED:', event.target.tagName, selector);
        clearHighlights('element_clicked'); // Auto-clear overlay on interaction

        // Send highlight_clicked - this is what Python uses to advance playback
        sendToBackground('highlight_clicked', {
            selector: selector,
            element_type: event.target.tagName.toLowerCase(),
            element_id: event.target.id,
            timestamp: Date.now()
        });

        // Also send element_clicked for backwards compatibility
        sendToBackground('element_clicked', {
            selector: selector,
            element_type: event.target.tagName.toLowerCase(),
            element_id: event.target.id,
            timestamp: Date.now()
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
        // 1. ID
        if (element.id) return '#' + CSS.escape(element.id);

        // 2. Important Attributes
        const attributes = ['name', 'placeholder', 'aria-label', 'data-testid', 'data-id', 'role', 'data-placeholder'];
        for (const attr of attributes) {
            if (element.hasAttribute(attr)) {
                const val = element.getAttribute(attr);
                if (val && val.length < 50) {
                    // Use double quotes and minimal escaping for attribute values to avoid over-escaping spaces
                    const safeVal = val.replace(/'/g, "\\'");
                    const selector = `[${attr}="${safeVal}"]`;
                    if (document.querySelectorAll(selector).length === 1) return selector;
                    const tagSelector = `${element.tagName.toLowerCase()}${selector}`;
                    if (document.querySelectorAll(tagSelector).length === 1) return tagSelector;
                }
            }
        }

        // 3. Classes (careful of generic Tailwind/Utility/State classes)
        const IGNORED_CLASSES = ['is-empty', 'is-focused', 'is-editor-empty', 'ProseMirror', 'osp-highlighted-element', 'osp-highlight-overlay'];
        if (element.className && typeof element.className === 'string') {
            const classes = element.className.trim().split(/\s+/)
                .filter(cls => {
                    if (!cls) return false;
                    // Ignore transient state classes
                    if (IGNORED_CLASSES.some(ignored => cls.includes(ignored))) return false;
                    // Ignore hover states
                    if (cls.includes('hover:')) return false;
                    // Ignore styled-component hashes (common patterns: styled__, -sc-)
                    if (cls.startsWith('styled__') || cls.includes('-sc-')) return false;
                    return true;
                });

            // Try single classes first (not generic ones)
            for (const cls of classes) {
                // Skip generic one-letter or two-letter classes (common in some frameworks)
                if (cls.length <= 2) continue;

                const selector = '.' + CSS.escape(cls);
                if (document.querySelectorAll(selector).length === 1) return selector;

                // Try tag + class
                const tagSelector = element.tagName.toLowerCase() + selector;
                if (document.querySelectorAll(tagSelector).length === 1) return tagSelector;
            }

            // Try combinations of 2 classes
            if (classes.length >= 2) {
                const selector = '.' + CSS.escape(classes[0]) + '.' + CSS.escape(classes[1]);
                if (document.querySelectorAll(selector).length === 1) return selector;
            }
        }

        // 4. CSS Path (Recursive Parent)
        try {
            if (!element || !element.parentNode) return element ? element.tagName.toLowerCase() : '';
            return getCssPath(element);
        } catch (e) {
            console.warn('[OSP] getSelector crashed:', e);
            return element ? element.tagName.toLowerCase() : '';
        }
    }

    function getCssPath(el) {
        if (!el || !(el instanceof Element)) return '';
        const path = [];
        const IGNORED_CLASSES = ['is-empty', 'is-focused', 'is-editor-empty', 'ProseMirror', 'osp-highlighted-element', 'osp-highlight-overlay'];

        while (el && el.nodeType === Node.ELEMENT_NODE) {
            let selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector += '#' + CSS.escape(el.id);
                path.unshift(selector);
                break;
            } else {
                // Add stable classes to the selector segment
                if (el.className && typeof el.className === 'string') {
                    const classes = el.className.trim().split(/\s+/)
                        .filter(cls => {
                            if (!cls || cls.length <= 2) return false;
                            if (IGNORED_CLASSES.some(ignored => cls.includes(ignored))) return false;
                            if (cls.includes('hover:')) return false;
                            if (cls.startsWith('styled__') || cls.includes('-sc-')) return false;
                            return true;
                        });
                    if (classes.length > 0) {
                        selector += '.' + classes.map(cls => CSS.escape(cls)).join('.');
                    }
                }

                // Only add nth-of-type if the selector isn't already unique among siblings
                let sib = el, nth = 1;
                while (sib = sib.previousElementSibling) {
                    if (sib.nodeName.toLowerCase() == el.nodeName.toLowerCase())
                        nth++;
                }
                if (nth != 1)
                    selector += `:nth-of-type(${nth})`;
            }
            path.unshift(selector);
            el = el.parentNode;
        }
        return path.join(" > ");
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
