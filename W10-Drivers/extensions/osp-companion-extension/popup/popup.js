document.addEventListener('DOMContentLoaded', () => {
    const btnEditor = document.getElementById('btn-toggle-editor');
    const btnClear = document.getElementById('btn-clear-rules');
    const logContainer = document.getElementById('log-container');
    const platformDisplay = document.getElementById('platform-name');
    const ruleCountDisplay = document.getElementById('rule-count');

    let isEditorActive = false;

    // init status
    updateUI();

    // Listen for button clicks
    btnEditor.addEventListener('click', () => {
        isEditorActive = !isEditorActive;
        sendMessageToContent({ type: 'toggle_editor', active: isEditorActive });
        btnEditor.textContent = isEditorActive ? 'Disable Visual Editor' : 'Enable Visual Editor';
        addLog(isEditorActive ? 'Editor enabled. Click elements to tag.' : 'Editor disabled.');
    });

    btnClear.addEventListener('click', () => {
        if (confirm('Are you sure you want to delete ALL saved highlighting rules?')) {
            chrome.runtime.sendMessage({ action: 'CLEAR_RULES' });
            chrome.storage.local.remove('osp_rules', () => {
                addLog('Rules cleared from storage.', 'warning');
                updateUI();
                // Notify content to reload
                sendMessageToContent({ type: 'reload_rules' });
            });
        }
    });

    function sendMessageToContent(message) {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                const tabId = tabs[0].id;
                // Check if we can message this tab
                if (tabs[0].url.startsWith('chrome://') || tabs[0].url.startsWith('edge://')) {
                    addLog('Cannot use editor on internal pages.', 'error');
                    return;
                }

                chrome.tabs.sendMessage(tabId, message).catch(err => {
                    // Suppress "Receiving end does not exist" which happens if content script isn't ready
                    if (err.message.includes('Receiving end does not exist')) {
                        addLog('Page not ready or unsupported. Try reloading the page.', 'error');
                    } else {
                        addLog('Error: ' + err.message, 'error');
                    }
                });
            }
        });
    }

    function addLog(msg, type = 'system') {
        const div = document.createElement('div');
        div.className = `log-entry ${type}`;
        div.textContent = `> ${msg}`;
        logContainer.appendChild(div);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    function updateUI() {
        // get status from content script or storage
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                if (tabs[0].url) {
                    try {
                        const url = new URL(tabs[0].url);
                        platformDisplay.textContent = url.hostname;
                    } catch (e) {
                        platformDisplay.textContent = "Unknown";
                    }
                }

                // Check rule count
                chrome.storage.local.get(['osp_rules'], (result) => {
                    const rules = result.osp_rules || [];
                    ruleCountDisplay.textContent = rules.length;
                });
            }
        });
    }

    // Ping for status updates occasionally
    setInterval(updateUI, 2000);
});
