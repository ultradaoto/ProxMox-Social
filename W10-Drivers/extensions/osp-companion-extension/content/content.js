/**
 * OSP Content Script
 * Highlights elements and reports interactions
 */
(function () {
    console.log('[OSP] Content Script Initialized');

    let highlightedElement = null;
    let highlightOverlay = null;

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        if (message.action === 'OSP_MESSAGE') {
            const { ospType, payload } = message;
            handleOSPMessage(ospType, payload);
        }
    });

    let lastHighlightTime = 0;
    let lastHighlightSelector = '';
    const SPAM_THRESHOLD_MS = 500;

    function handleOSPMessage(type, payload) {
        // console.log('[OSP] Msg:', type, payload); // Comment out to reduce console spam
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
        }
    }

    function highlightElement(selector, label) {
        clearHighlights();
        let element = document.querySelector(selector);
        if (!element) {
            console.warn('[OSP] Element not found:', selector);
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
        if (element.id) return '#' + element.id;
        if (element.getAttribute('data-placeholder')) return `[data-placeholder='${element.getAttribute('data-placeholder')}']`;
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
