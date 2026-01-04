/**
 * Background Service Worker
 * Handles message routing, context menus, and storage coordination
 */

// Initialize context menu on install
chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: 'toggle-safe',
        title: 'Toggle Safe Zone status',
        contexts: ['all']
    });

    chrome.contextMenus.create({
        id: 'pick-color',
        title: 'Pick color from element',
        contexts: ['all']
    });

    // Initialize storage structure
    chrome.storage.local.get(['sites'], (result) => {
        if (!result.sites) {
            chrome.storage.local.set({ sites: {} });
        }
    });
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === 'toggle-safe') {
        chrome.tabs.sendMessage(tab.id, {
            action: 'startEditMode',
            clickCoords: { x: info.x, y: info.y }
        });
    } else if (info.menuItemId === 'pick-color') {
        chrome.tabs.sendMessage(tab.id, {
            action: 'startColorPickerMode',
            clickCoords: { x: info.x, y: info.y }
        });
    }
});

// Handle keyboard shortcuts
chrome.commands.onCommand.addListener((command, tab) => {
    if (command === 'toggle-focus-mode') {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleFocusMode' });
    } else if (command === 'toggle-edit-mode') {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleEditMode' });
    } else if (command === 'toggle-color-picker') {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleColorPickerMode' });
    }
});

// Handle messages from content scripts and popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    switch (request.action) {
        case 'getSafeElements':
            getSafeElements(request.hostname).then(sendResponse);
            return true;

        case 'toggleSafeElement':
            toggleSafeElement(request.hostname, request.selector, request.description)
                .then(sendResponse);
            return true;

        case 'getColorHistory':
            getColorHistory().then(sendResponse);
            return true;

        case 'saveColor':
            saveColor(request.color).then(sendResponse);
            return true;

        case 'getActiveMode':
            getActiveMode(request.hostname).then(sendResponse);
            return true;

        case 'setActiveMode':
            setActiveMode(request.hostname, request.mode).then(sendResponse);
            return true;

        case 'getGuides':
            getGuides(request.hostname).then(sendResponse);
            return true;

        case 'saveGuide':
            saveGuide(request.hostname, request.guide).then(sendResponse);
            return true;
    }
});

async function getGuides(hostname) {
    const result = await chrome.storage.local.get(['sites']);
    const sites = result.sites || {};
    return sites[hostname]?.guides || [];
}

async function saveGuide(hostname, guide) {
    const result = await chrome.storage.local.get(['sites']);
    const sites = result.sites || {};

    if (!sites[hostname]) {
        sites[hostname] = { safeElements: [], settings: {}, guides: [] };
    }
    if (!sites[hostname].guides) {
        sites[hostname].guides = [];
    }

    // Update or Add
    const index = sites[hostname].guides.findIndex(g => g.id === guide.id);
    if (index >= 0) {
        sites[hostname].guides[index] = guide;
    } else {
        sites[hostname].guides.push(guide);
    }

    await chrome.storage.local.set({ sites });
    return { success: true };
}

async function getActiveMode(hostname) {
    const result = await chrome.storage.local.get(['sites']);
    const sites = result.sites || {};
    return sites[hostname]?.settings?.activeMode || 'NONE';
}

async function setActiveMode(hostname, mode) {
    const result = await chrome.storage.local.get(['sites']);
    const sites = result.sites || {};

    if (!sites[hostname]) {
        sites[hostname] = { safeElements: [], settings: {} };
    }
    if (!sites[hostname].settings) {
        sites[hostname].settings = {};
    }

    sites[hostname].settings.activeMode = mode;
    await chrome.storage.local.set({ sites });
    return { success: true };

    // Storage functions
    async function getSafeElements(hostname) {
        const result = await chrome.storage.local.get(['sites']);
        const sites = result.sites || {};
        return sites[hostname]?.safeElements || [];
    }

    async function toggleSafeElement(hostname, selector, description) {
        const result = await chrome.storage.local.get(['sites']);
        const sites = result.sites || {};

        if (!sites[hostname]) {
            sites[hostname] = { safeElements: [], settings: {} };
        }

        // Check if already safe
        const index = sites[hostname].safeElements.findIndex(
            el => el.selector === selector
        );

        if (index >= 0) {
            // Remove if exists (toggle off)
            sites[hostname].safeElements.splice(index, 1);
        } else {
            // Add if new (toggle on)
            sites[hostname].safeElements.push({
                selector,
                description,
                createdAt: new Date().toISOString(),
                enabled: true
            });
        }

        await chrome.storage.local.set({ sites });
        return { success: true, isSafe: index < 0 };
    }

    async function getColorHistory() {
        const result = await chrome.storage.local.get(['colorHistory']);
        return result.colorHistory || [];
    }

    async function saveColor(color) {
        const result = await chrome.storage.local.get(['colorHistory']);
        let history = result.colorHistory || [];

        // Add to front, remove duplicates, limit to 50
        history = history.filter(c => c.hex !== color.hex);
        history.unshift(color);
        history = history.slice(0, 50);

        await chrome.storage.local.set({ colorHistory: history });
        return { success: true };
    }
