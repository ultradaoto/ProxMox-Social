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
    console.log("Content received:", type, payload);

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
    // We try the selector, then try splitting it if it's multiple comma-sep selectors
    let element = document.querySelector(selector);

    if (!element) {
        // try alternatives from passed logic or hardcoded
        console.warn(`Element not found: ${selector}`);
        return;
    }

    highlightedElement = element;

    // Create overlay
    highlightOverlay = document.createElement('div');
    highlightOverlay.className = 'osp-highlight-overlay';

    // Determine style based on label content
    let extraClass = '';
    if (label.toLowerCase().includes('paste')) extraClass = 'paste';
    if (label.toLowerCase().includes('post') || label.toLowerCase().includes('submit')) extraClass = 'submit';
    if (extraClass) highlightOverlay.classList.add(extraClass);

    highlightOverlay.innerHTML = `
        <div class="osp-highlight-label">${label}</div>
        <div class="osp-highlight-arrow">⬇</div>
    `;

    // Position overlay
    document.body.appendChild(highlightOverlay);
    positionOverlay(element);

    // Update position on scroll/resize
    window.addEventListener('scroll', updateOverlayPosition, true);
    window.addEventListener('resize', updateOverlayPosition);

    // Add highlight to element
    element.classList.add('osp-highlighted-element');

    // Scroll element into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Add click listener
    element.addEventListener('click', onHighlightedElementClick);
    element.addEventListener('focus', onHighlightedElementFocus);
}

function updateOverlayPosition() {
    if (highlightedElement && highlightOverlay) {
        positionOverlay(highlightedElement);
    }
}

// Position the overlay above the element
function positionOverlay(element) {
    const rect = element.getBoundingClientRect();

    // Account for scrolling if using absolute/fixed mix, 
    // but here we use fixed for overlay so we just need viewport rel coords
    highlightOverlay.style.position = 'fixed';
    highlightOverlay.style.left = `${rect.left + rect.width / 2}px`;
    highlightOverlay.style.top = `${rect.top - 60}px`;
    highlightOverlay.style.transform = 'translateX(-50%)';
    highlightOverlay.style.zIndex = '2147483647'; // Max Z-Index
}

// Clear all highlights
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
    // Only report if we are inside a tracked input or the highlighted element
    if (target.matches('input, textarea, [contenteditable]')) {
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
    }
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
    try {
        chrome.runtime.sendMessage({
            target: 'background',
            type: type,
            payload: payload
        });
    } catch (e) {
        console.log("Extension connection lost/reset:", e);
    }
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
