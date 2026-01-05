/**
 * OSP Content Script
 * Highlights elements and reports interactions
 */
(function () {
    console.log('[OSP] Content Script Initialized');

    let highlightedElement = null;
    let highlightOverlay = null;

    let isRecording = false;

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
        } else {
            document.removeEventListener('click', onGlobalClick, true);
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
            // console.log('[OSP] Click detected:', selector);
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
                    // Ignore spam
                    return;
                }
                lastHighlightTime = now;
                lastHighlightSelector = payload.selector;
                highlightElement(payload.selector, payload.label);
                break;
            case 'clear_highlights':
                clearHighlights();
                break;
            case 'start_recording':
                toggleRecording(true);
                break;
            case 'stop_recording':
                toggleRecording(false);
                break;
        }
    }

    async function highlightElement(selector, label) {
        clearHighlights();

        // Try to find the element with retries (up to 5s)
        let element = null;
        try {
            element = await waitForElement(selector, 5000);
        } catch (e) {
            // Timed out
        }

        if (!element) {
            console.warn('[OSP] Element not found (after 5s):', selector);
            sendToBackground('element_not_found', { selector: selector });
            return;
        }

        highlightedElement = element;
        highlightOverlay = document.createElement('div');
        highlightOverlay.className = 'osp-highlight-overlay';

        let extraClass = '';
        if (label.toLowerCase().includes('paste')) extraClass = 'paste';
        if (label.toLowerCase().includes('post') || label.toLowerCase().includes('submit')) extraClass = 'submit';
        if (extraClass) highlightOverlay.classList.add(extraClass);

        highlightOverlay.innerHTML = `
            <div class="osp-highlight-label">${label}</div>
            <div class="osp-highlight-arrow">⬇</div>
        `;

        document.body.appendChild(highlightOverlay);
        positionOverlay(element);

        window.addEventListener('scroll', onScroll, true);
        window.addEventListener('resize', onResize);

        element.classList.add('osp-highlighted-element');
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });

        element.addEventListener('click', onHighlightedElementClick);
        element.addEventListener('focus', onHighlightedElementFocus);
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
        highlightOverlay.style.position = 'fixed';
        highlightOverlay.style.left = `${rect.left + rect.width / 2}px`;
        highlightOverlay.style.top = `${rect.top - 60}px`;
        highlightOverlay.style.transform = 'translateX(-50%)';
        highlightOverlay.style.zIndex = '999999';
    }

    function clearHighlights() {
        if (highlightOverlay) {
            highlightOverlay.remove();
            highlightOverlay = null;
        }
        window.removeEventListener('scroll', onScroll, true);
        window.removeEventListener('resize', onResize);
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
        // 1. ID
        if (element.id) return '#' + CSS.escape(element.id);

        // 2. Important Attributes
        const attributes = ['name', 'placeholder', 'aria-label', 'data-testid', 'data-id', 'role'];
        for (const attr of attributes) {
            if (element.hasAttribute(attr)) {
                const val = element.getAttribute(attr);
                // Ensure value isn't too long or crazy
                if (val && val.length < 50) {
                    const selector = `[${attr}='${CSS.escape(val)}']`;
                    if (document.querySelectorAll(selector).length === 1) return selector;
                    // Try combining with tag if not unique
                    const tagSelector = `${element.tagName.toLowerCase()}${selector}`;
                    if (document.querySelectorAll(tagSelector).length === 1) return tagSelector;
                }
            }
        }

        // 3. Unique Text Content (for buttons/labels/spans)
        if (['BUTTON', 'A', 'LABEL', 'SPAN', 'DIV'].includes(element.tagName) && element.innerText.trim().length > 0 && element.innerText.trim().length < 30) {
            // This is tricky for CSS selectors, better to use XPath or :contains (not standard).
            // We'll stick to CSS structure for now, but keeping text in mind for future.
        }

        // 4. Classes (careful of generic Tailwind/Utility classes)
        if (element.className && typeof element.className === 'string') {
            const classes = element.className.trim().split(/\s+/);
            // Try single classes first
            for (const cls of classes) {
                if (!cls) continue;
                const selector = '.' + CSS.escape(cls);
                if (document.querySelectorAll(selector).length === 1) return selector;
            }
            // Try combinations of 2
            if (classes.length >= 2) {
                const selector = '.' + CSS.escape(classes[0]) + '.' + CSS.escape(classes[1]);
                if (document.querySelectorAll(selector).length === 1) return selector;
            }
        }

        // 5. CSS Path (Recursive Parent)
        return getCssPath(element);
    }

    function getCssPath(el) {
        if (!(el instanceof Element)) return;
        const path = [];
        while (el.nodeType === Node.ELEMENT_NODE) {
            let selector = el.nodeName.toLowerCase();
            if (el.id) {
                selector += '#' + CSS.escape(el.id);
                path.unshift(selector);
                break;
            } else {
                let sib = el, nth = 1;
                while (sib = sib.previousElementSibling) {
                    if (sib.nodeName.toLowerCase() == selector)
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
