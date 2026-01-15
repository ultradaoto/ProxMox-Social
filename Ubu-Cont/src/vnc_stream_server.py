#!/usr/bin/env python3
"""
VNC Live Stream Server (Interactive + Recording)
- Serves live MJPEG stream
- Interactive: Captures clicks in browser and sends to Windows via HID
- Recording Mode: Capture clicks with timestamps for workflow automation
- Playback Mode: Replay recorded workflows
- Uses Multiprocessing for VNC capture
"""

import sys
import os
import time
import io
import logging
import multiprocessing
import json
import numpy as np
from datetime import datetime
from PIL import Image
from flask import Flask, Response, render_template_string, jsonify, request

# Ensure src is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from input_controller import InputController

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("VNCStreamer")
logger.setLevel(logging.INFO)

app = Flask(__name__)

# Configuration
VNC_HOST = "192.168.100.101"
VNC_PORT = 5900
VNC_PASSWORD = "Pa$$word"
TARGET_FPS = 10
TARGET_WIDTH = 1600
TARGET_HEIGHT = 1200
SHARED_FRAME_PATH = "/dev/shm/vnc_latest.png" if os.path.exists("/dev/shm") else "/tmp/vnc_latest.png"

# Recordings directory
RECORDINGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "recordings")
os.makedirs(RECORDINGS_DIR, exist_ok=True)

# Input Controller (Global)
input_ctrl = None

def get_input_controller():
    global input_ctrl
    if input_ctrl is None:
        try:
            input_ctrl = InputController()
            input_ctrl.connect()
            logger.info("InputController connected.")
        except Exception as e:
            logger.error(f"Failed to connect InputController: {e}")
    return input_ctrl

def capture_process_func():
    """Independent process to capture VNC frames."""
    from vncdotool import api as vnc_api
    
    print(f"[CaptureProcess] Connecting to {VNC_HOST}:{VNC_PORT}...")
    client = None
    
    while True:
        try:
            if client is None:
                client = vnc_api.connect(f"{VNC_HOST}::{VNC_PORT}", password=VNC_PASSWORD)
                print(f"[CaptureProcess] Connected to VNC.")
            
            # Refresh
            client.refreshScreen()
            
            if client.screen:
                # Save to shared path (atomic-ish)
                temp_path = SHARED_FRAME_PATH + ".tmp"
                client.screen.save(temp_path, format='PNG')
                os.replace(temp_path, SHARED_FRAME_PATH)
                
            time.sleep(1.0 / TARGET_FPS)
            
        except Exception as e:
            print(f"[CaptureProcess] Error: {e}")
            if client:
                try: client.disconnect() 
                except: pass
            client = None
            time.sleep(5)

def get_latest_frame():
    if not os.path.exists(SHARED_FRAME_PATH):
        return None
    try:
        for _ in range(3):
            try:
                with Image.open(SHARED_FRAME_PATH) as img:
                    img.load()
                    return img
            except OSError:
                time.sleep(0.01)
    except Exception:
        return None
    return None

def generate_mjpeg():
    while True:
        img = get_latest_frame()
        if img is None:
            time.sleep(0.1)
            continue
            
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        frame_bytes = buf.getvalue()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(1.0 / TARGET_FPS)

