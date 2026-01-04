/**
 * Popup Script
 * Handles popup UI for Focus Mode
 */

document.addEventListener('DOMContentLoaded', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const url = new URL(tab.url);
    const hostname = url.hostname;

    document.getElementById('current-site').textContent = hostname;

    loadSafeElements(hostname);

    // Check Mode
    chrome.tabs.sendMessage(tab.id, { action: 'getMode' }, (response) => {
        // Ignore errors if content script not loaded
        if (chrome.runtime.lastError) return;

        const mode = response?.mode || 'NONE';
        updateButtonStates(mode);
    });

    const focusBtn = document.getElementById('focus-mode-btn');
    const editBtn = document.getElementById('edit-mode-btn');

    focusBtn.onclick = () => {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleFocusMode' });
        window.close();
    };

    editBtn.onclick = () => {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleEditMode' });
        window.close();
    };

    document.getElementById('color-mode-btn').onclick = () => {
        chrome.tabs.sendMessage(tab.id, { action: 'toggleColorPickerMode' });
        window.close();
    };

    document.getElementById('options-link').onclick = (e) => {
        e.preventDefault();
        chrome.runtime.openOptionsPage();
    };
});

function updateButtonStates(mode) {
    const focusBtn = document.getElementById('focus-mode-btn');
    const editBtn = document.getElementById('edit-mode-btn');

    // Reset defaults (could put this in HTML)
    focusBtn.innerHTML = '▶️ Start Focus';
    focusBtn.classList.remove('btn-stop');

    editBtn.innerHTML = '✏️ Edit Safe Zones';
    editBtn.classList.remove('btn-stop');

    if (mode === 'FOCUS') {
        focusBtn.innerHTML = '⏹ Stop Focus';
        focusBtn.classList.add('btn-stop');
        // Disable edit button visually?
        editBtn.style.opacity = '0.5';
    } else if (mode === 'EDIT') {
        editBtn.innerHTML = '✅ Done Editing'; // Or Stop
        editBtn.classList.add('btn-stop'); // Maybe green for done?

        focusBtn.style.opacity = '0.5';
    }
}

async function loadSafeElements(hostname) {
    const response = await chrome.runtime.sendMessage({
        action: 'getSafeElements',
        hostname
    });

    const container = document.getElementById('safe-list');

    if (!response || response.length === 0) {
        container.innerHTML = '<p class="empty-state">No safe zones yet. Use "Edit Safe Zones" to add some!</p>';
        return;
    }

    container.innerHTML = response.map(item => `
    <div class="blocked-item">
      <span class="blocked-item-text" title="${item.selector}">
        ${item.description || item.selector}
      </span>
      <button class="blocked-item-restore" data-selector="${encodeURIComponent(item.selector)}">
        Remove
      </button>
    </div>
  `).join('');

    container.querySelectorAll('.blocked-item-restore').forEach(btn => {
        btn.onclick = async () => {
            const selector = decodeURIComponent(btn.dataset.selector);
            await chrome.runtime.sendMessage({
                action: 'toggleSafeElement',
                hostname,
                selector
            });
            loadSafeElements(hostname);
        };
    });
}
