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
}

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

/* =============================================================================
   OSP LOGIC (WebSocket Client)
   ============================================================================= */

let socket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 100;
const WS_URL = 'ws://localhost:8765';

function connectToOSP() {
    console.log('[OSP] Connecting...');
    try {
        socket = new WebSocket(WS_URL);
    } catch (e) {
        console.error('[OSP] Connection failed:', e);
        scheduleReconnect();
        return;
    }
    
    socket.onopen = () => {
        console.log('[OSP] Connected');
        reconnectAttempts = 0;
        sendToOSP('extension_ready', { timestamp: Date.now() });
        
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                sendToOSP('extension_ready', { tab_url: tabs[0].url, tab_title: tabs[0].title });
            }
        });
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('[OSP] Rx:', data);
        handleOSPMessage(data);
    };
    
    socket.onclose = () => {
        console.log('[OSP] Disconnected');
        socket = null;
        scheduleReconnect();
    };
    
    socket.onerror = (error) => {
        console.error('[OSP] Error:', error);
    };
}

function scheduleReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        setTimeout(connectToOSP, 3000);
    }
}

function sendToOSP(type, payload = {}) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type, payload }));
    }
}

function handleOSPMessage(data) {
    const { type, payload } = data;
    
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
        if (tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, { 
                action: 'OSP_MESSAGE', // Wrap in action to distinguish
                ospType: type,
                payload: payload 
            }).catch(() => {});
        }
    });
    
    if (type === 'open_url') {
        chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.update(tabs[0].id, { url: payload.url });
            } else {
                chrome.tabs.create({ url: payload.url });
            }
        });
    }
}

// Intercept messages from Content Script intended for OSP
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target === 'background' || message.action === 'OSP_SEND') {
        sendToOSP(message.type, message.payload);
    }
    // Don't return true unless we sendResponse asynchronously, which we don't here
});

// Tab Updates for OSP
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        let platform = 'unknown';
        if (tab.url.includes('skool.com')) platform = 'skool';
        else if (tab.url.includes('instagram.com')) platform = 'instagram';
        else if (tab.url.includes('facebook.com')) platform = 'facebook';
        else if (tab.url.includes('tiktok.com')) platform = 'tiktok';
        else if (tab.url.includes('linkedin.com')) platform = 'linkedin';
        
        sendToOSP('page_loaded', {
            url: tab.url,
            title: tab.title,
            platform: platform
        });
    }
});

// Init OSP
connectToOSP();

