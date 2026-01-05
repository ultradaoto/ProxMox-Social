/**
 * Background Service Worker
 * Manages WebSocket connection to Python OSP
 */

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

        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
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

    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, {
                action: 'OSP_MESSAGE', // Wrap in action to distinguish
                ospType: type,
                payload: payload
            }).catch(() => { });
        }
    });

    if (type === 'open_url') {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                chrome.tabs.update(tabs[0].id, { url: payload.url });
            } else {
                chrome.tabs.create({ url: payload.url });
            }
        });
    }
}

// Intercept messages from Content Script or Popup intended for OSP or Status Checks
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'GET_STATUS') {
        sendResponse({ connected: socket && socket.readyState === WebSocket.OPEN });
        return true;
    }
    if (message.target === 'background' || message.action === 'OSP_SEND') {
        sendToOSP(message.type, message.payload);

        // If it's a recording command, also forward to current tab immediately
        // so we don't depend on Python echoing it back yet.
        if (message.type === 'start_recording' || message.type === 'stop_recording') {
            chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                if (tabs[0]) {
                    chrome.tabs.sendMessage(tabs[0].id, {
                        action: 'OSP_MESSAGE',
                        ospType: message.type,
                        payload: message.payload
                    }).catch(() => { });
                }
            });
        }
        return false;
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
