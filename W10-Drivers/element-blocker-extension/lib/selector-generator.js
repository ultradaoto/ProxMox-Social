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
