/**
 * Background Service Worker
 * Manages WebSocket connection to Python OSP
 */

let socket = null;
let reconnectAttempts = 0;
let isRecording = false;
let reapplyTimerId = null;  // Track the re-apply timer so we can cancel it
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
        console.log('[OSP] Tx:', { type, payload });
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
        sendResponse({
            connected: socket && socket.readyState === WebSocket.OPEN,
            recording: isRecording
        });
        return true;
    }
    if (message.target === 'background' || message.action === 'OSP_SEND') {
        // Log who sent this
        console.log(`[OSP] Action: ${message.type} | From: ${sender.tab ? 'Content Script' : 'Popup'}`);
        sendToOSP(message.type, message.payload);

        // Handle Recording State
        if (message.type === 'start_recording') {
            isRecording = true;
            broadcastRecordingState(true);
        } else if (message.type === 'stop_recording') {
            isRecording = false;
            // Cancel any pending re-apply timer
            if (reapplyTimerId) {
                clearTimeout(reapplyTimerId);
                reapplyTimerId = null;
                console.log('[OSP] Cancelled pending re-apply timer');
            }
            broadcastRecordingState(false);
        }
        return false;
    }
    // Don't return true unless we sendResponse asynchronously, which we don't here
});

function broadcastRecordingState(enabled) {
    const action = enabled ? 'start_recording' : 'stop_recording';
    // Send to ALL tabs to ensure content scripts receive it immediately
    chrome.tabs.query({}, (tabs) => {
        for (const tab of tabs) {
            // Skip chrome:// and edge:// internal pages where content scripts can't run
            if (tab.id && tab.url && !tab.url.startsWith('chrome://') && !tab.url.startsWith('edge://')) {
                chrome.tabs.sendMessage(tab.id, {
                    action: 'OSP_MESSAGE',
                    ospType: action,
                    payload: {}
                }).catch(() => { });
            }
        }
    });
}

// Tab Updates for OSP
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.active) {
        // Skip internal browser pages - don't send page_loaded for these
        if (tab.url.startsWith('chrome://') || tab.url.startsWith('edge://') || tab.url.startsWith('about:')) {
            console.log('[OSP] Skipping internal page:', tab.url);
            return;
        }

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

        // Re-apply recording mode if active (Content Script resets on reload)
        if (isRecording) {
            // Clear any existing timer first
            if (reapplyTimerId) {
                clearTimeout(reapplyTimerId);
            }
            reapplyTimerId = setTimeout(() => {
                reapplyTimerId = null;
                // Double-check we're still recording before sending
                if (!isRecording) {
                    console.log('[OSP] Recording stopped before re-apply timer fired, skipping');
                    return;
                }
                chrome.tabs.sendMessage(tabId, {
                    action: 'OSP_MESSAGE',
                    ospType: 'start_recording',
                    payload: { reapply: true }  // Mark as re-apply for debugging
                }).catch(() => { });
            }, 500); // Small delay to ensure script is ready
        }
    }
});

// Init OSP
connectToOSP();
