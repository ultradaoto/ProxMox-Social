(function () {
    'use strict';

    // ===== STATE =====
    let isEditorMode = false;
    let userRules = [];
    let highlightElementsMap = new Map(); // Highlight DOM -> {element, rule}
    let editorHoverElement = null;

    // ===== CONFIG =====
    // Colors: Tailwind css values
    const COLORS = [
        { name: 'Green', value: '#10b981' },
        { name: 'Blue', value: '#3b82f6' },
        { name: 'Red', value: '#ef4444' },
        { name: 'Purple', value: '#a855f7' },
        { name: 'Orange', value: '#f97316' }
    ];

    // ===== INITIALIZATION =====
    function init() {
        console.log('[OSP Vision Helper] Initializing...');
        loadUserRules(() => applyAllHighlights());
        observeDomChanges();
        chrome.runtime.onMessage.addListener(handleMessages);
    }


    // ===== RULE MANAGEMENT =====
    function loadUserRules(callback) {
        chrome.storage.local.get(['osp_rules'], (result) => {
            if (result.osp_rules) {
                userRules = result.osp_rules;
            }
            if (callback) callback();
        });
    }

    function saveUserRule(newRule) {
        if (!newRule.id) newRule.id = Date.now().toString(36);

        // Check if updating existing
        const index = userRules.findIndex(r => r.id === newRule.id);
        if (index >= 0) {
            userRules[index] = newRule;
        } else {
            userRules.push(newRule);
        }

        chrome.storage.local.set({ osp_rules: userRules }, () => {
            applyAllHighlights();
        });
    }

    function deleteUserRule(ruleId) {
        userRules = userRules.filter(r => r.id !== ruleId);
        chrome.storage.local.set({ osp_rules: userRules }, () => {
            applyAllHighlights();
        });
    }


    // ===== HIGHLIGHTING ENGINE =====
    function applyAllHighlights() {
        // Cleanup old highlights matching our system
        document.querySelectorAll('.osp-static-highlight').forEach(el => el.remove());
        highlightElementsMap.clear();

        const hostname = window.location.hostname;

        // Apply User Rules
        const activeUserRules = userRules.filter(rule => hostname.includes(rule.domain));
        activeUserRules.forEach(rule => processRule(rule));
    }

    function processRule(rule) {
        let element = null;
        try {
            element = document.querySelector(rule.selector);
        } catch (e) { }

        if (element && isVisible(element)) {
            // Verify if selector matches multiple
            // In debug mode we might want to warn
            createHighlight(element, rule);
        }
    }

    function isVisible(element) {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }


    // ===== VISUAL RENDERING =====
    function createHighlight(element, rule) {
        const highlight = document.createElement('div');
        highlight.className = 'osp-static-highlight';
        highlight.dataset.ruleId = rule.id; // Store ID for editing

        // Shape
        if (rule.style === 'circle') highlight.classList.add('osp-shape-circle');
        else if (rule.style === 'pill') highlight.classList.add('osp-shape-pill');
        else if (rule.style === 'underline') highlight.classList.add('osp-shape-underline');
        else highlight.classList.add('osp-rectangle'); // default

        // Color
        const color = rule.color || '#10b981';
        highlight.style.borderColor = color;

        // Label
        const label = document.createElement('div');
        label.className = 'osp-highlight-label';
        label.textContent = rule.label;
        label.style.backgroundColor = color;

        highlight.appendChild(label);
        document.body.appendChild(highlight);

        // Position
        updateHighlightPosition(highlight, element, rule.labelPosition);

        // Store for interaction
        highlightElementsMap.set(highlight, { element, rule });
    }

    function updateHighlightPosition(highlight, element, labelPos = 'top') {
        const rect = element.getBoundingClientRect();
        highlight.style.left = `${rect.left + window.scrollX}px`;
        highlight.style.top = `${rect.top + window.scrollY}px`;
        highlight.style.width = `${rect.width}px`;
        highlight.style.height = `${rect.height}px`;

        const label = highlight.querySelector('.osp-highlight-label');
        if (label) {
            // Reset styles
            label.style.top = ''; label.style.bottom = ''; label.style.left = '0';

            if (labelPos === 'bottom') {
                label.style.bottom = '-28px';
            } else if (labelPos === 'inside') {
                label.style.top = '2px';
            } else {
                // Top (Default)
                label.style.top = '-28px';
            }
        }
    }

    // ===== DEEP DEBUGGER =====
    function inspectElement(element, rule = null) {
        console.clear();
        console.log('%c OSP Deep Inspector ', 'background: #10b981; color: white; padding: 4px; border-radius: 4px; font-weight: bold; font-size: 14px;');

        // 1. Element Info
        console.group('🔍 Element Details');
        console.log('DOM Element:', element);
        console.log('Dimensions:', element.getBoundingClientRect());
        console.log('Computed Style:', window.getComputedStyle(element));

        // Attributes
        const attrs = {};
        for (let i = 0; i < element.attributes.length; i++) {
            attrs[element.attributes[i].name] = element.attributes[i].value;
        }
        console.log('Attributes:', attrs);
        console.groupEnd();

        // 2. React Fiber Extraction
        console.group('⚛️ React Internals');
        const fiberKey = Object.keys(element).find(key => key.startsWith('__reactFiber$') || key.startsWith('__reactInternalInstance$'));
        if (fiberKey) {
            console.log('Fiber Key:', fiberKey);
            const fiber = element[fiberKey];
            console.log('Fiber Node:', fiber);

            // Try to dump Props & State
            if (fiber.memoizedProps) console.log('Props:', fiber.memoizedProps);
            if (fiber.memoizedState) console.log('State:', fiber.memoizedState);
            if (fiber.return) console.log('Parent Component:', fiber.return.type);
        } else {
            console.warn('No React Fiber data found on this element.');
        }
        console.groupEnd();

        // 3. Rule Analysis
        if (rule) {
            console.group('📏 Current Rule');
            console.log('Rule Config:', rule);
            const matchCount = document.querySelectorAll(rule.selector).length;
            console.log(`Selector "${rule.selector}" matches ${matchCount} element(s).`);
            if (matchCount > 1) {
                console.warn('⚠️ SELECTOR IS NOT UNIQUE! This causes drift.');
                console.log('Matches:', document.querySelectorAll(rule.selector));
            }
            console.groupEnd();
        }

        // 4. Selector Generation Debug
        console.group('🛠 Selector Generation Logic');
        const generated = generateSelector(element);
        console.log('Auto-Generated Selector:', generated);
        const genCount = document.querySelectorAll(generated).length;
        console.log(`Matches ${genCount} element(s).`);
        console.groupEnd();

        alert('Check Chrome DevTools Console (F12) for deep inspection data.');
    }


    // ===== SELECTOR GENERATION (HARDENED) =====
    function generateSelector(el) {
        const selector = _generateRawSelector(el);

        // Verify uniqueness
        const matches = document.querySelectorAll(selector);
        if (matches.length === 1) return selector;

        console.warn(`[OSP] Generated selector "${selector}" is not unique (${matches.length}). attempting hardening...`);

        // Hardening 1: Add parent context
        if (el.parentElement) {
            const parentSel = _generateRawSelector(el.parentElement);
            const combined = `${parentSel} > ${selector}`;
            if (document.querySelectorAll(combined).length === 1) return combined;
        }

        // Hardening 2: Nth-of-type fallback (Very strict but reliable against drift within a list)
        // This is dangerous if list order changes, but better than random jumping
        const path = getStrictPath(el);
        return path;
    }

    function _generateRawSelector(el) {
        // 1. ID (only if looks stable - no numbers or long hashes)
        if (el.id && !/\d{5,}/.test(el.id) && !/ember|react|uid/.test(el.id)) {
            return `#${CSS.escape(el.id)}`;
        }

        // 2. Stable Attributes (Prioritized)
        const stableAttrs = ['data-testid', 'name', 'placeholder', 'aria-label', 'href', 'type'];
        for (const attr of stableAttrs) {
            if (el.hasAttribute(attr)) {
                return `[${attr}="${CSS.escape(el.getAttribute(attr))}"]`;
            }
        }

        // 3. Class (Filter junk)
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(/\s+/).filter(c => {
                // Ignore hash-like classes (common in styled-components, css modules)
                if (c.length < 3) return false;
                if (/[a-zA-Z0-9]{10,}/.test(c)) return false; // Long hashes
                if (/hover:|focus:|active:/.test(c)) return false; // States
                if (c.includes('osp-')) return false;
                return true;
            });

            // Try first meaningful class
            if (classes.length > 0) {
                // Try to verify if this single class is unique enough locally?
                // No, just return it, verification happens in caller
                return `.${CSS.escape(classes[0])}`;
            }
        }

        return el.tagName.toLowerCase();
    }

    function getStrictPath(el) {
        let path = [];
        let curr = el;
        // Limit depth to 5 parents to avoid infinitely long selectors
        for (let i = 0; i < 5; i++) {
            if (!curr || curr.nodeType !== Node.ELEMENT_NODE) break;

            let sel = curr.tagName.toLowerCase();
            if (curr.id && !/\d/.test(curr.id)) {
                sel += `#${CSS.escape(curr.id)}`;
                path.unshift(sel);
                break; // ID is usually anchor enough
            } else {
                // Use nth-of-type for robustness
                let sib = curr, nth = 1;
                while (sib = sib.previousElementSibling) {
                    if (sib.tagName === curr.tagName) nth++;
                }
                sel += `:nth-of-type(${nth})`;
            }
            path.unshift(sel);
            curr = curr.parentElement;
        }
        return path.join(' > ');
    }


    // ===== EDITOR MODE =====
    function handleMessages(request, sender, sendResponse) {
        if (request.type === 'toggle_editor') toggleEditor(request.active);
        if (request.type === 'reload_rules') loadUserRules(() => applyAllHighlights());
    }

    function toggleEditor(active) {
        isEditorMode = active;
        if (active) {
            document.body.style.cursor = 'crosshair';
            document.addEventListener('mouseover', onEditorHover, true);
            document.addEventListener('click', onEditorClick, true);
            document.addEventListener('mouseout', onEditorOut, true);

            // Make highlights clickable
            document.querySelectorAll('.osp-static-highlight').forEach(el => {
                el.style.pointerEvents = 'auto';
                el.style.cursor = 'pointer';
            });
        } else {
            document.body.style.cursor = '';
            document.removeEventListener('mouseover', onEditorHover, true);
            document.removeEventListener('click', onEditorClick, true);
            document.removeEventListener('mouseout', onEditorOut, true);

            removeEditorHover();
            removeModal();

            // Reset highlights
            document.querySelectorAll('.osp-static-highlight').forEach(el => {
                el.style.pointerEvents = 'none';
            });

            applyAllHighlights();
        }
    }

    function onEditorHover(e) {
        if (e.target.closest('.osp-advanced-modal')) return;

        // If hovering over an existing highlight, highlight IT (visual feedback)
        if (e.target.classList.contains('osp-static-highlight')) {
            return;
        }

        if (editorHoverElement && editorHoverElement !== e.target) {
            editorHoverElement.classList.remove('osp-editor-hover');
        }

        editorHoverElement = e.target;
        editorHoverElement.classList.add('osp-editor-hover');
        e.preventDefault();
        e.stopPropagation();
    }

    function removeEditorHover() {
        if (editorHoverElement) {
            editorHoverElement.classList.remove('osp-editor-hover');
            editorHoverElement = null;
        }
    }

    function onEditorOut(e) {
        if (e.target.classList.contains('osp-editor-hover')) {
            e.target.classList.remove('osp-editor-hover');
        }
    }

    function onEditorClick(e) {
        if (!isEditorMode) return;
        if (e.target.closest('.osp-advanced-modal')) return;

        e.preventDefault();
        e.stopPropagation();

        // Check if we clicked an existing highlight
        if (e.target.classList.contains('osp-static-highlight') || e.target.classList.contains('osp-highlight-label')) {
            const highlight = e.target.closest('.osp-static-highlight');
            const data = highlightElementsMap.get(highlight);
            if (data) {
                showAdvancedModal(data.element, e.clientX, e.clientY, data.rule);
                return;
            }
        }

        // Otherwise, new element
        const target = e.target;
        showAdvancedModal(target, e.clientX, e.clientY);
    }


    // ===== ADVANCED MODAL =====
    function showAdvancedModal(targetElement, x, y, existingRule = null) {
        removeModal();

        const isEditing = !!existingRule;
        const selector = isEditing ? existingRule.selector : generateSelector(targetElement);
        const defaultLabel = isEditing ? existingRule.label : '';
        const defaultColor = isEditing ? existingRule.color : COLORS[0].value;
        const defaultShape = isEditing ? existingRule.style : 'rectangle';

        const modal = document.createElement('div');
        modal.className = 'osp-advanced-modal';

        // UI Generation (Keep mostly same as before, add Debug button)
        const colorGridHtml = COLORS.map(c =>
            `<div class="osp-color-option ${c.value === defaultColor ? 'selected' : ''}" 
                  style="background-color: ${c.value}" 
                  data-value="${c.value}" 
                  title="${c.name}"></div>`
        ).join('');

        modal.innerHTML = `
            <div class="osp-modal-header">
                <div class="osp-modal-title">${isEditing ? 'Edit Rule' : 'New Tag'}</div>
                <div style="display:flex; gap:8px;">
                     <button class="osp-btn-secondary" id="osp-debug-btn" title="Inspect Element">🐛</button>
                     <button class="osp-btn-secondary" id="osp-close-btn">✕</button>
                </div>
            </div>
            <div class="osp-modal-body">
                <div class="osp-form-group">
                    <label class="osp-label">Label Text</label>
                    <input type="text" class="osp-input" id="osp-label-input" placeholder="e.g. Upload Button" value="${defaultLabel}" autofocus>
                </div>

                <div class="osp-form-group">
                    <label class="osp-label">Color</label>
                    <div class="osp-color-grid">
                        ${colorGridHtml}
                    </div>
                </div>

                <div class="osp-form-group">
                    <label class="osp-label">Shape</label>
                    <div class="osp-shape-options">
                        <button class="osp-shape-btn ${defaultShape === 'rectangle' ? 'selected' : ''}" data-value="rectangle">Box</button>
                        <button class="osp-shape-btn ${defaultShape === 'circle' ? 'selected' : ''}" data-value="circle">Circle</button>
                        <button class="osp-shape-btn ${defaultShape === 'underline' ? 'selected' : ''}" data-value="underline">Line</button>
                    </div>
                </div>

                <div class="osp-form-group">
                    <label class="osp-label">CSS Selector (Verified)</label>
                    <input type="text" class="osp-input osp-code-input" id="osp-selector-input" value="${selector}">
                </div>
            </div>
            <div class="osp-modal-footer">
                ${isEditing ? '<button class="osp-btn osp-btn-danger" id="osp-delete-btn" title="Delete Rule">🗑 Delete</button>' : ''}
                <button class="osp-btn osp-btn-secondary" id="osp-cancel-btn">Cancel</button>
                <button class="osp-btn osp-btn-primary" id="osp-save-btn">Save Rule</button>
            </div>
        `;

        // Smart Positioning
        const modalX = Math.min(x, window.innerWidth - 400);
        const modalY = Math.min(y, window.innerHeight - 500);
        modal.style.left = `${Math.max(10, modalX)}px`;
        modal.style.top = `${Math.max(10, modalY)}px`;

        document.body.appendChild(modal);

        // Inputs
        const labelInput = modal.querySelector('#osp-label-input');
        const selectorInput = modal.querySelector('#osp-selector-input');
        labelInput.focus();

        // Color Click
        modal.querySelectorAll('.osp-color-option').forEach(opt => {
            opt.addEventListener('click', () => {
                modal.querySelectorAll('.osp-color-option').forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
            });
        });

        // Shape Click
        modal.querySelectorAll('.osp-shape-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.osp-shape-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
            });
        });

        // ACTIONS
        modal.querySelector('#osp-close-btn').onclick = removeModal;
        modal.querySelector('#osp-cancel-btn').onclick = removeModal;

        modal.querySelector('#osp-debug-btn').onclick = () => {
            inspectElement(targetElement, existingRule);
        };

        if (isEditing) {
            modal.querySelector('#osp-delete-btn').onclick = () => {
                if (confirm('Delete this rule permanently?')) {
                    deleteUserRule(existingRule.id);
                    removeModal();
                    removeEditorHover();
                }
            };
        }

        modal.querySelector('#osp-save-btn').onclick = () => {
            const label = labelInput.value.trim();
            if (!label) return;

            const color = modal.querySelector('.osp-color-option.selected').dataset.value;
            const shape = modal.querySelector('.osp-shape-btn.selected').dataset.value;
            const finalSelector = selectorInput.value.trim();

            const rule = {
                id: isEditing ? existingRule.id : null,
                domain: window.location.hostname,
                selector: finalSelector,
                label: label,
                color: color,
                style: shape
            };

            saveUserRule(rule);
            removeModal();
            removeEditorHover();
        };

        modal.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') removeModal();
            if (e.key === 'Enter') modal.querySelector('#osp-save-btn').click();
        });
    }

    function removeModal() {
        const modal = document.querySelector('.osp-advanced-modal');
        if (modal) modal.remove();
    }


    // ===== LOOP =====
    function observeDomChanges() {
        // High frequency DOM observation for SPA stability
        const observer = new MutationObserver(() => {
            requestAnimationFrame(() => {
                if (!isEditorMode) applyAllHighlights();
            });
        });
        observer.observe(document.body, { childList: true, subtree: true });

        window.addEventListener('resize', () => {
            if (!isEditorMode) applyAllHighlights();
        });

        window.addEventListener('scroll', () => {
            // Update highlight positions without full DOM scan
            document.querySelectorAll('.osp-static-highlight').forEach(highlight => {
                const data = highlightElementsMap.get(highlight);
                if (data && data.element && isVisible(data.element)) {
                    updateHighlightPosition(highlight, data.element, data.rule.labelPosition);
                } else {
                    highlight.style.display = 'none'; // Temporarily hide if lost
                }
            });
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
