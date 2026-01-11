/**
 * Background Service Worker
 * Simplified for Static OSP Vision
 */

// Lifecycle handling
chrome.runtime.onInstalled.addListener(() => {
    console.log('[OSP Companion] Extension installed');
});

// We can add logic here if we need to handle specific browser events
// But for now, the content script handles the detailed logic.
