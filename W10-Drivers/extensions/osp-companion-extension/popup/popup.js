document.addEventListener('DOMContentLoaded', () => {
    const statusIndicator = document.getElementById('status-indicator');
    const connectionStatus = document.getElementById('connection-status');
    const btnStart = document.getElementById('btn-start-recording');
    const btnStop = document.getElementById('btn-stop-recording');
    const logContainer = document.getElementById('log-container');

    // Poll for status
    function checkStatus() {
        chrome.runtime.sendMessage({ action: 'GET_STATUS' }, (response) => {
            if (chrome.runtime.lastError) {
                updateStatus(false);
                return;
            }
            if (response) {
                updateStatus(response.connected);
                // Also update recording state if we had it
            }
        });
    }

    function updateStatus(isConnected) {
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
