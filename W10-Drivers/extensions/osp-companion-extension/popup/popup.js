document.addEventListener('DOMContentLoaded', () => {
    const statusIndicator = document.getElementById('status-indicator');
    const connectionStatus = document.getElementById('connection-status');
    const btnStart = document.getElementById('btn-start-recording');
    const btnStop = document.getElementById('btn-stop-recording');
    const logContainer = document.getElementById('log-container');

    let currentTabUrl = '';

    // Poll for status
    function checkStatus() {
        chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (response) => {
            if (chrome.runtime.lastError) {
                updateStatus(false);
                return;
            }
            if (response) {
                updateStatus(response.connected, response.recording);
            }
        });

        // Also check current tab URL
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
            if (tabs[0]) {
                currentTabUrl = tabs[0].url || '';
                updateStepDisplay();
            }
        });
    }

    function isInternalPage(url) {
        return url.startsWith('chrome://') ||
            url.startsWith('edge://') ||
            url.startsWith('about:') ||
            url.startsWith('chrome-extension://');
    }

    function updateStepDisplay() {
        const stepEl = document.getElementById('step-display');
        if (stepEl && isInternalPage(currentTabUrl)) {
            stepEl.textContent = '⚠️ Internal page';
            stepEl.style.color = '#eab308';
        }
    }

    function updateStatus(isConnected, isRecording) {
        if (isConnected) {
            statusIndicator.classList.add('connected');
            statusIndicator.classList.remove('disconnected');
            statusIndicator.title = 'Connected';
            connectionStatus.textContent = 'Connected';
            connectionStatus.style.color = '#10b981';
            btnStart.disabled = false;
        } else {
            statusIndicator.classList.remove('connected');
            statusIndicator.classList.add('disconnected');
            statusIndicator.title = 'Disconnected';
            connectionStatus.textContent = 'Disconnected';
            connectionStatus.style.color = '#ef4444';
            btnStart.disabled = true;
        }

        // Sync Recording Buttons
        if (isRecording) {
            btnStart.classList.add('hidden');
            btnStop.classList.remove('hidden');
        } else {
            btnStop.classList.add('hidden');
            btnStart.classList.remove('hidden');
        }
    }

    function addLog(msg, type = 'system') {
        const div = document.createElement('div');
        div.className = `log-entry ${type}`;
        div.textContent = `> ${msg}`;
        logContainer.appendChild(div);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Button Listeners
    btnStart.addEventListener('click', () => {
        // Warn if on internal page but still allow recording
        // (recording will work once user navigates to a real site)
        if (isInternalPage(currentTabUrl)) {
            addLog('Note: On internal page. Recording will start when you navigate to a website.', 'warning');
        }

        chrome.runtime.sendMessage({ action: 'OSP_SEND', type: 'start_recording', payload: {} });
        addLog('Recording started...', 'success');
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');
    });

    btnStop.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'OSP_SEND', type: 'stop_recording', payload: {} });
        addLog('Recording stopped.', 'system');
        btnStop.classList.add('hidden');
        btnStart.classList.remove('hidden');
    });

    // Initial check
    checkStatus();
    // Poll every 2s
    setInterval(checkStatus, 2000);
});

