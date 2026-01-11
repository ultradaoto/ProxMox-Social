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

    document.getElementById('btn-clear-rules').addEventListener('click', () => {
        if (confirm('Are you sure you want to delete ALL saved rules? This cannot be undone.')) {
            chrome.storage.local.set({ osp_rules: [] }, () => {
                updateRuleCount();
                addLog('Rules cleared.', 'success');
                sendMessageToContent({ type: 'reload_rules' }); // Notify content script
            });
        }
    });

    document.getElementById('btn-export-rules').addEventListener('click', () => {
        chrome.storage.local.get(['osp_rules'], (result) => {
            const rules = result.osp_rules || [];
            // Rules in content.js are an array, saving as array is better for json
            const json = JSON.stringify(rules, null, 2);
            navigator.clipboard.writeText(json).then(() => {
                addLog('Rules copied to clipboard! Paste into rules.json.', 'success');
            }).catch(err => {
                addLog('Failed to copy: ' + err, 'error');
            });
        });
    });

    function updateRuleCount() {
        chrome.storage.local.get(['osp_rules'], (result) => {
            const rules = result.osp_rules || [];
            const count = Array.isArray(rules) ? rules.length : Object.keys(rules).length;
            document.getElementById('rule-count').textContent = count;
        });
    }

    function sendMessageToContent(message) {
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                const tabId = tabs[0].id;
                // Check if we can message this tab
                if (tabs[0].url.startsWith('chrome://') || tabs[0].url.startsWith('edge://')) {
                    addLog('Cannot use editor on internal pages.', 'error');
                    return;
                }

                // PING CHECK
                chrome.tabs.sendMessage(tabId, { type: 'PING' })
                    .then(() => {
                        // Connection OK, send actual message
                        return chrome.tabs.sendMessage(tabId, message);
                    })
                    .catch(err => {
                        // If Ping fails, content script is likely not ready
                        if (err.message.includes('Receiving end does not exist')) {
                            addLog('Extension not ready. Please reload the page.', 'error');
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
