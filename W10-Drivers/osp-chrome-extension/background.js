/**
 * Background Service Worker
 * Manages WebSocket connection to Python OSP
 */

let socket = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 100; // Keep trying essentially forever
const WS_URL = 'ws://localhost:8765';

// Connect to Python OSP
function connectToOSP() {
    console.log('Connecting to OSP...');

    try {
        socket = new WebSocket(WS_URL);
    } catch (e) {
        console.error("Connection failed:", e);
        scheduleReconnect();
        return;
    }

    socket.onopen = () => {
        console.log('Connected to Python OSP');
        reconnectAttempts = 0;

        // Notify OSP we're ready
        sendToOSP('extension_ready', {
            timestamp: Date.now()
        });

        // Get current tab info
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                sendToOSP('extension_ready', {
                    tab_url: tabs[0].url,
                    tab_title: tabs[0].title
                });
            }
        });
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('From OSP:', data);
        handleOSPMessage(data);
    };

    socket.onclose = () => {
        console.log('Disconnected from OSP');
        socket = null;
        scheduleReconnect();
    };

    socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        // creating socket error triggers onclose, so we handle reconnect there
    };
}

function scheduleReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        console.log(`Reconnecting in 3s (attempt ${reconnectAttempts})...`);
        setTimeout(connectToOSP, 3000);
    }
}

// Send message to Python OSP
function sendToOSP(type, payload = {}) {
    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type, payload }));
    } else {
        console.warn('Cannot send - WebSocket not connected');
    }
}

// Handle messages from Python OSP
function handleOSPMessage(data) {
    const { type, payload } = data;

    // Forward to content script in active tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
            chrome.tabs.sendMessage(tabs[0].id, { type, payload }).catch(err => {
                console.log("Could not send to content script (probably sleeping/restricted page):", err);
            });
        }
    });

    // Handle URL opening specially
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

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.target === 'background') {
        sendToOSP(message.type, message.payload);
    }
    return true;
});

// Listen for tab updates
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        // Detect platform from URL
        const platform = detectPlatform(tab.url);

        sendToOSP('page_loaded', {
            url: tab.url,
            title: tab.title,
            platform: platform
        });
    }
});

// Detect platform from URL
function detectPlatform(url) {
    if (!url) return 'unknown';
    if (url.includes('skool.com')) return 'skool';
    if (url.includes('instagram.com')) return 'instagram';
    if (url.includes('facebook.com')) return 'facebook';
    if (url.includes('tiktok.com')) return 'tiktok';
    if (url.includes('twitter.com') || url.includes('x.com')) return 'twitter';
    if (url.includes('linkedin.com')) return 'linkedin';
    return 'unknown';
}

// Start connection on load
connectToOSP();
