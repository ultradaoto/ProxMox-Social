(function () {
    'use strict';

    // ===== STATE =====
    let isEditorMode = false;
    let userRules = [];
    let highlightElementsMap = new Map(); // Highlight DOM -> {element, rule}
    let editorHoverElement = null;
    let hiddenElements = []; // For Layer Peeler feature
    let cursorX = 0;
    let cursorY = 0;

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
        // 1. Context Checking (Optional)
        if (!isEditorMode) {
            // A. Require Context (Show only if X is present)
            if (rule.contextText) {
                const pageText = document.body.innerText;
                if (!pageText.includes(rule.contextText)) return;
            }
            // B. Exclude Context (Hide if Y is present)
            if (rule.excludedContextText) {
                const pageText = document.body.innerText;
                if (pageText.includes(rule.excludedContextText)) return;
            }
        }

        // 2. Element Selection
        let element = null;
        try {
            element = document.querySelector(rule.selector);
        } catch (e) { }

        if (element && isVisible(element)) {
            createHighlight(element, rule);

            // 3. Ensure Visible (Auto-Scroll)
            if (rule.ensureVisible) {
                const rect = element.getBoundingClientRect();
                const viewportHeight = window.innerHeight;

                const buffer = 150; // Space for label + padding

                // If element is below the fold (including buffer)
                if (rect.bottom + buffer > viewportHeight) {
                    // Debounce scroll to avoid fighting user
                    if (!element._lastScroll || Date.now() - element._lastScroll > 2000) {
                        // Scroll down just enough to show element + buffer
                        const scrollAmount = rect.bottom - viewportHeight + buffer;
                        window.scrollBy({ top: scrollAmount, behavior: 'smooth' });
                        element._lastScroll = Date.now();
                        // block: 'end' aligns to absolute bottom, which cuts off label.
                        // window.scrollBy allows us to add the custom buffer.
                    }
                }
            }
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

        // Clamp dimensions to viewport/reasonable max to prevent "flying off screen"
        const MAX_HEIGHT = 500;
        const width = rect.width;
        let height = rect.height;
        let top = rect.top + window.scrollY;

        // If element is excessively tall, we cap it and show top portion
        if (height > MAX_HEIGHT) {
            height = MAX_HEIGHT;
            // Optionally could add a visual indicator class here
            highlight.classList.add('osp-highlight-truncated');
        }

        highlight.style.left = `${rect.left + window.scrollX}px`;
        highlight.style.top = `${top}px`;
        highlight.style.width = `${width}px`;
        highlight.style.height = `${height}px`;

        const label = highlight.querySelector('.osp-highlight-label');
        if (label) {
            // Reset styles
            label.style.top = ''; label.style.bottom = ''; label.style.left = '0';

            if (labelPos === 'bottom') {
                label.style.bottom = '-28px';
                label.style.top = 'auto'; // ensure top is cleared
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
        // 1. Try simple raw selector first
        let selector = _generateRawSelector(el);
        if (document.querySelectorAll(selector).length === 1) return selector;

        // 2. Iterative Climbing (Up to 15 levels)
        let currentEl = el;
        const pathSegments = [];

        for (let i = 0; i < 50; i++) {
            if (!currentEl || currentEl.tagName === 'BODY' || currentEl.tagName === 'HTML') break;

            // 1. Get base selector (Attribute or Tag)
            let levelSelector = _generateRawSelector(currentEl);

            // 2. Always add nth-of-type for robustness unless it's an ID
            if (!levelSelector.startsWith('#')) {
                const tag = currentEl.tagName.toLowerCase();
                // If the base selector is just attributes, prepends tag for valid CSS: [role='button'] -> div[role='button']
                if (levelSelector.startsWith('[')) {
                    levelSelector = tag + levelSelector;
                }

                // Calculate Index
                if (currentEl.parentElement) {
                    const siblings = Array.from(currentEl.parentElement.children).filter(c => c.tagName.toLowerCase() === tag);
                    if (siblings.length > 1) {
                        const index = siblings.indexOf(currentEl) + 1;
                        levelSelector += `:nth-of-type(${index})`;
                    }
                }
            }

            pathSegments.unshift(levelSelector);

            // Check combined path uniqueness
            const fullPath = pathSegments.join(' > ');
            if (document.querySelectorAll(fullPath).length === 1) {
                return fullPath;
            }

            currentEl = currentEl.parentElement;
        }

        // 3. Fallback: Strict Path (Absolute)
        return getStrictPath(el);
    }

    function _generateRawSelector(el) {
        // 1. ID (only if looks stable)
        if (el.id && !/\d{5,}/.test(el.id) && !/ember|react|uid/.test(el.id)) {
            return `#${CSS.escape(el.id)}`;
        }

        // 2. Stable Attributes (Prioritized)
        const stableAttrs = ['data-testid', 'name', 'placeholder', 'aria-label', 'href', 'title', 'role', 'for'];
        for (const attr of stableAttrs) {
            if (el.hasAttribute(attr)) {
                return `[${attr}="${CSS.escape(el.getAttribute(attr))}"]`;
            }
        }

        // 3. Class (Filter junk)
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(/\s+/).filter(c => {
                if (c.length < 3) return false;

                // Allow specific semantic React prefixes
                if (c.startsWith('styled__') || c.startsWith('css-')) return true;

                // Ban pure numeric/random hashes (e.g. "af3498")
                // Only if they are short and random-looking, OR extremely long and random
                if (/^[a-z0-9]{4,8}$/.test(c)) return false; // short random hash
                if (/^[a-zA-Z0-9]{30,}$/.test(c) && !c.includes('-') && !c.includes('_')) return false; // super long unique hash

                // Standard bans
                if (/hover:|focus:|active:|visited:/.test(c)) return false;
                if (c.includes('osp-')) return false;

                return true;
            });

            // Prefer classes that look "Meaningful" (contain capital letters or dashes) over generic ones
            classes.sort((a, b) => {
                let aScore = (a.includes('Wrapper') ? 10 : 0) + (a.includes('-') ? 2 : 0) + (/[A-Z]/.test(a) ? 1 : 0);
                let bScore = (b.includes('Wrapper') ? 10 : 0) + (b.includes('-') ? 2 : 0) + (/[A-Z]/.test(b) ? 1 : 0);

                // Boost specific keywords
                if (a.includes('Submit') || a.includes('Primary') || a.includes('Confirm') || a.includes('Post')) aScore += 5;
                if (b.includes('Submit') || b.includes('Primary') || b.includes('Confirm') || b.includes('Post')) bScore += 5;

                if (aScore === bScore) {
                    // Tie-Breaker: Prefer longer, more specific names
                    // e.g. "SubmitButtonWrapper" (len 19) > "ButtonWrapper" (len 13)
                    return b.length - a.length;
                }

                return bScore - aScore;
            });

            if (classes.length > 0) {
                return `.${CSS.escape(classes[0])}`;
            }
        }

        return el.tagName.toLowerCase();
    }

    function getStrictPath(el) {
        let path = [];
        let curr = el;
        for (let i = 0; i < 20; i++) {
            if (!curr || curr.nodeType !== Node.ELEMENT_NODE || curr.tagName === 'BODY') break;

            let sel = curr.tagName.toLowerCase();
            if (curr.id && !/\d/.test(curr.id)) {
                sel += `#${CSS.escape(curr.id)}`;
                path.unshift(sel);
                break;
            }

            let sib = curr, nth = 1;
            while (sib = sib.previousElementSibling) {
                if (sib.tagName === curr.tagName) nth++;
            }
            if (nth > 1) sel += `:nth-of-type(${nth})`;

            path.unshift(sel);
            curr = curr.parentElement;
        }
        return path.join(' > ');
    }


    // ===== EDITOR MODE =====
    function handleMessages(request, sender, sendResponse) {
        if (request.type === 'PING') sendResponse({ status: 'OK' });
        if (request.type === 'toggle_editor') toggleEditor(request.active);
        if (request.type === 'reload_rules') loadUserRules(() => applyAllHighlights());
    }

    function toggleEditor(active) {
        isEditorMode = active;
        if (active) {
            document.body.style.cursor = 'crosshair';
            document.addEventListener('mouseover', onEditorHover, true);
            document.addEventListener('mousemove', onMouseMove, true); // Track cursor
            document.addEventListener('click', onEditorClick, true);
            document.addEventListener('mouseout', onEditorOut, true);
            document.addEventListener('keydown', onEditorKeydown, true);

            // Re-run highlights to reveal hidden ones (Context Ignored)
            applyAllHighlights();

            // Make highlights clickable
            document.querySelectorAll('.osp-static-highlight').forEach(el => {
                el.style.pointerEvents = 'auto';
                el.style.cursor = 'pointer';
            });
        } else {
            document.body.style.cursor = '';
            document.removeEventListener('mouseover', onEditorHover, true);
            document.removeEventListener('mousemove', onMouseMove, true);
            document.removeEventListener('click', onEditorClick, true);
            document.removeEventListener('mouseout', onEditorOut, true);
            document.removeEventListener('keydown', onEditorKeydown, true);

            removeEditorHover();
            removeModal();
            // restoreHiddenElements(); // Removed to persist hidden layers across toggles
            document.querySelectorAll('.osp-static-highlight').forEach(el => {
                el.style.pointerEvents = 'none';
            });

            applyAllHighlights();
        }
    }

    function onEditorHover(e) {
        if (e.target.closest('.osp-advanced-modal')) return;

        // IGNORE BACKDROPS
        if (e.target.className && typeof e.target.className === 'string' && e.target.className.includes('InputBackdrop')) {
            e.target.style.pointerEvents = 'none';
            return;
        }

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

    function onMouseMove(e) {
        cursorX = e.clientX;
        cursorY = e.clientY;
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

    function onEditorKeydown(e) {
        if (!isEditorMode) return;

        // H or X to HIDE element (Layer Peeler)
        if (e.key.toLowerCase() === 'h' || e.key.toLowerCase() === 'x') {
            if (editorHoverElement) {
                e.preventDefault();
                e.stopPropagation();

                // Hide it
                editorHoverElement.style.visibility = 'hidden';
                hiddenElements.push(editorHoverElement);

                console.log('[OSP] Hidden element:', editorHoverElement);

                // Force reset hover so the mouse can "fall through" to the next element
                // We need to use the tracked current cursor position
                removeEditorHover();

                // Retrigger hover check
                const elementUnder = document.elementFromPoint(cursorX, cursorY);
                if (elementUnder) {
                    onEditorHover({ target: elementUnder, preventDefault: () => { }, stopPropagation: () => { } });
                }
            }
        }

        // R to RESTORE all
        if (e.key.toLowerCase() === 'r') {
            restoreHiddenElements();
        }
    }

    function restoreHiddenElements() {
        hiddenElements.forEach(el => el.style.visibility = '');
        hiddenElements = [];
        console.log('[OSP] Restored all hidden elements.');
    }


    // ===== ADVANCED MODAL =====
    function showAdvancedModal(targetElement, clickX, clickY, existingRule = null) {
        removeModal();

        const isEditing = !!existingRule;
        const selector = isEditing ? existingRule.selector : generateSelector(targetElement);
        const defaultLabel = isEditing ? existingRule.label : '';
        const defaultColor = isEditing ? existingRule.color : COLORS[0].value;
        const defaultShape = isEditing ? existingRule.style : 'rectangle';
        const defaultPos = (isEditing && existingRule.labelPosition) ? existingRule.labelPosition : 'top';
        const defaultContext = (isEditing && existingRule.contextText) ? existingRule.contextText : '';

        // Check uniqueness for UI feedback
        const matchCount = document.querySelectorAll(selector).length;
        const isUnique = matchCount === 1;

        const modal = document.createElement('div');
        modal.className = 'osp-advanced-modal';
        modal.style.visibility = 'hidden'; // Hide to measure
        modal.style.top = '0px';
        modal.style.left = '0px';

        // UI Generation
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

                <div style="display:flex; gap:16px;">
                    <div class="osp-form-group" style="flex:1">
                        <label class="osp-label">Shape</label>
                        <div class="osp-options-row">
                            <button class="osp-option-btn osp-shape-btn ${defaultShape === 'rectangle' ? 'selected' : ''}" data-value="rectangle">Box</button>
                            <button class="osp-option-btn osp-shape-btn ${defaultShape === 'circle' ? 'selected' : ''}" data-value="circle">Circle</button>
                            <button class="osp-option-btn osp-shape-btn ${defaultShape === 'underline' ? 'selected' : ''}" data-value="underline">Line</button>
                        </div>
                    </div>
                    <div class="osp-form-group" style="flex:1">
                        <label class="osp-label">Label Position</label>
                        <div class="osp-options-row">
                            <button class="osp-option-btn osp-pos-btn ${defaultPos === 'top' ? 'selected' : ''}" data-value="top">Top</button>
                            <button class="osp-option-btn osp-pos-btn ${defaultPos === 'bottom' ? 'selected' : ''}" data-value="bottom">Bottom</button>
                            <button class="osp-option-btn osp-pos-btn ${defaultPos === 'inside' ? 'selected' : ''}" data-value="inside">Inside</button>
                        </div>
                    </div>
                </div>

                <div class="osp-form-group">
                    <label class="osp-label">Visibility Context (Optional)</label>
                    <div style="display:flex; flex-direction:column; gap:8px;">
                        <input type="text" class="osp-input" id="osp-context-input" placeholder="✅ Show ONLY if page says... e.g. 'Create Post'" value="${defaultContext}">
                        <input type="text" class="osp-input" id="osp-excluded-context-input" placeholder="❌ HIDE if page says... e.g. 'Success'" value="${existingRule ? (existingRule.excludedContextText || '') : ''}">
                    </div>
                    <div style="font-size:10px; color:#6b7280; margin-top:2px;">Use these to prevent false positives on other screens.</div>
                </div>

                <div class="osp-form-group">
                     <label class="osp-label" style="display:flex; align-items:center; gap:8px; cursor:pointer;">
                        <input type="checkbox" id="osp-ensure-visible" ${existingRule && existingRule.ensureVisible ? 'checked' : ''}>
                        <span>⚓ Ensure Visible (Auto-Scroll)</span>
                    </label>
                    <div style="font-size:10px; color:#6b7280; margin-left:20px;">If this falls off-screen, auto-scroll to keep it visible.</div>
                </div>

                <div class="osp-form-group">
                    <label class="osp-label" style="display:flex; justify-content:space-between;">
                        <span>CSS Selector</span>
                        <span id="osp-match-count" style="color:${isUnique ? '#10b981' : '#f59e0b'}">
                            ${isUnique ? '✅ Unique Match' : '⚠️ Matches ' + matchCount}
                        </span>
                    </label>
                    <div style="display:flex; gap:8px;">
                        <input type="text" class="osp-input osp-code-input" id="osp-selector-input" value="${selector.replace(/"/g, '&quot;')}" style="flex:1">
                        <button class="osp-btn-secondary" id="osp-regen-btn" title="Regenerate Selector">🔄</button>
                    </div>
                </div>
            </div>
            <div class="osp-modal-footer">
                ${isEditing ? '<button class="osp-btn osp-btn-danger" id="osp-delete-btn" title="Delete Rule">🗑 Delete</button>' : ''}
                <button class="osp-btn osp-btn-secondary" id="osp-cancel-btn">Cancel</button>
                <button class="osp-btn osp-btn-primary" id="osp-save-btn">Save Rule</button>
            </div>
        `;

        document.body.appendChild(modal);

        // Smart Positioning (Bounds Check)
        const rect = modal.getBoundingClientRect();
        const viewportW = window.innerWidth;
        const viewportH = window.innerHeight;

        // Default: try to place slightly offset from cursor
        let finalX = clickX + 10;
        let finalY = clickY + 10;

        // X Axis Check
        if (finalX + rect.width > viewportW) {
            finalX = viewportW - rect.width - 20;
            if (finalX < 10) finalX = 10;
        }

        // Y Axis Check
        if (finalY + rect.height > viewportH) {
            finalY = viewportH - rect.height - 20;
            // Try shifting above if still tight
            if (finalY < 10) {
                const tryAbove = clickY - rect.height - 10;
                if (tryAbove > 0) finalY = tryAbove;
            }
        }

        modal.style.left = `${finalX}px`;
        modal.style.top = `${finalY}px`;
        modal.style.visibility = 'visible'; // Show after move

        // Inputs
        const labelInput = modal.querySelector('#osp-label-input');
        const selectorInput = modal.querySelector('#osp-selector-input');
        const contextInput = modal.querySelector('#osp-context-input');
        const excludedContextInput = modal.querySelector('#osp-excluded-context-input');
        const matchCountSpan = modal.querySelector('#osp-match-count');
        labelInput.focus();

        // REGENERATE CLICK
        modal.querySelector('#osp-regen-btn').onclick = () => {
            const newSelector = generateSelector(targetElement);
            selectorInput.value = newSelector;

            // Update match count info
            const count = document.querySelectorAll(newSelector).length;
            matchCountSpan.textContent = count === 1 ? '✅ Unique Match' : '⚠️ Matches ' + count;
            matchCountSpan.style.color = count === 1 ? '#10b981' : '#f59e0b';

            // Flash input to show update
            selectorInput.style.backgroundColor = '#d1fae5';
            setTimeout(() => selectorInput.style.backgroundColor = '', 300);
        };

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

        // Position Click
        modal.querySelectorAll('.osp-pos-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.osp-pos-btn').forEach(b => b.classList.remove('selected'));
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
            const position = modal.querySelector('.osp-pos-btn.selected').dataset.value;
            const contextText = contextInput.value ? contextInput.value.trim() : '';
            const excludedContextText = excludedContextInput.value ? excludedContextInput.value.trim() : '';
            const ensureVisible = modal.querySelector('#osp-ensure-visible').checked;
            const finalSelector = selectorInput.value.trim();

            const rule = {
                id: isEditing ? existingRule.id : null,
                domain: window.location.hostname,
                selector: finalSelector,
                label: label,
                color: color,
                style: shape,
                labelPosition: position,
                contextText: contextText,
                excludedContextText: excludedContextText,
                ensureVisible: ensureVisible
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
        observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true });

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
