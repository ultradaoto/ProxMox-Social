/**
 * Background Service Worker
 * Simplified for Static OSP Vision
 */

// Lifecycle handling
// On Install/Update, seed default rules if empty
chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.get(['osp_rules'], (result) => {
        if (!result.osp_rules || result.osp_rules.length === 0) {
            fetch(chrome.runtime.getURL('rules.json'))
                .then(response => response.json())
                .then(rules => {
                    chrome.storage.local.set({ osp_rules: rules });
                    console.log('Seeded default rules from rules.json');
                })
                .catch(err => console.log('No default rules found or invalid JSON', err));
        }
    });
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('[OSP Companion] Extension installed');
});

// We can add logic here if we need to handle specific browser events
// But for now, the content script handles the detailed logic.
