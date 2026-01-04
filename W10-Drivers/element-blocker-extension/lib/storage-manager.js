/**
 * Storage Manager
 * Wrapper for Chrome storage with caching
 */

class StorageManager {
    constructor() {
        this.cache = {};
        this.hostname = window.location.hostname;
    }

    async getSafeSelectors() {
        if (this.cache.safe) {
            return this.cache.safe;
        }

        return new Promise((resolve) => {
            chrome.runtime.sendMessage(
                { action: 'getSafeElements', hostname: this.hostname },
                (response) => {
                    this.cache.safe = response || [];
                    resolve(this.cache.safe);
                }
            );
        });
    }

    async toggleSafeElement(selector, description) {
        // Clear cache
        this.cache.safe = null;

        return new Promise((resolve) => {
            chrome.runtime.sendMessage({
                action: 'toggleSafeElement',
                hostname: this.hostname,
                selector,
                description
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

    async getSettings() {
        return new Promise((resolve) => {
            chrome.runtime.sendMessage(
                { action: 'getSettings' },
                resolve
            );
        });
    }
}

if (typeof window !== 'undefined') {
    window.StorageManager = StorageManager;
}
