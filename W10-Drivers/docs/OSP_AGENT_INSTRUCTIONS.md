# OSP GUI: Agent Access Instructions

This document outlines how an automated agent (Antigravity/Ubuntu Controller) should access and run the **One-Click Social Poster (OSP)** on the Windows 10 VM.

## 1. Application Location
*   **Script Path**: `C:\ProxMox-Social\W10-Drivers\SocialWorker\osp_gui.py`
*   **Working Directory**: `C:\ProxMox-Social\W10-Drivers\SocialWorker`

## 2. Prerequisites
Ensure the Windows environment has the necessary Python dependencies installed.

```powershell
pip install -r C:\ProxMox-Social\W10-Drivers\SocialWorker\requirements.txt
```

**Key Dependencies:**
*   `PyQt6` (GUI)
*   `websockets` (Chrome Interaction)
*   `pypaperclip` (Clipboard)
*   `Pillow` (Image processing)

## 3. Launching the Application
The application **MUST** be launched from its working directory to correctly load local resources and the `.env` file.

**PowerShell Command:**
```powershell
Start-Process python -ArgumentList "osp_gui.py" -WorkingDirectory "C:\ProxMox-Social\W10-Drivers\SocialWorker"
```

## 4. Verification
*   **Process Name**: `python` (running `osp_gui.py`)
*   **Window Title**: "OSP Queue"
*   **Docking**: The window automatically docks to the **Right 15%** of the screen.

## 5. Interaction (Chrome)
The OSP GUI works in tandem with the **Element Blocker Extension** (which contains the merged OSP WebSocket Client).

1.  **Launch OSP**: Run the command above.
2.  **Open Chrome**: Ensure the extension is loaded.
3.  **Status Check**: The top-left label in the OSP GUI should turn **Green ("● Connected")**.
4.  **Flow**:
    *   The Agent should execute clicks on the **Manual Actions** buttons in the OSP GUI (via VNC/Mouse).
    *   **Open URL**: triggers navigation in Chrome.
    *   **Copy Title/Body**: Copies text to clipboard.
    *   **Copy Image**: Copies image path/data.
    *   **Chrome Highlights**: The Extension will highlight input fields in the browser to guide the Agent on where to Paste/Click.

## 6. Troubleshooting
*   **"Disconnected" Status**: Reload the Chrome tab or restart the Extension in `chrome://extensions/`.
*   **Window not visible**: Check if it's minimized or if the process crashed. Run the launch command again (it enforces docking on startup).
