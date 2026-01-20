#!/usr/bin/env python3
"""
VNC Live Stream Server (Interactive)
- Serves live MJPEG stream
- Interactive: Captures clicks in browser and sends to Windows via HID
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

# HTML with Interactive Click & Keyboard Handler + Workflow Editor
VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Windows VNC Live (Interactive)</title>
    <style>
        * { box-sizing: border-box; }
        :root {
            --bg: #0f1224;
            --panel: #141b33;
            --panel-2: #10182d;
            --accent: #1da1f2;
            --accent-2: #00f5a0;
            --danger: #e74c3c;
            --warn: #f1c40f;
            --text: #e9eef5;
            --muted: #9aa6b2;
            --border: #25314f;
        }
        body {
            margin: 0;
            background: var(--bg);
            display: flex;
            flex-direction: row;
            font-family: 'Segoe UI', Arial, sans-serif;
            color: var(--text);
            height: 100vh;
            overflow: hidden;
        }
        .main-panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 16px 18px;
            gap: 10px;
            overflow: hidden;
        }
        .top-bar {
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        h1 { color: var(--accent); margin: 0; font-weight: 500; font-size: 1.25em; }
        .status { color: var(--accent-2); font-size: 0.85em; }
        .container {
            position: relative;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.45);
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid var(--border);
            outline: none;
            flex: 1;
            width: 100%;
            max-height: calc(100vh - 200px);
            background: #0b0f1f;
        }
        .container:focus { border-color: var(--accent-2); box-shadow: 0 0 0 2px rgba(0, 245, 160, 0.2); }
        .container.recording { border-color: var(--danger); animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { border-color: var(--danger); } 50% { border-color: #ff6b81; } }
        #stream { display: block; width: 100%; height: 100%; object-fit: contain; cursor: crosshair; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; justify-content: center; }
        button {
            background: #1b4b7a;
            border: 1px solid #2b5f93;
            padding: 7px 14px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            color: white;
            transition: transform 0.05s, background 0.2s, border 0.2s;
            font-size: 0.83em;
        }
        button:hover { background: #2667a4; border-color: #2f77b8; }
        button:active { transform: translateY(1px); }
        button.danger { background: #7a1b1b; border-color: #a12b2b; }
        button.danger:hover { background: #9e2b2b; }
        button.success { background: #0f6b4b; border-color: #178a63; }
        button.success:hover { background: #139c70; }
        .info { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; color: var(--muted); font-size: 0.82em; }
        .info-row { width: 100%; display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }

        /* Workflow Editor Panel */
        .editor-panel {
            width: 400px;
            background: var(--panel);
            border-left: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        .editor-header {
            background: var(--panel-2);
            padding: 12px 14px;
            border-bottom: 1px solid var(--border);
        }
        .editor-header h2 { margin: 0; color: var(--accent); font-size: 1.05em; font-weight: 500; }
        .editor-controls { padding: 12px; background: var(--panel); border-bottom: 1px solid var(--border); }
        .editor-controls select, .editor-controls input, .editor-controls textarea {
            background: #0f1a30; border: 1px solid #263a5e; color: #fff; padding: 6px 10px;
            border-radius: 6px; width: 100%; margin-bottom: 8px; font-size: 0.82em;
        }
        .editor-buttons { display: flex; flex-wrap: wrap; gap: 6px; }
        .editor-buttons button { padding: 6px 10px; font-size: 0.78em; flex: 1; min-width: 90px; }
        .panel-section { margin-top: 8px; }
        .panel-title { font-size: 0.75em; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; margin: 6px 0; }
        .action-list {
            flex: 1;
            overflow-y: auto;
            padding: 12px;
        }
        .action-item {
            background: #0f1a30;
            border: 1px solid #1d2b45;
            border-radius: 8px;
            padding: 10px 10px 8px;
            margin-bottom: 10px;
            font-size: 0.8em;
            position: relative;
        }
        .action-item:hover { border-color: var(--accent); }
        .action-item.selected { border-color: var(--accent-2); background: #132a2a; }
        .action-item .action-type { color: var(--accent); font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em; }
        .action-item .action-coords { color: #ffeaa7; }
        .action-item .action-delay { color: #7bdff2; }
        .action-item .action-desc { color: #dfe6e9; font-style: italic; margin-top: 4px; }
        .action-item .action-buttons { position: absolute; right: 8px; top: 8px; display: flex; gap: 4px; }
        .action-item .action-buttons button { padding: 2px 6px; font-size: 0.7em; }
        .insert-marker { background: var(--accent-2); height: 3px; border-radius: 2px; margin: 4px 0; }
        .recording-status { background: var(--danger); color: white; padding: 8px; text-align: center; font-weight: bold; }
        .unsaved-indicator { color: var(--warn); font-size: 0.85em; margin-left: 10px; }

        .modal {
            position: fixed; inset: 0; display: none; align-items: center; justify-content: center;
            background: rgba(0,0,0,0.6); z-index: 999;
        }
        .modal-content {
            width: 520px; max-width: 95vw; background: #0f1a30; border: 1px solid #1f2f4f;
            border-radius: 10px; padding: 14px; box-shadow: 0 10px 40px rgba(0,0,0,0.45);
        }
        .modal-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .modal-title { font-size: 1em; color: var(--accent); font-weight: 600; }
        .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
        .form-row { display: flex; flex-direction: column; gap: 4px; }
        .form-row label { font-size: 0.75em; color: var(--muted); }
        .form-row input, .form-row select, .form-row textarea { width: 100%; background: #0c1426; border: 1px solid #223455; color: #fff; padding: 6px 8px; border-radius: 6px; font-size: 0.8em; }
        .modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="main-panel">
        <div class="top-bar">
            <h1>Windows 10 Live Control</h1>
            <div class="status">Streaming from {{ vnc_host }} | <span id="mode-indicator">Interactive Mode</span></div>
        </div>
        
        <div class="container" tabindex="0" id="view-container">
            <img id="stream" src="/stream" alt="VNC Stream">
            <div id="coord-marker" style="display:none;position:absolute;pointer-events:none;z-index:100;">
                <svg width="30" height="30" viewBox="0 0 30 30">
                    <line x1="0" y1="0" x2="30" y2="30" stroke="red" stroke-width="3"/>
                    <line x1="30" y1="0" x2="0" y2="30" stroke="red" stroke-width="3"/>
                </svg>
            </div>
        </div>

        <div class="info-row">
            <div class="info" id="coords">Click inside to type / Move mouse</div>
            <div class="info" id="recording-info">Recording: 0 actions | Last: —</div>
        </div>

        <div class="controls">
            <button onclick="sendHotkey(['ctrl', 'alt', 'delete'])" class="danger">Ctrl+Alt+Del</button>
            <button onclick="snapshot()">Snapshot</button>
            <button onclick="reconnectVNC()" id="btn-reconnect">Reconnect VNC</button>
            <span id="vnc-status" style="padding: 7px 14px; border-radius: 6px; font-size: 0.83em; background: #333;">Checking...</span>
        </div>
    </div>
    
    <div class="editor-panel">
        <div class="editor-header">
            <h2>Workflow Editor <span class="unsaved-indicator" id="unsaved" style="display:none">*unsaved</span></h2>
        </div>
        <div id="recording-status" class="recording-status" style="display:none">RECORDING...</div>
        
        <div class="editor-controls">
            <select id="recording-select" onchange="loadSelectedRecording()">
                <option value="">-- Select Recording --</option>
            </select>
            <input id="recording-platform" placeholder="platform (instagram, facebook, skool...)" />
            <input id="recording-description" placeholder="recording description" />
            <div class="editor-buttons">
                <button onclick="loadRecordingsList()">Refresh</button>
                <button onclick="newRecording()" class="success">New Empty</button>
            </div>
            <div class="panel-section">
                <div class="panel-title">Automation Control</div>
                <div class="editor-buttons">
                    <button onclick="toggleMainPause()" id="btn-pause-main" class="danger" style="flex:2">Pause Main</button>
                </div>
                <div id="pause-status" style="margin-top:6px;font-size:0.75em;color:var(--muted);text-align:center;">Checking...</div>
            </div>
            <div class="panel-section">
                <div class="panel-title">Record</div>
                <div class="editor-buttons">
                    <button onclick="startRecording()" class="danger" id="btn-record">Record New</button>
                    <button onclick="stopRecording()" style="display:none" id="btn-stop">Stop</button>
                    <button onclick="toggleInsertMode()" id="btn-insert">Insert At Position</button>
                </div>
            </div>
            <div class="panel-section">
                <div class="panel-title">Actions</div>
                <div class="editor-buttons">
                    <button onclick="addManualAction('click')">Add Click</button>
                    <button onclick="addManualAction('right_click')">Add Right Click</button>
                    <button onclick="addManualAction('double_click')">Add Double</button>
                    <button onclick="addManualAction('wait')">Add Wait</button>
                    <button onclick="addManualAction('key')">Add Key</button>
                    <button onclick="addManualAction('type')">Add Type</button>
                    <button onclick="addManualAction('paste')">Add Paste</button>
                    <button onclick="addManualAction('scroll')">Add Scroll</button>
                    <button onclick="addManualAction('wait_for_change')">Add Wait Change</button>
                </div>
            </div>
            <div class="panel-section">
                <div class="panel-title">Save & Playback</div>
                <div class="editor-buttons">
                    <button onclick="saveRecording()">Save</button>
                    <button onclick="saveRecordingAs()">Save As</button>
                    <button onclick="testPlayback()" class="success" id="btn-playback">Test Playback</button>
                    <button onclick="abortPlayback()" class="danger" id="btn-abort" style="display:none">Abort</button>
                </div>
            </div>
        </div>
        
        <div class="action-list" id="action-list">
            <div style="color:#636e72;text-align:center;padding:20px">
                Select or create a recording to begin
            </div>
        </div>
    </div>

    <div class="modal" id="action-modal">
        <div class="modal-content">
            <div class="modal-header">
                <div class="modal-title">Edit Action</div>
                <button onclick="closeActionModal()" class="danger">Close</button>
            </div>
            <div class="form-grid">
                <div class="form-row">
                    <label>Type</label>
                    <select id="edit-type">
                        <option value="click">click</option>
                        <option value="double_click">double_click</option>
                        <option value="right_click">right_click</option>
                        <option value="wait">wait</option>
                        <option value="key">key</option>
                        <option value="type">type</option>
                        <option value="paste">paste</option>
                        <option value="scroll">scroll</option>
                        <option value="wait_for_change">wait_for_change</option>
                    </select>
                </div>
                <div class="form-row">
                    <label>Description</label>
                    <input id="edit-description" />
                </div>
                <div class="form-row">
                    <label>X</label>
                    <input id="edit-x" type="number" />
                </div>
                <div class="form-row">
                    <label>Y</label>
                    <input id="edit-y" type="number" />
                </div>
                <div class="form-row">
                    <label>Button</label>
                    <select id="edit-button">
                        <option value="left">left</option>
                        <option value="right">right</option>
                    </select>
                </div>
                <div class="form-row">
                    <label>Delay Before (ms)</label>
                    <input id="edit-delay-before" type="number" />
                </div>
                <div class="form-row">
                    <label>Delay (ms)</label>
                    <input id="edit-delay" type="number" />
                </div>
                <div class="form-row">
                    <label>Key</label>
                    <input id="edit-key" />
                </div>
                <div class="form-row">
                    <label>Ctrl</label>
                    <select id="edit-ctrl"><option value="false">false</option><option value="true">true</option></select>
                </div>
                <div class="form-row">
                    <label>Shift</label>
                    <select id="edit-shift"><option value="false">false</option><option value="true">true</option></select>
                </div>
                <div class="form-row">
                    <label>Text</label>
                    <textarea id="edit-text" rows="2"></textarea>
                </div>
                <div class="form-row">
                    <label>Scroll Delta</label>
                    <input id="edit-delta" type="number" />
                </div>
                <div class="form-row">
                    <label>Timeout (ms)</label>
                    <input id="edit-timeout" type="number" />
                </div>
                <div class="form-row">
                    <label>Change Threshold</label>
                    <input id="edit-threshold" type="number" />
                </div>
            </div>
            <div class="modal-actions">
                <button onclick="useLastMouse()">Use Last Mouse</button>
                <button onclick="saveActionEdit()" class="success">Save Changes</button>
            </div>
        </div>
    </div>

    <script>
        const TARGET_WIDTH = 1600;
        const TARGET_HEIGHT = 1200;
        const img = document.getElementById('stream');
        const container = document.getElementById('view-container');
        const info = document.getElementById('coords');
        const recordingInfo = document.getElementById('recording-info');
        const platformInput = document.getElementById('recording-platform');
        const descriptionInput = document.getElementById('recording-description');

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

        let lastMouse = { x: 0, y: 0 };

        // Helper to get actual rendered image bounds (accounting for object-fit: contain letterboxing)
        function getImageBounds() {
            const rect = img.getBoundingClientRect();
            const naturalWidth = img.naturalWidth || TARGET_WIDTH;
            const naturalHeight = img.naturalHeight || TARGET_HEIGHT;
            
            // Calculate the actual rendered size maintaining aspect ratio
            const containerAspect = rect.width / rect.height;
            const imageAspect = naturalWidth / naturalHeight;
            
            let renderedWidth, renderedHeight, offsetX, offsetY;
            
            if (containerAspect > imageAspect) {
                // Container is wider - letterbox on sides
                renderedHeight = rect.height;
                renderedWidth = rect.height * imageAspect;
                offsetX = (rect.width - renderedWidth) / 2;
                offsetY = 0;
            } else {
                // Container is taller - letterbox on top/bottom
                renderedWidth = rect.width;
                renderedHeight = rect.width / imageAspect;
                offsetX = 0;
                offsetY = (rect.height - renderedHeight) / 2;
            }
            
            return {
                rect,
                renderedWidth,
                renderedHeight,
                offsetX,
                offsetY,
                naturalWidth,
                naturalHeight
            };
        }

        // Track mouse coords
        img.addEventListener('mousemove', (e) => {
            const bounds = getImageBounds();
            const relX = e.clientX - bounds.rect.left - bounds.offsetX;
            const relY = e.clientY - bounds.rect.top - bounds.offsetY;
            
            // Check if mouse is within actual image area
            if (relX < 0 || relX > bounds.renderedWidth || relY < 0 || relY > bounds.renderedHeight) {
                info.innerText = `Outside image area`;
                return;
            }
            
            const scaleX = TARGET_WIDTH / bounds.renderedWidth;
            const scaleY = TARGET_HEIGHT / bounds.renderedHeight;
            const x = Math.round(relX * scaleX);
            const y = Math.round(relY * scaleY);
            
            // Clamp to valid range
            lastMouse = { 
                x: Math.max(0, Math.min(TARGET_WIDTH - 1, x)), 
                y: Math.max(0, Math.min(TARGET_HEIGHT - 1, y)) 
            };
            info.innerText = `Pos: ${lastMouse.x}, ${lastMouse.y}`;
        });

        // Helper to get coords (accounting for object-fit: contain)
        function getCoords(e) {
            const bounds = getImageBounds();
            const relX = e.clientX - bounds.rect.left - bounds.offsetX;
            const relY = e.clientY - bounds.rect.top - bounds.offsetY;
            
            const scaleX = TARGET_WIDTH / bounds.renderedWidth;
            const scaleY = TARGET_HEIGHT / bounds.renderedHeight;
            
            const x = Math.round(relX * scaleX);
            const y = Math.round(relY * scaleY);
            
            // Clamp to valid range
            return {
                x: Math.max(0, Math.min(TARGET_WIDTH - 1, x)),
                y: Math.max(0, Math.min(TARGET_HEIGHT - 1, y))
            };
        }

        async function sendClick(x, y, button) {
            info.innerText = `Sending Click (${button}): ${x}, ${y}...`;
            try {
                const resp = await fetch('/click', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({x: x, y: y, button: button})
                });
                const data = await resp.json();
                if(data.success) {
                    info.innerText = `Clicked (${button}): ${x}, ${y}`;
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
            e.preventDefault(); // Prevent browser menu
            container.focus();
            const coords = getCoords(e);
            await sendClick(coords.x, coords.y, 'right');
        });

        // Handle Scroll Loop
        let scrollTimeout = null;
        container.addEventListener('wheel', async (e) => {
            e.preventDefault();
            
            // User Requested Tuning:
            // 1. Invert direction (-1)
            // 2. Reduce intensity to 1% of raw (0.01) - 10% of previous
            const SCROLL_FACTOR = -0.01;
            
            const delta = Math.round(e.deltaY * SCROLL_FACTOR);
            
            // Filter noise
            if (delta === 0) return;

            // Info update
            info.innerText = `Scrolling: ${delta} (Raw: ${Math.round(e.deltaY)})`;

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
                }
            } catch (err) {
                info.innerText = `Key Failed: ${err}`;
            }
        });

        async function snapshot() {
            const resp = await fetch('/snapshot');
            const data = await resp.json();
            alert('Snapshot: ' + data.path);
        }
        
        async function reconnectVNC() {
            const btn = document.getElementById('btn-reconnect');
            const statusEl = document.getElementById('vnc-status');
            
            btn.disabled = true;
            btn.textContent = 'Reconnecting...';
            statusEl.textContent = 'Reconnecting...';
            statusEl.style.background = '#7a6b1b';
            
            try {
                const resp = await fetch('/reconnect', { method: 'POST' });
                const data = await resp.json();
                
                if (data.success) {
                    statusEl.textContent = data.message;
                    statusEl.style.background = data.has_frame ? '#0f6b4b' : '#7a6b1b';
                    
                    // Reload the stream by resetting src
                    img.src = '/stream?' + Date.now();
                    
                    // Check status after a moment
                    setTimeout(checkVNCStatus, 3000);
                } else {
                    statusEl.textContent = 'Failed: ' + data.error;
                    statusEl.style.background = '#7a1b1b';
                }
            } catch (err) {
                statusEl.textContent = 'Error: ' + err;
                statusEl.style.background = '#7a1b1b';
            } finally {
                btn.disabled = false;
                btn.textContent = 'Reconnect VNC';
            }
        }
        
        async function checkVNCStatus() {
            const statusEl = document.getElementById('vnc-status');
            try {
                const resp = await fetch('/vnc_status');
                const data = await resp.json();
                
                if (data.connected) {
                    statusEl.textContent = 'Connected';
                    statusEl.style.background = '#0f6b4b';
                } else if (data.process_alive && !data.frame_fresh) {
                    statusEl.textContent = 'Stale (' + (data.frame_age_seconds || '?') + 's)';
                    statusEl.style.background = '#7a6b1b';
                } else if (data.process_alive) {
                    statusEl.textContent = 'Waiting for frames...';
                    statusEl.style.background = '#7a6b1b';
                } else {
                    statusEl.textContent = 'Disconnected';
                    statusEl.style.background = '#7a1b1b';
                }
            } catch (err) {
                statusEl.textContent = 'Status check failed';
                statusEl.style.background = '#7a1b1b';
            }
        }
        
        // Check VNC status periodically
        setInterval(checkVNCStatus, 5000);
        checkVNCStatus(); // Initial check
        
        // =====================================================
        // WORKFLOW EDITOR JAVASCRIPT
        // =====================================================
        
        let currentRecording = null;
        let currentFilename = null;
        let isRecording = false;
        let isInsertMode = false;
        let insertPosition = -1;
        let recordingStartTime = 0;
        let lastActionTime = 0;
        let hasUnsavedChanges = false;
        let editIndex = -1;
        let playbackAborted = false;
        let isPlayingBack = false;
        let coordEditMode = false;
        let coordEditIndex = -1;
        
        // Main pause state
        let mainPaused = false;
        
        async function checkMainPauseStatus() {
            try {
                const resp = await fetch('/main/status');
                const data = await resp.json();
                mainPaused = data.paused;
                updatePauseButton();
            } catch (err) {
                console.error('Failed to check pause status:', err);
            }
        }
        
        function updatePauseButton() {
            const btn = document.getElementById('btn-pause-main');
            const status = document.getElementById('pause-status');
            if (mainPaused) {
                btn.textContent = 'Resume Main';
                btn.classList.remove('danger');
                btn.classList.add('success');
                status.innerHTML = '<span style="color:#e74c3c;font-weight:bold;">PAUSED</span> - Automation halted, you can safely edit workflows';
            } else {
                btn.textContent = 'Pause Main';
                btn.classList.remove('success');
                btn.classList.add('danger');
                status.innerHTML = '<span style="color:#00f5a0;">RUNNING</span> - Automation active';
            }
        }
        
        async function toggleMainPause() {
            const btn = document.getElementById('btn-pause-main');
            btn.disabled = true;
            btn.textContent = mainPaused ? 'Resuming...' : 'Pausing...';
            
            try {
                const endpoint = mainPaused ? '/main/resume' : '/main/pause';
                const resp = await fetch(endpoint, { method: 'POST' });
                const data = await resp.json();
                mainPaused = data.paused;
                updatePauseButton();
                info.innerText = mainPaused ? 'Main automation PAUSED' : 'Main automation RESUMED';
            } catch (err) {
                info.innerText = 'Pause toggle failed: ' + err;
                console.error('Pause toggle failed:', err);
            } finally {
                btn.disabled = false;
            }
        }
        
        // Load recordings list on page load
        window.onload = () => {
            loadRecordingsList();
            checkMainPauseStatus();
            container.focus();
            // Periodically check pause status
            setInterval(checkMainPauseStatus, 5000);
        };
        
        async function loadRecordingsList() {
            try {
                const resp = await fetch('/recording/list');
                const data = await resp.json();
                const select = document.getElementById('recording-select');
                select.innerHTML = '<option value="">-- Select Recording --</option>';
                for (const rec of data.recordings || []) {
                    const opt = document.createElement('option');
                    opt.value = rec.filename;
                    opt.textContent = `${rec.filename} (${rec.platform}, ${rec.action_count} actions)`;
                    select.appendChild(opt);
                }
            } catch (err) {
                console.error('Failed to load recordings:', err);
            }
        }
        
        async function loadSelectedRecording() {
            const select = document.getElementById('recording-select');
            const filename = select.value;
            if (!filename) return;
            
            try {
                const resp = await fetch(`/recording/load/${filename}`);
                if (!resp.ok) throw new Error('Failed to load');
                currentRecording = await resp.json();
                currentFilename = filename;
                hasUnsavedChanges = false;
                platformInput.value = currentRecording.platform || '';
                descriptionInput.value = currentRecording.description || '';
                renderActionList();
                updateUnsavedIndicator();
                updateRecordingInfo();
            } catch (err) {
                alert('Failed to load recording: ' + err);
            }
        }
        
        function newRecording() {
            currentRecording = {
                platform: (platformInput.value || 'custom').trim() || 'custom',
                created: new Date().toISOString(),
                resolution: '1600x1200',
                description: (descriptionInput.value || 'New recording').trim() || 'New recording',
                actions: []
            };
            currentFilename = null;
            hasUnsavedChanges = true;
            renderActionList();
            updateUnsavedIndicator();
            updateRecordingInfo();
        }
        
        function renderActionList() {
            const list = document.getElementById('action-list');
            if (!currentRecording || !currentRecording.actions) {
                list.innerHTML = '<div style="color:#636e72;text-align:center;padding:20px">No actions</div>';
                return;
            }
            
            list.innerHTML = '';
            currentRecording.actions.forEach((action, i) => {
                // Insert marker if in insert mode
                if (isInsertMode && insertPosition === i) {
                    list.innerHTML += '<div class="insert-marker"></div>';
                }
                
                const item = document.createElement('div');
                item.className = 'action-item' + (isInsertMode && insertPosition === i ? ' selected' : '');
                item.onclick = () => { if (isInsertMode) setInsertPosition(i); };
                
                let details = '';
                if (action.type === 'click' || action.type === 'double_click' || action.type === 'right_click') {
                    details = `<span class="action-coords">(${action.x}, ${action.y})</span>`;
                } else if (action.type === 'wait') {
                    details = `<span class="action-delay">${action.delay_ms}ms</span>`;
                } else if (action.type === 'key') {
                    details = `<span class="action-coords">${action.ctrl ? 'Ctrl+' : ''}${action.shift ? 'Shift+' : ''}${action.key}</span>`;
                } else if (action.type === 'type') {
                    details = `<span class="action-coords">"${(action.text || '').substring(0, 20)}..."</span>`;
                } else if (action.type === 'paste') {
                    details = `<span class="action-coords">Paste</span>`;
                } else if (action.type === 'scroll') {
                    details = `<span class="action-coords">Δ ${action.delta || 0}</span>`;
                } else if (action.type === 'wait_for_change') {
                    details = `<span class="action-delay">${action.timeout_ms || 0}ms</span>`;
                }
                
                const delay = action.delay_before_ms || action.delay_ms || 0;
                
                const isClickAction = ['click', 'double_click', 'right_click'].includes(action.type);
                const editCoordBtn = isClickAction ? `<button onclick="startCoordEdit(${i});event.stopPropagation();" class="success">Edit Coords</button>` : '';
                
                item.innerHTML = `
                    <span class="action-type">${i + 1}. ${action.type}</span> ${details}
                    <span class="action-delay" style="margin-left:8px">+${delay}ms</span>
                    ${action.description ? '<div class="action-desc">' + action.description + '</div>' : ''}
                    <div class="action-buttons">
                        <button onclick="moveAction(${i}, -1);event.stopPropagation();">↑</button>
                        <button onclick="moveAction(${i}, 1);event.stopPropagation();">↓</button>
                        <button onclick="duplicateAction(${i});event.stopPropagation();">Dup</button>
                        ${editCoordBtn}
                        <button onclick="editAction(${i});event.stopPropagation();">Edit</button>
                        <button onclick="deleteAction(${i});event.stopPropagation();" class="danger">Del</button>
                    </div>
                `;
                
                // Make click actions show coordinate marker on click
                if (isClickAction) {
                    item.style.cursor = 'pointer';
                    item.addEventListener('click', (e) => {
                        if (!isInsertMode && !coordEditMode) {
                            showCoordMarker(action.x, action.y);
                        }
                    });
                }
                
                list.appendChild(item);
            });
            
            // Insert marker at end if inserting at end
            if (isInsertMode && insertPosition >= currentRecording.actions.length) {
                list.innerHTML += '<div class="insert-marker"></div>';
            }
        }
        
        function updateUnsavedIndicator() {
            document.getElementById('unsaved').style.display = hasUnsavedChanges ? 'inline' : 'none';
        }

        function updateRecordingInfo() {
            if (!currentRecording || !currentRecording.actions) {
                recordingInfo.textContent = 'Recording: 0 actions | Last: —';
                return;
            }
            const count = currentRecording.actions.length;
            const last = currentRecording.actions[count - 1];
            const lastText = last
                ? `${last.type}${last.x !== undefined ? ` @ ${last.x},${last.y}` : ''}`
                : '—';
            recordingInfo.textContent = `Recording: ${count} actions | Last: ${lastText}`;
        }
        
        function startRecording() {
            if (!currentRecording) newRecording();
            currentRecording.platform = (platformInput.value || currentRecording.platform || 'custom').trim();
            currentRecording.description = (descriptionInput.value || currentRecording.description || '').trim();
            isRecording = true;
            recordingStartTime = Date.now();
            lastActionTime = recordingStartTime;
            document.getElementById('view-container').classList.add('recording');
            document.getElementById('recording-status').style.display = 'block';
            document.getElementById('btn-record').style.display = 'none';
            document.getElementById('btn-stop').style.display = 'inline-block';
            document.getElementById('mode-indicator').textContent = 'RECORDING';
        }
        
        function stopRecording() {
            isRecording = false;
            document.getElementById('view-container').classList.remove('recording');
            document.getElementById('recording-status').style.display = 'none';
            document.getElementById('btn-record').style.display = 'inline-block';
            document.getElementById('btn-stop').style.display = 'none';
            document.getElementById('mode-indicator').textContent = 'Interactive Mode';
            hasUnsavedChanges = true;
            updateUnsavedIndicator();
            renderActionList();
            updateRecordingInfo();
        }
        
        function toggleInsertMode() {
            isInsertMode = !isInsertMode;
            const btn = document.getElementById('btn-insert');
            if (isInsertMode) {
                btn.textContent = 'Cancel Insert';
                btn.classList.add('danger');
                insertPosition = currentRecording ? currentRecording.actions.length : 0;
            } else {
                btn.textContent = 'Insert At Position';
                btn.classList.remove('danger');
                insertPosition = -1;
            }
            renderActionList();
        }
        
        function setInsertPosition(index) {
            insertPosition = index + 1;  // Insert after clicked item
            renderActionList();
        }
        
        function recordAction(action) {
            if (!currentRecording) return;
            
            const now = Date.now();
            action.delay_before_ms = now - lastActionTime;
            lastActionTime = now;
            
            if (isInsertMode && insertPosition >= 0) {
                currentRecording.actions.splice(insertPosition, 0, action);
                insertPosition++;
            } else {
                currentRecording.actions.push(action);
            }
            
            hasUnsavedChanges = true;
            updateUnsavedIndicator();
            renderActionList();
            updateRecordingInfo();
        }

        function addManualAction(type) {
            if (!currentRecording) newRecording();
            const base = { type, description: '' };
            if (type === 'click' || type === 'right_click' || type === 'double_click') {
                base.x = lastMouse.x;
                base.y = lastMouse.y;
                base.button = type === 'right_click' ? 'right' : 'left';
            } else if (type === 'wait') {
                base.delay_ms = 1000;
            } else if (type === 'key') {
                base.key = 'Enter';
                base.ctrl = false;
                base.shift = false;
            } else if (type === 'type') {
                base.text = 'text';
            } else if (type === 'paste') {
                base.ctrl = true;
                base.key = 'v';
            } else if (type === 'scroll') {
                base.delta = -120;
            } else if (type === 'wait_for_change') {
                base.timeout_ms = 5000;
                base.threshold = 10;
            }
            recordAction(base);
        }
        
        function editAction(index) {
            if (!currentRecording) return;
            editIndex = index;
            const action = currentRecording.actions[index];
            document.getElementById('edit-type').value = action.type || 'click';
            document.getElementById('edit-description').value = action.description || '';
            document.getElementById('edit-x').value = action.x ?? '';
            document.getElementById('edit-y').value = action.y ?? '';
            document.getElementById('edit-button').value = action.button || 'left';
            document.getElementById('edit-delay-before').value = action.delay_before_ms ?? '';
            document.getElementById('edit-delay').value = action.delay_ms ?? '';
            document.getElementById('edit-key').value = action.key ?? '';
            document.getElementById('edit-ctrl').value = String(action.ctrl ?? false);
            document.getElementById('edit-shift').value = String(action.shift ?? false);
            document.getElementById('edit-text').value = action.text ?? '';
            document.getElementById('edit-delta').value = action.delta ?? '';
            document.getElementById('edit-timeout').value = action.timeout_ms ?? '';
            document.getElementById('edit-threshold').value = action.threshold ?? '';
            document.getElementById('action-modal').style.display = 'flex';
        }

        function closeActionModal() {
            document.getElementById('action-modal').style.display = 'none';
        }

        function useLastMouse() {
            document.getElementById('edit-x').value = lastMouse.x;
            document.getElementById('edit-y').value = lastMouse.y;
        }

        function saveActionEdit() {
            if (!currentRecording || editIndex < 0) return;
            const action = currentRecording.actions[editIndex];
            action.type = document.getElementById('edit-type').value;
            action.description = document.getElementById('edit-description').value || '';
            const xVal = parseInt(document.getElementById('edit-x').value, 10);
            const yVal = parseInt(document.getElementById('edit-y').value, 10);
            if (!Number.isNaN(xVal)) action.x = xVal;
            if (!Number.isNaN(yVal)) action.y = yVal;
            action.button = document.getElementById('edit-button').value || action.button;
            const delayBefore = parseInt(document.getElementById('edit-delay-before').value, 10);
            const delay = parseInt(document.getElementById('edit-delay').value, 10);
            if (!Number.isNaN(delayBefore)) action.delay_before_ms = delayBefore;
            if (!Number.isNaN(delay)) action.delay_ms = delay;
            action.key = document.getElementById('edit-key').value || action.key;
            action.ctrl = document.getElementById('edit-ctrl').value === 'true';
            action.shift = document.getElementById('edit-shift').value === 'true';
            action.text = document.getElementById('edit-text').value || action.text;
            const delta = parseInt(document.getElementById('edit-delta').value, 10);
            if (!Number.isNaN(delta)) action.delta = delta;
            const timeoutMs = parseInt(document.getElementById('edit-timeout').value, 10);
            if (!Number.isNaN(timeoutMs)) action.timeout_ms = timeoutMs;
            const threshold = parseInt(document.getElementById('edit-threshold').value, 10);
            if (!Number.isNaN(threshold)) action.threshold = threshold;

            hasUnsavedChanges = true;
            updateUnsavedIndicator();
            renderActionList();
            updateRecordingInfo();
            closeActionModal();
        }
        
        function deleteAction(index) {
            if (confirm('Delete this action?')) {
                currentRecording.actions.splice(index, 1);
                hasUnsavedChanges = true;
                updateUnsavedIndicator();
                renderActionList();
                updateRecordingInfo();
            }
        }

        function moveAction(index, delta) {
            if (!currentRecording) return;
            const newIndex = index + delta;
            if (newIndex < 0 || newIndex >= currentRecording.actions.length) return;
            const [item] = currentRecording.actions.splice(index, 1);
            currentRecording.actions.splice(newIndex, 0, item);
            hasUnsavedChanges = true;
            updateUnsavedIndicator();
            renderActionList();
        }

        function duplicateAction(index) {
            if (!currentRecording) return;
            const copy = JSON.parse(JSON.stringify(currentRecording.actions[index]));
            currentRecording.actions.splice(index + 1, 0, copy);
            hasUnsavedChanges = true;
            updateUnsavedIndicator();
            renderActionList();
            updateRecordingInfo();
        }
        
        function showCoordMarker(x, y) {
            const marker = document.getElementById('coord-marker');
            const bounds = getImageBounds();
            
            // Calculate position relative to rendered image (accounting for letterboxing)
            const scaleX = bounds.renderedWidth / TARGET_WIDTH;
            const scaleY = bounds.renderedHeight / TARGET_HEIGHT;
            
            const displayX = bounds.offsetX + (x * scaleX) - 15;  // Center the 30px marker
            const displayY = bounds.offsetY + (y * scaleY) - 15;
            
            marker.style.left = displayX + 'px';
            marker.style.top = displayY + 'px';
            marker.style.display = 'block';
            
            // Auto-hide after 3 seconds unless in edit mode
            if (!coordEditMode) {
                setTimeout(() => {
                    if (!coordEditMode) marker.style.display = 'none';
                }, 3000);
            }
        }
        
        function hideCoordMarker() {
            document.getElementById('coord-marker').style.display = 'none';
        }
        
        function startCoordEdit(index) {
            coordEditMode = true;
            coordEditIndex = index;
            const action = currentRecording.actions[index];
            
            // Show current position
            showCoordMarker(action.x, action.y);
            
            // Change cursor and add visual indicator
            img.style.cursor = 'crosshair';
            container.classList.add('recording');
            info.innerText = `COORD EDIT MODE: Click on the stream to set new coordinates for action #${index + 1}. Press ESC to cancel.`;
            document.getElementById('mode-indicator').textContent = 'COORD EDIT MODE';
        }
        
        function cancelCoordEdit() {
            coordEditMode = false;
            coordEditIndex = -1;
            hideCoordMarker();
            img.style.cursor = 'crosshair';
            container.classList.remove('recording');
            info.innerText = 'Coord edit cancelled';
            document.getElementById('mode-indicator').textContent = 'Interactive Mode';
        }
        
        function applyCoordEdit(x, y) {
            if (coordEditIndex >= 0 && currentRecording) {
                currentRecording.actions[coordEditIndex].x = x;
                currentRecording.actions[coordEditIndex].y = y;
                hasUnsavedChanges = true;
                updateUnsavedIndicator();
                renderActionList();
                updateRecordingInfo();
                info.innerText = `Updated action #${coordEditIndex + 1} to (${x}, ${y})`;
            }
            coordEditMode = false;
            coordEditIndex = -1;
            hideCoordMarker();
            container.classList.remove('recording');
            document.getElementById('mode-indicator').textContent = 'Interactive Mode';
        }
        
        async function saveRecording() {
            if (!currentRecording) {
                alert('No recording to save');
                return;
            }
            if (!currentFilename) {
                saveRecordingAs();
                return;
            }

            currentRecording.platform = (platformInput.value || currentRecording.platform || 'custom').trim();
            currentRecording.description = (descriptionInput.value || currentRecording.description || '').trim();
            
            try {
                const resp = await fetch('/recording/save', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        filename: currentFilename,
                        recording: currentRecording
                    })
                });
                if (resp.ok) {
                    hasUnsavedChanges = false;
                    updateUnsavedIndicator();
                    alert('Saved!');
                } else {
                    alert('Save failed');
                }
            } catch (err) {
                alert('Save error: ' + err);
            }
        }
        
        function saveRecordingAs() {
            if (!currentRecording) {
                alert('No recording to save');
                return;
            }
            const filename = prompt('Filename:', currentFilename || `recording_${Date.now()}.json`);
            if (filename) {
                currentFilename = filename.endsWith('.json') ? filename : filename + '.json';
                saveRecording();
                loadRecordingsList();
            }
        }
        
        async function testPlayback() {
            if (!currentRecording || !currentRecording.actions.length) {
                alert('No actions to play');
                return;
            }
            if (!confirm('Run playback? This will control the VM.')) return;
            
            playbackAborted = false;
            isPlayingBack = true;
            document.getElementById('btn-playback').style.display = 'none';
            document.getElementById('btn-abort').style.display = 'inline-block';
            
            try {
                const resp = await fetch('/recording/playback', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({actions: currentRecording.actions})
                });
                const data = await resp.json();
                if (data.success) {
                    const failed = data.results.filter(r => !r.success).length;
                    if (!playbackAborted) {
                        alert(`Playback complete! ${data.results.length} actions, ${failed} failed.`);
                    }
                } else {
                    alert('Playback error: ' + data.error);
                }
            } catch (err) {
                if (!playbackAborted) {
                    alert('Playback failed: ' + err);
                }
            } finally {
                isPlayingBack = false;
                document.getElementById('btn-playback').style.display = 'inline-block';
                document.getElementById('btn-abort').style.display = 'none';
            }
        }
        
        async function abortPlayback() {
            playbackAborted = true;
            try {
                await fetch('/recording/abort', { method: 'POST' });
                info.innerText = 'Playback aborted!';
            } catch (err) {
                console.error('Abort failed:', err);
            }
            isPlayingBack = false;
            document.getElementById('btn-playback').style.display = 'inline-block';
            document.getElementById('btn-abort').style.display = 'none';
        }
        
        // Override click handler for recording and coord edit
        img.addEventListener('click', async (e) => {
            const coords = getCoords(e);
            
            // Handle coord edit mode - intercept click to update coordinates
            if (coordEditMode) {
                e.preventDefault();
                e.stopPropagation();
                applyCoordEdit(coords.x, coords.y);
                return;
            }
            
            if (isRecording) {
                recordAction({
                    type: 'click',
                    x: coords.x,
                    y: coords.y,
                    button: 'left',
                    description: ''
                });
            }
        });

        img.addEventListener('contextmenu', async (e) => {
            if (isRecording) {
                const coords = getCoords(e);
                recordAction({
                    type: 'right_click',
                    x: coords.x,
                    y: coords.y,
                    button: 'right',
                    description: ''
                });
            }
        });
        
        // Override keyboard handler for recording and coord edit cancel
        container.addEventListener('keydown', async (e) => {
            // ESC cancels coord edit mode
            if (e.key === 'Escape' && coordEditMode) {
                e.preventDefault();
                cancelCoordEdit();
                return;
            }
            
            if (isRecording) {
                const action = {
                    type: 'key',
                    key: e.key,
                    ctrl: e.ctrlKey,
                    shift: e.shiftKey,
                    description: ''
                };
                recordAction(action);
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

@app.route('/snapshot')
def snapshot():
    img = get_latest_frame()
    if img is None:
        return jsonify({"error": "No frame"}), 503
    path = f"/tmp/vnc_snapshot_{int(time.time())}.png"
    img.save(path)
    return jsonify({"path": path})

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

# =====================================================
# RECORDING & WORKFLOW EDITOR API ENDPOINTS
# =====================================================

RECORDINGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'recordings')

# Playback abort flag
playback_abort_flag = False

# Main automation pause flag - shared file-based for cross-process communication
PAUSE_FLAG_PATH = "/tmp/brain_pause_flag"

def is_main_paused():
    """Check if main automation is paused."""
    return os.path.exists(PAUSE_FLAG_PATH)

def set_main_paused(paused: bool):
    """Set the main automation pause state."""
    if paused:
        with open(PAUSE_FLAG_PATH, 'w') as f:
            f.write(str(time.time()))
    else:
        if os.path.exists(PAUSE_FLAG_PATH):
            os.remove(PAUSE_FLAG_PATH)

@app.route('/recording/list', methods=['GET'])
def list_recordings():
    """List all JSON recordings."""
    try:
        recordings = []
        if os.path.exists(RECORDINGS_DIR):
            for f in os.listdir(RECORDINGS_DIR):
                if f.endswith('.json'):
                    filepath = os.path.join(RECORDINGS_DIR, f)
                    try:
                        with open(filepath, 'r') as fp:
                            data = json.load(fp)
                            recordings.append({
                                'filename': f,
                                'platform': data.get('platform', 'unknown'),
                                'action_count': len(data.get('actions', [])),
                                'created': data.get('created', 'unknown')
                            })
                    except:
                        recordings.append({'filename': f, 'platform': 'error', 'action_count': 0})
        return jsonify({'recordings': recordings})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recording/load/<filename>', methods=['GET'])
def load_recording(filename):
    """Load a recording for editing."""
    try:
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'Recording not found'}), 404
        with open(filepath, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recording/save', methods=['POST'])
def save_recording():
    """Save/overwrite a recording."""
    try:
        data = request.json
        filename = data.get('filename')
        recording = data.get('recording')
        
        if not filename or not recording:
            return jsonify({'error': 'Missing filename or recording data'}), 400
        
        # Ensure recordings dir exists
        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        
        filepath = os.path.join(RECORDINGS_DIR, filename)
        with open(filepath, 'w') as f:
            json.dump(recording, f, indent=2)
        
        return jsonify({'success': True, 'path': filepath})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recording/delete/<filename>', methods=['DELETE'])
def delete_recording(filename):
    """Delete a recording."""
    try:
        filepath = os.path.join(RECORDINGS_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': 'Recording not found'}), 404
        os.remove(filepath)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/recording/abort', methods=['POST'])
def abort_playback():
    """Abort playback."""
    global playback_abort_flag
    playback_abort_flag = True
    logger.info("Playback abort requested")
    return jsonify({'success': True})

@app.route('/main/pause', methods=['POST'])
def pause_main():
    """Pause the main automation (orchestrator)."""
    set_main_paused(True)
    logger.info("Main automation PAUSED via web UI")
    return jsonify({'success': True, 'paused': True})

@app.route('/main/resume', methods=['POST'])
def resume_main():
    """Resume the main automation (orchestrator)."""
    set_main_paused(False)
    logger.info("Main automation RESUMED via web UI")
    return jsonify({'success': True, 'paused': False})

@app.route('/main/status', methods=['GET'])
def main_status():
    """Check if main automation is paused."""
    paused = is_main_paused()
    return jsonify({'paused': paused})

@app.route('/recording/playback', methods=['POST'])
def playback_recording():
    """Execute all actions in a recording on the VM."""
    global playback_abort_flag
    playback_abort_flag = False
    
    try:
        data = request.json
        actions = data.get('actions', [])
        
        if not actions:
            return jsonify({'error': 'No actions to play'}), 400
        
        ctrl = get_input_controller()
        if not ctrl:
            return jsonify({'error': 'Input controller not available'}), 500
        
        results = []
        for i, action in enumerate(actions):
            # Check abort flag
            if playback_abort_flag:
                results.append({'index': i, 'type': 'aborted', 'success': False, 'error': 'Playback aborted'})
                break
            action_type = action.get('type')
            delay_before = action.get('delay_before_ms', 0) / 1000.0
            
            # Wait before action
            if delay_before > 0:
                time.sleep(delay_before)
            
            try:
                if action_type == 'click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click(action.get('button', 'left'))
                    results.append({'index': i, 'type': 'click', 'success': True})
                    
                elif action_type == 'double_click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('left')
                    time.sleep(0.1)
                    ctrl.click('left')
                    results.append({'index': i, 'type': 'double_click', 'success': True})

                elif action_type == 'right_click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('right')
                    results.append({'index': i, 'type': 'right_click', 'success': True})
                    
                elif action_type == 'wait':
                    delay_ms = action.get('delay_ms', 0)
                    time.sleep(delay_ms / 1000.0)
                    results.append({'index': i, 'type': 'wait', 'success': True})
                    
                elif action_type == 'key':
                    key = action.get('key', '')
                    ctrl_mod = action.get('ctrl', False)
                    shift_mod = action.get('shift', False)
                    
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
                    results.append({'index': i, 'type': 'key', 'success': True})

                elif action_type == 'paste':
                    ctrl.keyboard._send_key('ctrl', 'down')
                    time.sleep(0.05)
                    ctrl.keyboard._send_key('v', 'press')
                    time.sleep(0.05)
                    ctrl.keyboard._send_key('ctrl', 'up')
                    results.append({'index': i, 'type': 'paste', 'success': True})
                    
                elif action_type == 'type':
                    text = action.get('text', '')
                    for char in text:
                        ctrl.keyboard._send_key(char, 'press')
                        time.sleep(0.05)
                    results.append({'index': i, 'type': 'type', 'success': True})
                    
                elif action_type == 'scroll':
                    delta = action.get('delta', 0)
                    ctrl.scroll_raw(delta)
                    results.append({'index': i, 'type': 'scroll', 'success': True})

                elif action_type == 'wait_for_change':
                    timeout_ms = action.get('timeout_ms', 5000)
                    threshold = action.get('threshold', 10)
                    start = time.time()
                    last = get_latest_frame()
                    if last is None:
                        results.append({'index': i, 'type': 'wait_for_change', 'success': False, 'error': 'No frame'})
                        continue
                    last_np = np.array(last)
                    changed = False
                    while (time.time() - start) * 1000 < timeout_ms:
                        time.sleep(0.2)
                        current = get_latest_frame()
                        if current is None:
                            continue
                        cur_np = np.array(current)
                        if cur_np.shape != last_np.shape:
                            changed = True
                            break
                        diff = np.abs(cur_np.astype(np.int16) - last_np.astype(np.int16))
                        if diff.mean() > threshold:
                            changed = True
                            break
                    results.append({'index': i, 'type': 'wait_for_change', 'success': changed, 'error': None if changed else 'timeout'})
                    
                else:
                    results.append({'index': i, 'type': action_type, 'success': False, 'error': 'Unknown action type'})
                    
            except Exception as e:
                results.append({'index': i, 'type': action_type, 'success': False, 'error': str(e)})
        
        return jsonify({'success': True, 'results': results})
        
    except Exception as e:
        logger.error(f"Playback failed: {e}")
        return jsonify({'error': str(e)}), 500

capture_proc = None

def start_capture_process():
    """Start or restart the VNC capture process."""
    global capture_proc
    
    # Kill existing process if running
    if capture_proc is not None and capture_proc.is_alive():
        logger.info("Terminating existing capture process...")
        capture_proc.terminate()
        capture_proc.join(timeout=3)
        if capture_proc.is_alive():
            capture_proc.kill()
            capture_proc.join(timeout=2)
    
    # Clear old frame
    if os.path.exists(SHARED_FRAME_PATH):
        try:
            os.remove(SHARED_FRAME_PATH)
        except:
            pass
    
    # Start new process
    capture_proc = multiprocessing.Process(target=capture_process_func)
    capture_proc.daemon = True
    capture_proc.start()
    logger.info(f"Started new capture process (PID: {capture_proc.pid})")
    return capture_proc.pid

@app.route('/reconnect', methods=['POST'])
def reconnect_vnc():
    """Force reconnect to VNC server."""
    try:
        pid = start_capture_process()
        # Wait a bit for connection
        time.sleep(2)
        
        # Check if we got a frame
        has_frame = os.path.exists(SHARED_FRAME_PATH)
        return jsonify({
            'success': True, 
            'pid': pid,
            'has_frame': has_frame,
            'message': 'Reconnect initiated' + (' - receiving frames' if has_frame else ' - waiting for frames...')
        })
    except Exception as e:
        logger.error(f"Reconnect failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/vnc_status', methods=['GET'])
def vnc_status():
    """Check VNC connection status."""
    global capture_proc
    
    proc_alive = capture_proc is not None and capture_proc.is_alive()
    has_frame = os.path.exists(SHARED_FRAME_PATH)
    
    # Check frame freshness (if older than 5 seconds, likely stale)
    frame_fresh = False
    frame_age = None
    if has_frame:
        try:
            frame_age = time.time() - os.path.getmtime(SHARED_FRAME_PATH)
            frame_fresh = frame_age < 5.0
        except:
            pass
    
    return jsonify({
        'process_alive': proc_alive,
        'has_frame': has_frame,
        'frame_fresh': frame_fresh,
        'frame_age_seconds': round(frame_age, 1) if frame_age else None,
        'connected': proc_alive and has_frame and frame_fresh
    })

if __name__ == '__main__':
    # Start Capture Process
    start_capture_process()
    
    logger.info("Starting Interactive VNC Stream Server...")
    logger.info("Open http://localhost:5555")
    
    try:
        app.run(host='0.0.0.0', port=5555, threaded=True)
    finally:
        if capture_proc is not None and capture_proc.is_alive():
            capture_proc.terminate()