# HTML with Interactive Click & Keyboard Handler + Recording Mode
VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Windows VNC Live (Interactive + Recording)</title>
    <style>
        body { 
            margin: 0; 
            background: #1a1a2e; 
            display: flex; 
            flex-direction: row;
            padding: 20px;
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #dfe6e9;
            min-height: 100vh;
        }
        .main-panel {
            display: flex;
            flex-direction: column;
            align-items: center;
            flex: 1;
        }
        .side-panel {
            width: 320px;
            background: #16213e;
            border-radius: 8px;
            padding: 15px;
            margin-left: 20px;
            max-height: 90vh;
            overflow-y: auto;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; font-weight: 300; }
        h2 { color: #00d4ff; margin: 0 0 15px 0; font-size: 1.1em; font-weight: 400; }
        .status { color: #00ff88; margin-bottom: 10px; font-size: 0.9em; }
        .container {
            position: relative;
            box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid #00d4ff;
            outline: none;
        }
        .container:focus {
            border-color: #00ff88;
            box-shadow: 0 0 40px rgba(0, 255, 136, 0.3);
        }
        .container.recording {
            border-color: #ff4757 !important;
            box-shadow: 0 0 40px rgba(255, 71, 87, 0.5) !important;
            animation: pulse-red 1s infinite;
        }
        @keyframes pulse-red {
            0%, 100% { box-shadow: 0 0 40px rgba(255, 71, 87, 0.5); }
            50% { box-shadow: 0 0 60px rgba(255, 71, 87, 0.8); }
        }
        #stream { 
            display: block;
            max-width: 100%;
            max-height: 80vh;
            cursor: crosshair; 
        }
        .controls {
            margin-top: 15px;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            justify-content: center;
        }
        button {
            background: #0984e3;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            color: white;
            transition: background 0.2s;
            font-size: 0.9em;
        }
        button:hover { background: #74b9ff; }
        button:disabled { background: #636e72; cursor: not-allowed; }
        button.record-btn { background: #ff4757; }
        button.record-btn:hover { background: #ff6b7a; }
        button.stop-btn { background: #ffa502; }
        button.stop-btn:hover { background: #ffb830; }
        button.play-btn { background: #2ed573; }
        button.play-btn:hover { background: #7bed9f; }
        .info {
            margin-top: 10px;
            font-family: monospace;
            color: #aaa;
        }
        .instructions {
            margin-top: 5px;
            font-size: 0.8em;
            color: #636e72;
        }
        .recording-status {
            background: #ff4757;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: 600;
            display: none;
            animation: blink 1s infinite;
        }
        .recording-status.active { display: inline-block; }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .section {
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid #2d3436;
        }
        .section:last-child { border-bottom: none; }
        select, input[type="text"], input[type="number"] {
            width: 100%;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #2d3436;
            background: #0d1b2a;
            color: #dfe6e9;
            margin-bottom: 10px;
        }
        .action-list {
            max-height: 400px;
            overflow-y: auto;
            background: #0d1b2a;
            border-radius: 4px;
            padding: 8px;
            font-family: monospace;
            font-size: 0.8em;
        }
        .action-item {
            padding: 6px 8px;
            margin: 4px 0;
            background: #1a1a2e;
            border-radius: 4px;
            border-left: 3px solid #0984e3;
            cursor: pointer;
            transition: all 0.2s;
        }
        .action-item:hover { background: #2d3436; }
        .action-item.selected { 
            border-left-color: #00ff88; 
            background: #1e3a5f;
        }

        .action-item .action-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        .action-item .action-num { 
            color: #636e72; 
            font-size: 0.75em;
            margin-right: 8px;
        }
        .action-item .type { color: #00d4ff; font-weight: bold; }
        .action-item .coords { color: #00ff88; }
        .action-item .time { color: #ffa502; font-size: 0.85em; }
        .action-item .desc { 
            color: #b2bec3; 
            font-size: 0.8em; 
            margin-top: 2px;
            font-style: italic;
        }
        .action-item .action-btns {
            display: flex;
            gap: 4px;
            margin-top: 6px;
        }
        .action-item .action-btns button {
            padding: 2px 6px;
            font-size: 0.75em;
            border: none;
            border-radius: 3px;
            cursor: pointer;
        }
        .action-item .edit-btn { background: #0984e3; color: white; }
        .action-item .up-btn, .action-item .down-btn { background: #636e72; color: white; }
        .action-item .dup-btn { background: #6c5ce7; color: white; }
        .action-item .del-btn { background: #d63031; color: white; }
        .action-item .action-btns button:hover { opacity: 0.8; }
        .btn-row {
            display: flex;
            gap: 8px;
            margin-bottom: 10px;
        }
        .btn-row button { flex: 1; }
        label {
            display: block;
            margin-bottom: 5px;
            color: #b2bec3;
            font-size: 0.85em;
        }
        .stats {
            font-size: 0.85em;
            color: #b2bec3;
            margin-top: 10px;
        }
        .loaded-file {
            background: #2d3436;
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 10px;
            font-size: 0.85em;
        }
        .loaded-file .filename { color: #00d4ff; font-weight: bold; }
        .loaded-file .modified { color: #ffa502; }
        .edit-modal {
            display: none;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            border: 2px solid #00d4ff;
            z-index: 1000;
            min-width: 350px;
            box-shadow: 0 0 50px rgba(0,0,0,0.8);
        }
        .edit-modal.active { display: block; }
        .edit-modal h3 { color: #00d4ff; margin: 0 0 15px 0; }
        .edit-modal .field { margin-bottom: 12px; }
        .edit-modal .field label { color: #dfe6e9; margin-bottom: 4px; }
        .edit-modal .field input, .edit-modal .field select {
            width: 100%;
            padding: 8px;
            border-radius: 4px;
            border: 1px solid #2d3436;
            background: #0d1b2a;
            color: #dfe6e9;
            box-sizing: border-box;
        }
        .edit-modal .modal-btns { display: flex; gap: 10px; margin-top: 15px; }
        .edit-modal .modal-btns button { flex: 1; padding: 10px; }
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.7);
            z-index: 999;
        }
        .modal-overlay.active { display: block; }
        .insert-marker {
            height: 3px;
            background: #00ff88;
            margin: 2px 0;
            border-radius: 2px;
            display: none;
        }
        .insert-marker.active { display: block; animation: pulse-green 1s infinite; }
        @keyframes pulse-green {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .mode-indicator {
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: bold;
            margin-bottom: 10px;
            text-align: center;
        }
        .mode-indicator.edit-mode { background: #0984e3; color: white; }
        .mode-indicator.record-mode { background: #ff4757; color: white; }
        .mode-indicator.insert-mode { background: #00ff88; color: #1a1a2e; }
    </style>
</head>
<body>
    <div class="main-panel">
        <h1>Windows 10 Live Control</h1>
        <div class="status">
            Streaming from {{ vnc_host }} | 
            <span class="recording-status" id="rec-status">🔴 RECORDING</span>
        </div>
        
        <div class="container" tabindex="0" id="view-container">
            <img id="stream" src="/stream" alt="VNC Stream">
        </div>

        <div class="info" id="coords">Click inside to type / Move mouse</div>
        <div class="instructions">Focus image to enable keyboard | Recording captures clicks with timing</div>

        <div class="controls">
            <button onclick="sendHotkey(['ctrl', 'alt', 'delete'])" style="background: #d63031;">Ctrl+Alt+Del</button>
            <button onclick="location.reload()">Reconnect</button>
        </div>
    </div>
    
    <div class="side-panel">
        <div class="section">
            <h2>📂 Workflow Editor</h2>
            
            <div class="loaded-file" id="loadedFileInfo" style="display: none;">
                <div>Editing: <span class="filename" id="currentFilename">--</span></div>
                <div class="modified" id="modifiedIndicator" style="display: none;">⚠️ Unsaved changes</div>
            </div>
            
            <label>Load Recording</label>
            <select id="savedRecordings" onchange="loadSelectedRecording()">
                <option value="">-- Select a recording to edit --</option>
            </select>
            
            <label style="margin-top: 10px;">Platform</label>
            <select id="platform">
                <option value="instagram">Instagram</option>
                <option value="instagram_video">Instagram (Video)</option>
                <option value="skool">Skool</option>
                <option value="facebook">Facebook</option>
                <option value="tiktok">TikTok</option>
                <option value="custom">Custom</option>
            </select>
            
            <div class="btn-row" style="margin-top: 10px;">
                <button id="saveBtn" onclick="saveRecording()" disabled title="Overwrite current file">💾 Save</button>
                <button id="saveAsBtn" onclick="saveRecordingAs()" disabled title="Save as new file">📄 Save As</button>
            </div>
            
            <div class="btn-row">
                <button class="play-btn" id="playBtn" onclick="playRecording()" disabled>▶️ Test Playback</button>
            </div>
            
            <div class="btn-row">
                <button onclick="newRecording()" style="background: #636e72;">📝 New Empty</button>
                <button onclick="refreshRecordings()">🔄 Refresh</button>
            </div>
        </div>
        
        <div class="section">
            <h2>🎯 Capture Mode</h2>
            <div class="mode-indicator" id="modeIndicator">EDIT MODE - Click actions to modify</div>
            
            <div class="btn-row">
                <button class="record-btn" id="startRecBtn" onclick="startRecording()">🔴 Record New</button>
                <button class="stop-btn" id="stopRecBtn" onclick="stopRecording()" disabled>⏹️ Stop</button>
            </div>
            
            <div class="btn-row">
                <button id="insertModeBtn" onclick="toggleInsertMode()" style="background: #00b894;">📍 Insert At Position</button>
            </div>
            
            <div class="stats" id="recStats">Actions: 0</div>
        </div>
        
        <div class="section">
            <h2>📋 Actions <span id="actionCount">(0)</span></h2>
            <div class="action-list" id="actionList">
                <div style="color: #636e72; text-align: center; padding: 20px;">
                    Load a recording or start fresh
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>➕ Add Action</h2>
            <label>Action Type</label>
            <select id="manualActionType" onchange="updateManualActionFields()">
                <option value="click">Click at position</option>
                <option value="wait">Wait (delay)</option>
                <option value="key">Press Key</option>
                <option value="paste">Paste (Ctrl+V)</option>
                <option value="type">Type Text</option>
            </select>
            <div id="manualActionFields">
                <div class="btn-row">
                    <input type="number" id="manualX" placeholder="X" style="width: 45%;">
                    <input type="number" id="manualY" placeholder="Y" style="width: 45%;">
                </div>
            </div>
            <input type="number" id="manualDelay" placeholder="Delay before (ms)" value="500">
            <input type="text" id="manualDesc" placeholder="Description (optional)">
            <button onclick="addManualAction()" style="width: 100%;">Add to End</button>
        </div>
    </div>
    
    <!-- Edit Action Modal -->
    <div class="modal-overlay" id="modalOverlay" onclick="closeEditModal()"></div>
    <div class="edit-modal" id="editModal">
        <h3>✏️ Edit Action #<span id="editActionNum">0</span></h3>
        <div class="field">
            <label>Type</label>
            <select id="editType" onchange="updateEditFields()">
                <option value="click">Click</option>
                <option value="right_click">Right Click</option>
                <option value="double_click">Double Click</option>
                <option value="wait">Wait</option>
                <option value="key">Key Press</option>
                <option value="paste">Paste</option>
                <option value="type">Type Text</option>
                <option value="scroll">Scroll</option>
            </select>
        </div>
        <div class="field" id="editCoordsField">
            <label>Coordinates</label>
            <div class="btn-row">
                <input type="number" id="editX" placeholder="X">
                <input type="number" id="editY" placeholder="Y">
            </div>
            <button onclick="captureCurrentPosition()" style="width: 100%; margin-top: 5px; background: #00b894;">
                📍 Capture Current Mouse Position
            </button>
        </div>
        <div class="field" id="editValueField" style="display: none;">
            <label>Value</label>
            <input type="text" id="editValue" placeholder="Value">
        </div>
        <div class="field">
            <label>Delay Before (ms)</label>
            <input type="number" id="editDelay" placeholder="Delay in ms">
        </div>
        <div class="field">
            <label>Description</label>
            <input type="text" id="editDesc" placeholder="What this action does">
        </div>
        <div class="modal-btns">
            <button onclick="closeEditModal()" style="background: #636e72;">Cancel</button>
            <button onclick="saveEditedAction()" style="background: #00b894;">Save Changes</button>
        </div>
    </div>

    <script>
        const TARGET_WIDTH = 1600;
        const TARGET_HEIGHT = 1200;
        const img = document.getElementById('stream');
        const container = document.getElementById('view-container');
        const info = document.getElementById('coords');
        
        // State
        let isRecording = false;
        let isInsertMode = false;
        let insertAtIndex = -1;
        let recordingStartTime = null;
        let lastActionTime = null;
        let recordedActions = [];
        let isPlayingBack = false;
        let currentFilename = null;
        let isModified = false;
        let editingActionIndex = -1;
        let lastMouseX = 0;
        let lastMouseY = 0;

        // UI Elements
        const recStatus = document.getElementById('rec-status');
        const startRecBtn = document.getElementById('startRecBtn');
        const stopRecBtn = document.getElementById('stopRecBtn');
        const playBtn = document.getElementById('playBtn');
        const saveBtn = document.getElementById('saveBtn');
        const saveAsBtn = document.getElementById('saveAsBtn');
        const actionList = document.getElementById('actionList');
        const recStats = document.getElementById('recStats');
        const modeIndicator = document.getElementById('modeIndicator');
        const loadedFileInfo = document.getElementById('loadedFileInfo');
        const currentFilenameEl = document.getElementById('currentFilename');
        const modifiedIndicator = document.getElementById('modifiedIndicator');
        const actionCount = document.getElementById('actionCount');

        function setModified(modified) {
            isModified = modified;
            modifiedIndicator.style.display = modified ? 'block' : 'none';
            saveBtn.disabled = !modified || !currentFilename;
            saveAsBtn.disabled = recordedActions.length === 0;
        }

        function updateMode() {
            if (isRecording) {
                modeIndicator.className = 'mode-indicator record-mode';
                modeIndicator.innerText = '🔴 RECORDING - Clicks are captured';
            } else if (isInsertMode) {
                modeIndicator.className = 'mode-indicator insert-mode';
                modeIndicator.innerText = `📍 INSERT MODE - Next click inserts at position ${insertAtIndex + 1}`;
            } else {
                modeIndicator.className = 'mode-indicator edit-mode';
                modeIndicator.innerText = 'EDIT MODE - Click actions to modify';
            }
        }

        function newRecording() {
            if (isModified && !confirm('Discard unsaved changes?')) return;
            recordedActions = [];
            currentFilename = null;
            isModified = false;
            loadedFileInfo.style.display = 'none';
            document.getElementById('savedRecordings').value = '';
            updateActionList();
            updateStats();
            playBtn.disabled = true;
            saveBtn.disabled = true;
            saveAsBtn.disabled = true;
            info.innerText = 'New empty recording';
        }

        function startRecording() {
            if (isModified && !confirm('This will clear current actions. Continue?')) return;
            
            isRecording = true;
            recordingStartTime = Date.now();
            lastActionTime = recordingStartTime;
            recordedActions = [];
            currentFilename = null;
            
            container.classList.add('recording');
            recStatus.classList.add('active');
            startRecBtn.disabled = true;
            stopRecBtn.disabled = false;
            playBtn.disabled = true;
            saveBtn.disabled = true;
            loadedFileInfo.style.display = 'none';
            
            updateActionList();
            updateStats();
            updateMode();
            info.innerText = 'Recording started - click to capture actions';
        }

        function stopRecording() {
            isRecording = false;
            container.classList.remove('recording');
            recStatus.classList.remove('active');
            startRecBtn.disabled = false;
            stopRecBtn.disabled = true;
            playBtn.disabled = recordedActions.length === 0;
            saveAsBtn.disabled = recordedActions.length === 0;
            setModified(recordedActions.length > 0);
            
            updateMode();
            info.innerText = `Recording stopped - ${recordedActions.length} actions captured`;
        }

        function toggleInsertMode() {
            isInsertMode = !isInsertMode;
            if (isInsertMode) {
                insertAtIndex = recordedActions.length; // Default to end
                document.getElementById('insertModeBtn').style.background = '#ff4757';
                document.getElementById('insertModeBtn').innerText = '❌ Cancel Insert';
            } else {
                insertAtIndex = -1;
                document.getElementById('insertModeBtn').style.background = '#00b894';
                document.getElementById('insertModeBtn').innerText = '📍 Insert At Position';
            }
            updateMode();
            updateActionList();
        }

        function setInsertPosition(idx) {
            if (!isInsertMode) return;
            insertAtIndex = idx;
            updateMode();
            updateActionList();
            info.innerText = `Insert position set to ${idx}. Click on VNC to insert action here.`;
        }

        function recordAction(action) {
            const now = Date.now();
            
            if (isRecording) {
                const delayBefore = now - lastActionTime;
                lastActionTime = now;
                action.delay_before_ms = delayBefore;
            } else if (isInsertMode) {
                action.delay_before_ms = 500; // Default delay for inserted actions
            } else {
                return; // Not in a capture mode
            }
            
            action.timestamp = new Date().toISOString();
            
            if (isInsertMode && insertAtIndex >= 0 && insertAtIndex <= recordedActions.length) {
                recordedActions.splice(insertAtIndex, 0, action);
                insertAtIndex++; // Move insert point forward
                info.innerText = `Inserted action at position ${insertAtIndex}`;
            } else {
                recordedActions.push(action);
            }
            
            setModified(true);
            updateActionList();
            updateStats();
        }

        function updateStats() {
            recStats.innerText = `Actions: ${recordedActions.length}`;
            actionCount.innerText = `(${recordedActions.length})`;
        }

        function updateActionList() {
            if (recordedActions.length === 0) {
                actionList.innerHTML = '<div style="color: #636e72; text-align: center; padding: 20px;">Load a recording or start fresh</div>';
                return;
            }
            
            let html = '';
            
            // Insert marker at beginning if in insert mode and index is 0
            if (isInsertMode && insertAtIndex === 0) {
                html += '<div class="insert-marker active"></div>';
            }
            
            recordedActions.forEach((action, idx) => {
                let details = '';
                if (action.type === 'click' || action.type === 'double_click' || action.type === 'right_click') {
                    details = `<span class="coords">(${action.x}, ${action.y})</span>`;
                } else if (action.type === 'wait') {
                    details = `<span class="coords">${action.delay_ms || 0}ms</span>`;
                } else if (action.type === 'key') {
                    const mods = [];
                    if (action.ctrl) mods.push('Ctrl');
                    if (action.shift) mods.push('Shift');
                    const modStr = mods.length ? mods.join('+') + '+' : '';
                    details = `<span class="coords">${modStr}${action.key}</span>`;
                } else if (action.type === 'type') {
                    details = `<span class="coords">"${(action.text || '').substring(0, 20)}..."</span>`;
                } else if (action.type === 'paste') {
                    details = `<span class="coords">Ctrl+V</span>`;
                } else if (action.type === 'scroll') {
                    details = `<span class="coords">delta: ${action.delta}</span>`;
                }
                
                const desc = action.description ? `<div class="desc">${action.description}</div>` : '';
                const selected = (isInsertMode && insertAtIndex === idx) ? 'selected' : '';
                
                html += `
                <div class="action-item ${selected}" onclick="selectAction(${idx})">
                    <div class="action-header">
                        <span>
                            <span class="action-num">#${idx + 1}</span>
                            <span class="type">${action.type}</span> ${details}
                        </span>
                        <span class="time">+${action.delay_before_ms || 0}ms</span>
                    </div>
                    ${desc}
                    <div class="action-btns">
                        <button class="edit-btn" onclick="event.stopPropagation(); openEditModal(${idx})">✏️</button>
                        <button class="up-btn" onclick="event.stopPropagation(); moveAction(${idx}, -1)" ${idx === 0 ? 'disabled' : ''}>↑</button>
                        <button class="down-btn" onclick="event.stopPropagation(); moveAction(${idx}, 1)" ${idx === recordedActions.length - 1 ? 'disabled' : ''}>↓</button>
                        <button class="dup-btn" onclick="event.stopPropagation(); duplicateAction(${idx})">📋</button>
                        <button class="del-btn" onclick="event.stopPropagation(); deleteAction(${idx})">🗑️</button>
                    </div>
                </div>`;
                
                // Insert marker after this item if it's the insert position
                if (isInsertMode && insertAtIndex === idx + 1) {
                    html += '<div class="insert-marker active"></div>';
                }
            });
            
            // Insert marker at end if inserting at end
            if (isInsertMode && insertAtIndex >= recordedActions.length) {
                html += '<div class="insert-marker active"></div>';
            }
            
            actionList.innerHTML = html;
        }

        function selectAction(idx) {
            if (isInsertMode) {
                setInsertPosition(idx + 1); // Insert after clicked item
            }
        }

        function moveAction(idx, direction) {
            const newIdx = idx + direction;
            if (newIdx < 0 || newIdx >= recordedActions.length) return;
            
            const action = recordedActions.splice(idx, 1)[0];
            recordedActions.splice(newIdx, 0, action);
            setModified(true);
            updateActionList();
        }

        function duplicateAction(idx) {
            const action = JSON.parse(JSON.stringify(recordedActions[idx]));
            action.timestamp = new Date().toISOString();
            recordedActions.splice(idx + 1, 0, action);
            setModified(true);
            updateActionList();
            updateStats();
            info.innerText = `Duplicated action #${idx + 1}`;
        }

        function deleteAction(idx) {
            if (!confirm(`Delete action #${idx + 1}?`)) return;
            recordedActions.splice(idx, 1);
            setModified(true);
            updateActionList();
            updateStats();
            playBtn.disabled = recordedActions.length === 0;
        }

        // Edit Modal Functions
        function openEditModal(idx) {
            editingActionIndex = idx;
            const action = recordedActions[idx];
            
            document.getElementById('editActionNum').innerText = idx + 1;
            document.getElementById('editType').value = action.type || 'click';
            document.getElementById('editX').value = action.x || '';
            document.getElementById('editY').value = action.y || '';
            document.getElementById('editDelay').value = action.delay_before_ms || 500;
            document.getElementById('editDesc').value = action.description || '';
            
            // Set value field based on type
            if (action.type === 'wait') {
                document.getElementById('editValue').value = action.delay_ms || 1000;
            } else if (action.type === 'key') {
                document.getElementById('editValue').value = action.key || '';
            } else if (action.type === 'type') {
                document.getElementById('editValue').value = action.text || '';
            } else {
                document.getElementById('editValue').value = '';
            }
            
            updateEditFields();
            document.getElementById('modalOverlay').classList.add('active');
            document.getElementById('editModal').classList.add('active');
        }

        function closeEditModal() {
            editingActionIndex = -1;
            document.getElementById('modalOverlay').classList.remove('active');
            document.getElementById('editModal').classList.remove('active');
        }

        function updateEditFields() {
            const type = document.getElementById('editType').value;
            const coordsField = document.getElementById('editCoordsField');
            const valueField = document.getElementById('editValueField');
            const valueInput = document.getElementById('editValue');
            
            // Show/hide fields based on type
            if (['click', 'right_click', 'double_click'].includes(type)) {
                coordsField.style.display = 'block';
                valueField.style.display = 'none';
            } else if (type === 'wait') {
                coordsField.style.display = 'none';
                valueField.style.display = 'block';
                valueField.querySelector('label').innerText = 'Wait Duration (ms)';
            } else if (type === 'key') {
                coordsField.style.display = 'none';
                valueField.style.display = 'block';
                valueField.querySelector('label').innerText = 'Key (e.g., Enter, Tab, a, v)';
            } else if (type === 'type') {
                coordsField.style.display = 'none';
                valueField.style.display = 'block';
                valueField.querySelector('label').innerText = 'Text to Type';
            } else {
                coordsField.style.display = 'none';
                valueField.style.display = 'none';
            }
        }

        function captureCurrentPosition() {
            document.getElementById('editX').value = lastMouseX;
            document.getElementById('editY').value = lastMouseY;
            info.innerText = `Captured position: (${lastMouseX}, ${lastMouseY})`;
        }

        function saveEditedAction() {
            if (editingActionIndex < 0) return;
            
            const action = recordedActions[editingActionIndex];
            const type = document.getElementById('editType').value;
            
            action.type = type;
            action.delay_before_ms = parseInt(document.getElementById('editDelay').value) || 500;
            action.description = document.getElementById('editDesc').value;
            
            if (['click', 'right_click', 'double_click'].includes(type)) {
                action.x = parseInt(document.getElementById('editX').value) || 0;
                action.y = parseInt(document.getElementById('editY').value) || 0;
            } else if (type === 'wait') {
                action.delay_ms = parseInt(document.getElementById('editValue').value) || 1000;
            } else if (type === 'key') {
                action.key = document.getElementById('editValue').value;
            } else if (type === 'type') {
                action.text = document.getElementById('editValue').value;
            }
            
            setModified(true);
            updateActionList();
            closeEditModal();
            info.innerText = `Updated action #${editingActionIndex + 1}`;
        }

        // Manual Action Fields
        function updateManualActionFields() {
            const type = document.getElementById('manualActionType').value;
            const fields = document.getElementById('manualActionFields');
            
            if (type === 'click') {
                fields.innerHTML = `
                    <div class="btn-row">
                        <input type="number" id="manualX" placeholder="X" style="width: 45%;" value="${lastMouseX}">
                        <input type="number" id="manualY" placeholder="Y" style="width: 45%;" value="${lastMouseY}">
                    </div>`;
            } else if (type === 'wait') {
                fields.innerHTML = `<input type="number" id="manualValue" placeholder="Wait duration (ms)" value="1000">`;
            } else if (type === 'key') {
                fields.innerHTML = `<input type="text" id="manualValue" placeholder="Key (Enter, Tab, v, etc.)">`;
            } else if (type === 'type') {
                fields.innerHTML = `<input type="text" id="manualValue" placeholder="Text to type">`;
            } else {
                fields.innerHTML = '';
            }
        }

        function addManualAction() {
            const type = document.getElementById('manualActionType').value;
            const delay = parseInt(document.getElementById('manualDelay').value) || 500;
            const desc = document.getElementById('manualDesc').value;
            
            let action = { 
                type, 
                delay_before_ms: delay,
                description: desc,
                timestamp: new Date().toISOString()
            };
            
            if (type === 'click') {
                action.x = parseInt(document.getElementById('manualX').value) || 0;
                action.y = parseInt(document.getElementById('manualY').value) || 0;
            } else if (type === 'wait') {
                action.delay_ms = parseInt(document.getElementById('manualValue').value) || 1000;
            } else if (type === 'key') {
                action.key = document.getElementById('manualValue').value || 'Enter';
            } else if (type === 'type') {
                action.text = document.getElementById('manualValue').value || '';
            }
            
            recordedActions.push(action);
            setModified(true);
            updateActionList();
            updateStats();
            playBtn.disabled = false;
            
            document.getElementById('manualDesc').value = '';
            info.innerText = `Added ${type} action`;
        }

        async function saveRecording() {
            if (!currentFilename) {
                saveRecordingAs();
                return;
            }
            
            const platform = document.getElementById('platform').value;
            const recording = {
                platform: platform,
                created: new Date().toISOString(),
                resolution: `${TARGET_WIDTH}x${TARGET_HEIGHT}`,
                actions: recordedActions,
                filename: currentFilename
            };
            
            try {
                const resp = await fetch('/recording/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(recording)
                });
                const data = await resp.json();
                if (data.success) {
                    setModified(false);
                    info.innerText = `Saved: ${currentFilename}`;
                } else {
                    alert(`Save failed: ${data.error}`);
                }
            } catch (err) {
                alert(`Save error: ${err}`);
            }
        }

        async function saveRecordingAs() {
            const platform = document.getElementById('platform').value;
            const recording = {
                platform: platform,
                created: new Date().toISOString(),
                resolution: `${TARGET_WIDTH}x${TARGET_HEIGHT}`,
                actions: recordedActions
            };
            
            try {
                const resp = await fetch('/recording/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(recording)
                });
                const data = await resp.json();
                if (data.success) {
                    currentFilename = data.filename;
                    currentFilenameEl.innerText = currentFilename;
                    loadedFileInfo.style.display = 'block';
                    setModified(false);
                    refreshRecordings();
                    info.innerText = `Saved as: ${currentFilename}`;
                } else {
                    alert(`Save failed: ${data.error}`);
                }
            } catch (err) {
                alert(`Save error: ${err}`);
            }
        }

        async function playRecording() {
            if (recordedActions.length === 0 || isPlayingBack) return;
            
            isPlayingBack = true;
            playBtn.disabled = true;
            playBtn.innerText = '⏸️ Playing...';
            info.innerText = 'Playback started...';
            
            try {
                const resp = await fetch('/recording/playback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ actions: recordedActions })
                });
                const data = await resp.json();
                if (data.success) {
                    info.innerText = `Playback complete: ${data.executed} actions`;
                } else {
                    info.innerText = `Playback failed: ${data.error}`;
                }
            } catch (err) {
                info.innerText = `Playback error: ${err}`;
            }
            
            isPlayingBack = false;
            playBtn.disabled = false;
            playBtn.innerText = '▶️ Test Playback';
        }

        async function refreshRecordings() {
            try {
                const resp = await fetch('/recording/list');
                const data = await resp.json();
                const select = document.getElementById('savedRecordings');
                const currentVal = select.value;
                select.innerHTML = '<option value="">-- Select a recording to edit --</option>';
                data.recordings.forEach(rec => {
                    const opt = document.createElement('option');
                    opt.value = rec;
                    opt.innerText = rec;
                    if (rec === currentVal) opt.selected = true;
                    select.appendChild(opt);
                });
            } catch (err) {
                console.error('Failed to load recordings:', err);
            }
        }

        async function loadSelectedRecording() {
            const filename = document.getElementById('savedRecordings').value;
            if (!filename) return;
            
            if (isModified && !confirm('Discard unsaved changes?')) {
                document.getElementById('savedRecordings').value = currentFilename || '';
                return;
            }
            
            try {
                const resp = await fetch(`/recording/load/${filename}`);
                const data = await resp.json();
                if (data.success) {
                    recordedActions = data.recording.actions || [];
                    currentFilename = filename;
                    document.getElementById('platform').value = data.recording.platform || 'custom';
                    
                    currentFilenameEl.innerText = filename;
                    loadedFileInfo.style.display = 'block';
                    setModified(false);
                    
                    updateActionList();
                    updateStats();
                    playBtn.disabled = recordedActions.length === 0;
                    saveAsBtn.disabled = recordedActions.length === 0;
                    info.innerText = `Loaded: ${filename} (${recordedActions.length} actions)`;
                }
            } catch (err) {
                info.innerText = `Load error: ${err}`;
            }
        }

        // Initialize
        refreshRecordings();
        updateManualActionFields();
        updateMode();

        async function sendHotkey(keys) {
            info.innerText = `Sending Hotkey: ${keys.join('+')}...`;
            try {
                await fetch('/hotkey', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({keys: keys})
                });
                info.innerText = `Sent Hotkey`;
            } catch (err) {
                info.innerText = `Hotkey Error: ${err}`;
            }
        }

        // Track mouse coords
        img.addEventListener('mousemove', (e) => {
            const rect = img.getBoundingClientRect();
            const scaleX = TARGET_WIDTH / rect.width;
            const scaleY = TARGET_HEIGHT / rect.height;
            const x = Math.round((e.clientX - rect.left) * scaleX);
            const y = Math.round((e.clientY - rect.top) * scaleY);
            lastMouseX = x;
            lastMouseY = y;
            info.innerText = `Pos: ${x}, ${y}`;
            if (isRecording) {
                info.innerText += ' | 🔴 RECORDING';
            } else if (isInsertMode) {
                info.innerText += ' | 📍 INSERT MODE';
            }
        });

        // Helper to get coords
        function getCoords(e) {
            const rect = img.getBoundingClientRect();
            const scaleX = TARGET_WIDTH / rect.width;
            const scaleY = TARGET_HEIGHT / rect.height;
            return {
                x: Math.round((e.clientX - rect.left) * scaleX),
                y: Math.round((e.clientY - rect.top) * scaleY)
            };
        }

        async function sendClick(x, y, button) {
            info.innerText = `Sending Click (${button}): ${x}, ${y}...`;
            
            // Record the action if in recording or insert mode
            if (isRecording || isInsertMode) {
                recordAction({
                    type: button === 'left' ? 'click' : (button === 'right' ? 'right_click' : 'click'),
                    x: x,
                    y: y
                });
            }
            
            try {
                const resp = await fetch('/click', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({x: x, y: y, button: button})
                });
                const data = await resp.json();
                if(data.success) {
                    info.innerText = `Clicked (${button}): ${x}, ${y}`;
                    if (isRecording) info.innerText += ' | 🔴 Recorded';
                } else {
                    info.innerText = `Error: ${data.error}`;
                }
            } catch (err) {
                info.innerText = `Req Failed: ${err}`;
            }
        }

        // Handle Left Click
        img.addEventListener('click', async (e) => {
            container.focus(); 
            const coords = getCoords(e);
            await sendClick(coords.x, coords.y, 'left');
        });

        // Handle Right Click (Context Menu)
        img.addEventListener('contextmenu', async (e) => {
            e.preventDefault();
            container.focus();
            const coords = getCoords(e);
            await sendClick(coords.x, coords.y, 'right');
        });

        // Handle Double Click
        img.addEventListener('dblclick', async (e) => {
            container.focus();
            const coords = getCoords(e);
            
            // Record double click action (recordAction handles mode check)
            if (isRecording || isInsertMode) {
                recordAction({
                    type: 'double_click',
                    x: coords.x,
                    y: coords.y
                });
            }
            
            // Note: Single clicks already sent by click event, just send one more for double
            try {
                await fetch('/click', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({x: coords.x, y: coords.y, button: 'left'})
                });
            } catch (err) {
                console.error("Double click second click failed:", err);
            }
        });

        // Handle Scroll
        container.addEventListener('wheel', async (e) => {
            e.preventDefault();
            
            const SCROLL_FACTOR = -0.01;
            const delta = Math.round(e.deltaY * SCROLL_FACTOR);
            
            if (delta === 0) return;

            info.innerText = `Scrolling: ${delta} (Raw: ${Math.round(e.deltaY)})`;
            
            // Record scroll action if in capture mode
            if (isRecording || isInsertMode) {
                recordAction({
                    type: 'scroll',
                    delta: delta
                });
            }

            try {
                await fetch('/scroll', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({delta: delta})
                });
            } catch (err) {
                console.error("Scroll fail:", err);
            }
        }, { passive: false });

        // Handle Keyboard
        container.addEventListener('keydown', async (e) => {
            e.preventDefault(); 
            
            const key = e.key;
            console.log("Key:", key, "Ctrl:", e.ctrlKey);
            info.innerText = `Sending Key: ${key} (Ctrl: ${e.ctrlKey})...`;
            
            // Record key action if in capture mode
            if (isRecording || isInsertMode) {
                recordAction({
                    type: 'key',
                    key: key,
                    ctrl: e.ctrlKey,
                    shift: e.shiftKey
                });
            }
            
            try {
                const resp = await fetch('/keypress', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        key: key,
                        ctrl: e.ctrlKey,
                        shift: e.shiftKey
                    })
                });
                const data = await resp.json();
                if(data.success) {
                    info.innerText = `Sent Key: ${key}`;
                    if (isRecording) info.innerText += ' | 🔴 Recorded';
                }
            } catch (err) {
                info.innerText = `Key Failed: ${err}`;
            }
        });

    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(VIEWER_HTML, vnc_host=VNC_HOST)

@app.route('/stream')
def stream():
    return Response(generate_mjpeg(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/frame')
def frame():
    img = get_latest_frame()
    if img is None:
        return "No frame", 503
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=95)
    buf.seek(0)
    return Response(buf.getvalue(), mimetype='image/jpeg')

@app.route('/click', methods=['POST'])
def handle_click():
    """Handle interactive click."""
    try:
        data = request.json
        x = data.get('x')
        y = data.get('y')
        button = data.get('button', 'left')
        
        # Validation
        if x is None or y is None:
            return jsonify({"error": "Missing coordinates"}), 400

        ctrl = get_input_controller()
        if ctrl:
            # Move and Click
            ctrl.move_to(x, y)
            time.sleep(0.05)
            ctrl.click(button)
            return jsonify({"success": True, "clicked": {"x": x, "y": y}})
        else:
            return jsonify({"error": "Controller not available"}), 500

    except Exception as e:
        logger.error(f"Click handler failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/keypress', methods=['POST'])
def handle_keypress():
    """Handle interactive keypress with properly timed modifiers."""
    try:
        data = request.json
        key = data.get('key')
        ctrl_mod = data.get('ctrl', False)
        
        if not key:
            return jsonify({"error": "Missing key"}), 400

        ctrl = get_input_controller()
        if ctrl:
            # Ignore modifier keys themselves if properly handled as modifiers
            if key.lower() in ['control', 'shift', 'alt']:
                return jsonify({"success": True, "ignored": key})

            # Special Character Map (Shift + Key)
            SHIFT_MAP = {
                '$': '4', '@': '2', '#': '3', '%': '5', '^': '6',
                '&': '7', '*': '8', '(': '9', ')': '0', '!': '1',
                ':': ';', '"': "'", '<': ',', '>': '.', '?': '/',
                '_': '-', '+': '=', '{': '[', '}': ']', '|': '\\',
                '~': '`'
            }

            # Map known special keys from JS to HID names
            if len(key) > 1:
                key = key.lower()
                if key == " ": key = "space" 

            # HANDLE CTRL COMBINATIONS
            if ctrl_mod:
                ctrl.keyboard._send_key('ctrl', 'down')
                time.sleep(0.05)
                # If the key is 'Control', we ignore it above.
                # For Ctrl+V, key is 'v', etc.
                ctrl.keyboard._send_key(key.lower(), 'press')
                time.sleep(0.05)
                ctrl.keyboard._send_key('ctrl', 'up')

            # HANDLE SHIFT COMBINATIONS (Symbols)
            elif key in SHIFT_MAP:
                mapped_key = SHIFT_MAP[key]
                ctrl.keyboard._send_key('shift', 'down')
                time.sleep(0.05)
                ctrl.keyboard._send_key(mapped_key, 'press')
                time.sleep(0.05)
                ctrl.keyboard._send_key('shift', 'up')
            
            # HANDLE UPPERCASE (via Shift)
            elif len(key) == 1 and key.isupper():
                ctrl.keyboard._send_key('shift', 'down')
                time.sleep(0.05)
                ctrl.keyboard._send_key(key.lower(), 'press')
                time.sleep(0.05)
                ctrl.keyboard._send_key('shift', 'up')
                
            # STANDARD KEYPRESS
            else:
                ctrl.keyboard._send_key(key, 'press')
            
            return jsonify({"success": True, "key": key})
        else:
            return jsonify({"error": "Controller not available"}), 500

    except Exception as e:
        logger.error(f"Key handler failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/scroll', methods=['POST'])
def handle_scroll():
    """Handle interactive scroll."""
    try:
        data = request.json
        delta = data.get('delta')
        
        if delta is None:
            return jsonify({"error": "Missing delta"}), 400

        ctrl = get_input_controller()
        if ctrl:
            # Send raw scroll
            ctrl.scroll_raw(delta)
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Controller not available"}), 500

    except Exception as e:
        logger.error(f"Scroll handler failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/hotkey', methods=['POST'])
def handle_hotkey():
    """Handle hotkey combinations."""
    try:
        data = request.json
        keys = data.get('keys')
        
        if not keys or not isinstance(keys, list):
            return jsonify({"error": "Missing or invalid keys list"}), 400

        ctrl = get_input_controller()
        if ctrl:
            ctrl.hotkey(*keys)
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Controller not available"}), 500

    except Exception as e:
        logger.error(f"Hotkey handler failed: {e}")
        return jsonify({"error": str(e)}), 500

# ============== RECORDING ENDPOINTS ==============

@app.route('/recording/list')
def list_recordings():
    """List all saved recordings."""
    try:
        recordings = [f for f in os.listdir(RECORDINGS_DIR) if f.endswith('.json')]
        return jsonify({"recordings": sorted(recordings)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/recording/save', methods=['POST'])
def save_recording():
    """Save a recording to disk. If filename provided, overwrite existing."""
    try:
        data = request.json
        platform = data.get('platform', 'custom')
        existing_filename = data.get('filename')
        
        if existing_filename:
            # Overwrite existing file
            filename = existing_filename
            filepath = os.path.join(RECORDINGS_DIR, filename)
        else:
            # Generate new filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{platform}_{timestamp}.json"
            filepath = os.path.join(RECORDINGS_DIR, filename)
        
        # Remove filename from data before saving (it's metadata)
        save_data = {k: v for k, v in data.items() if k != 'filename'}
        
        with open(filepath, 'w') as f:
            json.dump(save_data, f, indent=2)
        
        logger.info(f"Recording saved: {filepath}")
        return jsonify({"success": True, "path": filepath, "filename": filename})
    except Exception as e:
        logger.error(f"Save recording failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/recording/load/<filename>')
def load_recording(filename):
    """Load a recording from disk."""
    try:
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "Recording not found"}), 404
        
        with open(filepath, 'r') as f:
            recording = json.load(f)
        
        return jsonify({"success": True, "recording": recording})
    except Exception as e:
        logger.error(f"Load recording failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/recording/playback', methods=['POST'])
def playback_recording():
    """Execute a recorded workflow."""
    try:
        data = request.json
        actions = data.get('actions', [])
        
        if not actions:
            return jsonify({"error": "No actions to play"}), 400
        
        ctrl = get_input_controller()
        if not ctrl:
            return jsonify({"error": "Controller not available"}), 500
        
        executed = 0
        for action in actions:
            action_type = action.get('type')
            delay_before = action.get('delay_before_ms', 0)
            
            # Wait before action
            if delay_before > 0:
                time.sleep(delay_before / 1000.0)
            
            # Execute action based on type
            if action_type == 'click':
                x, y = action.get('x'), action.get('y')
                if x is not None and y is not None:
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('left')
                    
            elif action_type == 'right_click':
                x, y = action.get('x'), action.get('y')
                if x is not None and y is not None:
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('right')
                    
            elif action_type == 'double_click':
                x, y = action.get('x'), action.get('y')
                if x is not None and y is not None:
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('left')
                    time.sleep(0.1)
                    ctrl.click('left')
                    
            elif action_type == 'scroll':
                delta = action.get('delta', 0)
                if delta != 0:
                    ctrl.scroll_raw(delta)
                    
            elif action_type == 'key':
                key = action.get('key')
                ctrl_mod = action.get('ctrl', False)
                shift_mod = action.get('shift', False)
                
                if key:
                    if ctrl_mod:
                        ctrl.keyboard._send_key('ctrl', 'down')
                        time.sleep(0.05)
                        ctrl.keyboard._send_key(key.lower(), 'press')
                        time.sleep(0.05)
                        ctrl.keyboard._send_key('ctrl', 'up')
                    elif shift_mod:
                        ctrl.keyboard._send_key('shift', 'down')
                        time.sleep(0.05)
                        ctrl.keyboard._send_key(key.lower(), 'press')
                        time.sleep(0.05)
                        ctrl.keyboard._send_key('shift', 'up')
                    else:
                        ctrl.keyboard._send_key(key, 'press')
                        
            elif action_type == 'type':
                text = action.get('text', '')
                if text:
                    ctrl.keyboard.type_text(text)
                    
            elif action_type == 'paste':
                # Ctrl+V
                ctrl.keyboard._send_key('ctrl', 'down')
                time.sleep(0.05)
                ctrl.keyboard._send_key('v', 'press')
                time.sleep(0.05)
                ctrl.keyboard._send_key('ctrl', 'up')
                
            elif action_type == 'wait':
                wait_ms = action.get('delay_ms', 1000)
                time.sleep(wait_ms / 1000.0)
            
            executed += 1
            logger.info(f"Executed action {executed}: {action_type}")
        
        return jsonify({"success": True, "executed": executed})
    except Exception as e:
        logger.error(f"Playback failed: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/recording/delete/<filename>', methods=['DELETE'])
def delete_recording(filename):
    """Delete a recording."""
    try:
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({"success": True})
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============== END RECORDING ENDPOINTS ==============

if __name__ == '__main__':
    # Start Capture Process
    capture_proc = multiprocessing.Process(target=capture_process_func)
    capture_proc.daemon = True
    capture_proc.start()
    
    logger.info("Starting Interactive VNC Stream Server...")
    logger.info("Open http://localhost:5555")
    
    try:
        app.run(host='0.0.0.0', port=5555, threaded=True)
    finally:
        if capture_proc.is_alive():
            capture_proc.terminate()
