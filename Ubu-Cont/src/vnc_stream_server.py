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
from pathlib import Path
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
            <div class="status">Streaming from {{ vnc_host }} | <span id="mode-indicator">Interactive Mode</span> | <a href="/runs/" style="color:#60a5fa;">Runs</a> | <a href="/heal/" style="color:#f59e0b;">Heal</a></div>
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
                    <button onclick="recordBaseline()" style="background:#7a4b1b;border-color:#a16b2b;" id="btn-baseline">Record Baseline</button>
                    <button onclick="abortPlayback()" class="danger" id="btn-abort" style="display:none">Abort</button>
                </div>
                <div style="font-size:0.7em;color:#9aa6b2;margin-top:4px;">
                    <a href="/runs/" target="_blank" style="color:#60a5fa;">View Runs Comparison</a>
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
            document.getElementById('btn-baseline').style.display = 'inline-block';
            document.getElementById('btn-abort').style.display = 'none';
        }
        
        async function recordBaseline() {
            if (!currentRecording || !currentRecording.actions.length) {
                alert('No actions to play');
                return;
            }
            if (!currentFilename) {
                alert('Please save the recording first');
                return;
            }
            if (!confirm('Record Baseline?\\n\\nThis will:\\n1. Run through the workflow\\n2. Capture 100x100 screenshots before each click\\n3. Save them as baseline images with crosshair\\n\\nThis will control the VM.')) return;
            
            playbackAborted = false;
            isPlayingBack = true;
            document.getElementById('btn-playback').style.display = 'none';
            document.getElementById('btn-baseline').style.display = 'none';
            document.getElementById('btn-abort').style.display = 'inline-block';
            info.innerText = 'Recording baselines...';
            
            const workflowName = currentFilename.replace('.json', '');
            
            try {
                const resp = await fetch('/validation/record-baseline', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        actions: currentRecording.actions,
                        workflow_name: workflowName
                    })
                });
                const data = await resp.json();
                if (data.success) {
                    if (!playbackAborted) {
                        alert('Baseline recording complete!\\n' + data.baselines_created + ' baselines captured with crosshairs.\\n\\nView them at /runs/');
                    }
                } else {
                    alert('Baseline recording error: ' + data.error);
                }
            } catch (err) {
                if (!playbackAborted) {
                    alert('Baseline recording failed: ' + err);
                }
            } finally {
                isPlayingBack = false;
                document.getElementById('btn-playback').style.display = 'inline-block';
                document.getElementById('btn-baseline').style.display = 'inline-block';
                document.getElementById('btn-abort').style.display = 'none';
                info.innerText = 'Baseline recording finished';
            }
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

# =====================================================
# VISUAL VALIDATION ENDPOINTS
# =====================================================

# Try to import validation modules (optional feature)
try:
    from validation.database import ValidationDatabase
    from validation.baseline_manager import BaselineManager
    VALIDATION_AVAILABLE = True
    VALIDATION_DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'workflow-validation', 'validation.db')
    os.makedirs(os.path.dirname(VALIDATION_DB_PATH), exist_ok=True)
    logger.info("Visual validation module loaded")
except ImportError as e:
    VALIDATION_AVAILABLE = False
    logger.warning(f"Visual validation not available: {e}")

def capture_screenshot_region(click_x: int, click_y: int, box_size: int = 100) -> bytes:
    """Capture a region around click coordinates with crosshair."""
    from PIL import Image, ImageDraw
    
    # Read current VNC frame
    if not os.path.exists(SHARED_FRAME_PATH):
        return None
    
    try:
        full_screen = Image.open(SHARED_FRAME_PATH).convert('RGB')
    except Exception as e:
        logger.error(f"Failed to load screen: {e}")
        return None
    
    half_box = box_size // 2
    screen_width, screen_height = full_screen.size
    
    # Calculate crop region
    left = max(0, click_x - half_box)
    top = max(0, click_y - half_box)
    right = min(screen_width, click_x + half_box)
    bottom = min(screen_height, click_y + half_box)
    
    region = full_screen.crop((left, top, right, bottom))
    
    # Pad if near edge
    if region.size != (box_size, box_size):
        padded = Image.new('RGB', (box_size, box_size), (0, 0, 0))
        paste_x = (box_size - region.size[0]) // 2
        paste_y = (box_size - region.size[1]) // 2
        padded.paste(region, (paste_x, paste_y))
        region = padded
    
    # Draw crosshair at click point
    draw = ImageDraw.Draw(region)
    rel_x = click_x - left
    rel_y = click_y - top
    
    # Adjust for padding if near edge
    if click_x < half_box:
        rel_x = half_box - (half_box - click_x)
    if click_y < half_box:
        rel_y = half_box - (half_box - click_y)
    
    crosshair_size = 8
    line_width = 2
    
    # White outline
    for offset in [-1, 0, 1]:
        draw.line([(rel_x - crosshair_size + offset, rel_y), (rel_x + crosshair_size + offset, rel_y)], fill='white', width=line_width + 2)
        draw.line([(rel_x, rel_y - crosshair_size + offset), (rel_x, rel_y + crosshair_size + offset)], fill='white', width=line_width + 2)
    
    # Red crosshair
    draw.line([(rel_x - crosshair_size, rel_y), (rel_x + crosshair_size, rel_y)], fill='red', width=line_width)
    draw.line([(rel_x, rel_y - crosshair_size), (rel_x, rel_y + crosshair_size)], fill='red', width=line_width)
    
    # Convert to PNG bytes
    buffer = io.BytesIO()
    region.save(buffer, format='PNG')
    return buffer.getvalue()

@app.route('/validation/record-baseline', methods=['POST'])
def record_baseline():
    """Run playback while capturing screenshots for baselines - mirrors playback_recording exactly."""
    global playback_abort_flag
    
    if not VALIDATION_AVAILABLE:
        return jsonify({'error': 'Validation module not available'}), 500
    
    playback_abort_flag = False
    
    try:
        data = request.json
        actions = data.get('actions', [])
        workflow_name = data.get('workflow_name', 'unknown')
        
        if not actions:
            return jsonify({'error': 'No actions provided'}), 400
        
        ctrl = get_input_controller()
        if not ctrl:
            return jsonify({'error': 'Input controller not available'}), 500
        
        # Count click actions
        click_actions = [a for a in actions if a.get('type') in ('click', 'right_click', 'double_click')]
        click_count = len(click_actions)
        
        # Initialize database and register workflow
        db = ValidationDatabase(VALIDATION_DB_PATH)
        workflow_id = db.register_workflow(
            name=workflow_name,
            json_path=f"recordings/{workflow_name}.json",
            platform=workflow_name.split('_')[0] if '_' in workflow_name else 'custom',
            total_actions=len(actions),
            click_count=click_count
        )
        
        baselines_created = 0
        click_index = 0
        
        for i, action in enumerate(actions):
            if playback_abort_flag:
                logger.info("Baseline recording aborted")
                break
            
            action_type = action.get('type')
            delay_before = action.get('delay_before_ms', 0) / 1000.0
            
            # Wait before action (same as playback)
            if delay_before > 0:
                time.sleep(delay_before)
            
            try:
                if action_type == 'click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    
                    # CAPTURE SCREENSHOT BEFORE CLICKING
                    screenshot_bytes = capture_screenshot_region(x, y)
                    if screenshot_bytes:
                        db.save_baseline(
                            workflow_id=workflow_id,
                            action_index=click_index,
                            action_type=action_type,
                            click_x=x,
                            click_y=y,
                            image_data=screenshot_bytes,
                            description=action.get('description', '')
                        )
                        baselines_created += 1
                        logger.info(f"Baseline {click_index}: captured at ({x}, {y})")
                    click_index += 1
                    
                    # Now click (same as playback)
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click(action.get('button', 'left'))
                    
                elif action_type == 'double_click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    
                    # CAPTURE SCREENSHOT BEFORE CLICKING
                    screenshot_bytes = capture_screenshot_region(x, y)
                    if screenshot_bytes:
                        db.save_baseline(
                            workflow_id=workflow_id,
                            action_index=click_index,
                            action_type=action_type,
                            click_x=x,
                            click_y=y,
                            image_data=screenshot_bytes,
                            description=action.get('description', '')
                        )
                        baselines_created += 1
                        logger.info(f"Baseline {click_index}: captured at ({x}, {y})")
                    click_index += 1
                    
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('left')
                    time.sleep(0.1)
                    ctrl.click('left')

                elif action_type == 'right_click':
                    x, y = action.get('x', 0), action.get('y', 0)
                    
                    # CAPTURE SCREENSHOT BEFORE CLICKING
                    screenshot_bytes = capture_screenshot_region(x, y)
                    if screenshot_bytes:
                        db.save_baseline(
                            workflow_id=workflow_id,
                            action_index=click_index,
                            action_type=action_type,
                            click_x=x,
                            click_y=y,
                            image_data=screenshot_bytes,
                            description=action.get('description', '')
                        )
                        baselines_created += 1
                        logger.info(f"Baseline {click_index}: captured at ({x}, {y})")
                    click_index += 1
                    
                    ctrl.move_to(x, y)
                    time.sleep(0.05)
                    ctrl.click('right')
                    
                elif action_type == 'wait':
                    delay_ms = action.get('delay_ms', 0)
                    time.sleep(delay_ms / 1000.0)
                    
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

                elif action_type == 'paste':
                    ctrl.keyboard._send_key('ctrl', 'down')
                    time.sleep(0.05)
                    ctrl.keyboard._send_key('v', 'press')
                    time.sleep(0.05)
                    ctrl.keyboard._send_key('ctrl', 'up')
                    
                elif action_type == 'type':
                    text = action.get('text', '')
                    for char in text:
                        ctrl.keyboard._send_key(char, 'press')
                        time.sleep(0.05)
                    
                elif action_type == 'scroll':
                    delta = action.get('delta', 0)
                    ctrl.scroll_raw(delta)

                elif action_type == 'wait_for_change':
                    timeout_ms = action.get('timeout_ms', 5000)
                    threshold = action.get('threshold', 10)
                    start = time.time()
                    last = get_latest_frame()
                    if last is not None:
                        last_np = np.array(last)
                        while (time.time() - start) * 1000 < timeout_ms:
                            time.sleep(0.2)
                            current = get_latest_frame()
                            if current is None:
                                continue
                            cur_np = np.array(current)
                            if cur_np.shape != last_np.shape:
                                break
                            diff = np.abs(cur_np.astype(np.int16) - last_np.astype(np.int16))
                            if diff.mean() > threshold:
                                break
                
                # Wait after action (same as original)
                delay_ms = action.get('delay_ms', 0)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
                    
            except Exception as e:
                logger.error(f"Baseline action {i} failed: {e}")
        
        return jsonify({
            'success': True,
            'baselines_created': baselines_created,
            'workflow_name': workflow_name
        })
        
    except Exception as e:
        logger.error(f"Record baseline failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/validation/status/<workflow_name>', methods=['GET'])
def validation_status(workflow_name):
    """Get validation status for a workflow."""
    if not VALIDATION_AVAILABLE:
        return jsonify({'error': 'Validation not available'})
    
    try:
        db = ValidationDatabase(VALIDATION_DB_PATH)
        
        # Get workflow info
        workflow = db.get_workflow(workflow_name)
        if not workflow:
            return jsonify({'error': 'Workflow not registered', 'baselines_count': 0, 'total_clicks': 0})
        
        workflow_id = workflow['id']
        
        # Get baselines count
        baselines = db.get_baselines(workflow_id)
        baselines_count = len(baselines)
        total_clicks = workflow.get('click_count', 0)
        
        # Get recent runs (simplified - just count from runs table)
        success_runs = 0
        failed_runs = 0
        
        coverage = (baselines_count / total_clicks * 100) if total_clicks > 0 else 0
        
        return jsonify({
            'workflow_name': workflow_name,
            'baselines_count': baselines_count,
            'total_clicks': total_clicks,
            'coverage_percent': coverage,
            'success_runs': success_runs,
            'failed_runs': failed_runs,
            'alerts': []
        })
    except Exception as e:
        logger.error(f"Validation status error: {e}")
        return jsonify({'error': str(e)})

@app.route('/validation/baseline/<workflow_name>/<int:action_index>', methods=['GET'])
def get_baseline_image(workflow_name, action_index):
    """Serve a baseline image."""
    if not VALIDATION_AVAILABLE:
        return "Validation not available", 404
    
    try:
        db = ValidationDatabase(VALIDATION_DB_PATH)
        workflow = db.get_workflow(workflow_name)
        if not workflow:
            return "Workflow not found", 404
        
        baselines = db.get_baselines(workflow['id'])
        
        for b in baselines:
            if b.get('action_index') == action_index:
                return Response(b['baseline_image'], mimetype='image/png')
        
        return "Baseline not found", 404
    except Exception as e:
        return str(e), 500

@app.route('/validation/runs/<workflow_name>', methods=['GET'])
def get_workflow_runs(workflow_name):
    """Get recent runs with screenshots for a workflow."""
    if not VALIDATION_AVAILABLE:
        return jsonify({'error': 'Validation not available'}), 500
    
    try:
        db = ValidationDatabase(VALIDATION_DB_PATH)
        workflow = db.get_workflow(workflow_name)
        if not workflow:
            return jsonify({'error': 'Workflow not found', 'runs': []})
        
        workflow_id = workflow['id']
        
        # Get recent runs
        with db._get_connection() as conn:
            runs = conn.execute('''
                SELECT id, post_id, status, started_at, completed_at
                FROM workflow_runs
                WHERE workflow_id = ?
                ORDER BY started_at DESC
                LIMIT 3
            ''', (workflow_id,)).fetchall()
            runs = [dict(r) for r in runs]
        
        # For each run, get screenshot action indices
        for run in runs:
            with db._get_connection() as conn:
                screenshots = conn.execute('''
                    SELECT action_index, click_x, click_y, baseline_match_score, is_match
                    FROM run_screenshots
                    WHERE run_id = ?
                    ORDER BY action_index
                ''', (run['id'],)).fetchall()
                run['screenshots'] = [dict(s) for s in screenshots]
        
        return jsonify({
            'workflow_name': workflow_name,
            'runs': runs
        })
    except Exception as e:
        logger.error(f"Get runs error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/validation/run-screenshot/<int:run_id>/<int:action_index>', methods=['GET'])
def get_run_screenshot(run_id, action_index):
    """Serve a screenshot from a specific run."""
    if not VALIDATION_AVAILABLE:
        return "Validation not available", 404
    
    try:
        db = ValidationDatabase(VALIDATION_DB_PATH)
        with db._get_connection() as conn:
            row = conn.execute('''
                SELECT captured_image FROM run_screenshots
                WHERE run_id = ? AND action_index = ?
            ''', (run_id, action_index)).fetchone()
        
        if row and row['captured_image']:
            return Response(row['captured_image'], mimetype='image/png')
        
        return "Screenshot not found", 404
    except Exception as e:
        return str(e), 500

@app.route('/runs/')
def runs_comparison_page():
    """Page showing baseline vs run comparison grid."""
    return render_template_string(RUNS_COMPARISON_HTML)

RUNS_COMPARISON_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Workflow Runs Comparison</title>
    <style>
        :root {
            --bg: #0a0f1a;
            --panel: #111827;
            --border: #1f2937;
            --text: #e5e7eb;
            --muted: #6b7280;
            --accent: #3b82f6;
            --success: #10b981;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; }
        body { margin: 0; padding: 20px; background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; }
        h1 { margin: 0 0 20px 0; font-size: 1.5em; }
        .controls { margin-bottom: 20px; display: flex; gap: 10px; align-items: center; }
        select { background: var(--panel); color: var(--text); border: 1px solid var(--border); padding: 8px 12px; border-radius: 6px; }
        .grid { display: grid; gap: 2px; background: var(--border); }
        .grid-header { display: contents; }
        .grid-header > div { background: var(--panel); padding: 10px; font-weight: 600; text-align: center; position: sticky; top: 0; }
        .grid-row { display: contents; }
        .grid-row > div { background: var(--bg); padding: 8px; display: flex; align-items: center; justify-content: center; }
        .action-info { flex-direction: column; text-align: center; font-size: 0.8em; }
        .action-info .idx { font-size: 1.2em; font-weight: bold; color: var(--accent); }
        .action-info .coords { color: var(--muted); }
        .screenshot { width: 100px; height: 100px; border: 2px solid var(--border); border-radius: 4px; object-fit: contain; background: #000; }
        .screenshot.match { border-color: var(--success); }
        .screenshot.mismatch { border-color: var(--danger); }
        .no-baseline { width: 100px; height: 100px; display: flex; align-items: center; justify-content: center; background: var(--panel); border-radius: 4px; color: var(--muted); font-size: 0.7em; }
        .match-pct { font-size: 0.7em; margin-top: 4px; }
        .match-pct.good { color: var(--success); }
        .match-pct.bad { color: var(--danger); }
        a { color: var(--accent); }
    </style>
</head>
<body>
    <h1>Workflow Runs Comparison</h1>
    <p><a href="/">&larr; Back to Editor</a></p>
    
    <div class="controls">
        <label>Workflow:</label>
        <select id="workflow-select" onchange="loadComparison()">
            <option value="">-- Select Workflow --</option>
        </select>
        <span id="status" style="color:var(--muted);font-size:0.9em;"></span>
    </div>
    
    <div id="grid-container"></div>
    
    <script>
        async function loadWorkflows() {
            const resp = await fetch('/recording/list');
            const data = await resp.json();
            const sel = document.getElementById('workflow-select');
            data.recordings.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r.filename.replace('.json', '');
                opt.textContent = r.filename;
                sel.appendChild(opt);
            });
        }
        
        async function loadComparison() {
            const workflow = document.getElementById('workflow-select').value;
            if (!workflow) return;
            
            document.getElementById('status').textContent = 'Loading...';
            
            try {
                // Get baseline status
                const statusResp = await fetch(`/validation/status/${workflow}`);
                const status = await statusResp.json();
                
                if (status.baselines_count === 0) {
                    document.getElementById('grid-container').innerHTML = '<p style="color:var(--muted)">No baselines recorded yet. Use "Record Baseline" in the editor.</p>';
                    document.getElementById('status').textContent = '';
                    return;
                }
                
                // Get recent runs
                const runsResp = await fetch(`/validation/runs/${workflow}`);
                const runsData = await runsResp.json();
                const runs = runsData.runs || [];
                
                // Build grid
                let html = '<div class="grid" style="grid-template-columns: 120px repeat(' + (1 + 3) + ', 120px);">';
                html += '<div class="grid-header"><div>Action</div><div>Baseline</div>';
                for (let r = 0; r < 3; r++) {
                    if (runs[r]) {
                        const runTime = runs[r].started_at ? runs[r].started_at.split('T')[1]?.substring(0,5) || '' : '';
                        const runStatus = runs[r].status || '';
                        html += `<div title="${runs[r].post_id || 'Run ' + (r+1)}">Run ${r+1}<br><small style="color:var(--muted)">${runTime} ${runStatus}</small></div>`;
                    } else {
                        html += `<div>Run ${r+1}</div>`;
                    }
                }
                html += '</div>';
                
                for (let i = 0; i < status.baselines_count; i++) {
                    html += '<div class="grid-row">';
                    html += `<div class="action-info"><span class="idx">#${i}</span></div>`;
                    html += `<div><img class="screenshot" src="/validation/baseline/${workflow}/${i}" onerror="this.parentElement.innerHTML='<div class=no-baseline>-</div>'"></div>`;
                    
                    // Add run screenshots
                    for (let r = 0; r < 3; r++) {
                        if (runs[r]) {
                            const screenshot = runs[r].screenshots?.find(s => s.action_index === i);
                            if (screenshot) {
                                const matchClass = screenshot.is_match === true ? 'match' : (screenshot.is_match === false ? 'mismatch' : '');
                                const matchPct = screenshot.baseline_match_score != null ? (screenshot.baseline_match_score * 100).toFixed(0) + '%' : '';
                                html += `<div style="flex-direction:column"><img class="screenshot ${matchClass}" src="/validation/run-screenshot/${runs[r].id}/${i}" onerror="this.parentElement.innerHTML='<div class=no-baseline>err</div>'">`;
                                if (matchPct) {
                                    const pctClass = screenshot.is_match ? 'good' : 'bad';
                                    html += `<span class="match-pct ${pctClass}">${matchPct}</span>`;
                                }
                                html += `</div>`;
                            } else {
                                html += '<div class="no-baseline">-</div>';
                            }
                        } else {
                            html += '<div class="no-baseline">-</div>';
                        }
                    }
                    html += '</div>';
                }
                
                html += '</div>';
                document.getElementById('grid-container').innerHTML = html;
                document.getElementById('status').textContent = `${status.baselines_count} baselines, ${runs.length} recent runs`;
                
            } catch (err) {
                document.getElementById('status').textContent = 'Error: ' + err;
                console.error(err);
            }
        }
        
        loadWorkflows();
    </script>
</body>
</html>
"""

# ============================================================================
# SELF-HEALING DASHBOARD
# ============================================================================

# Import healing store
try:
    # Try relative import first (when running from Ubu-Cont directory)
    from src.self_healing import get_healing_store, SIMILARITY_FAILURE_THRESHOLD, MAX_HEALING_ATTEMPTS, CONFIDENCE_THRESHOLD
    from src.self_healing.config import WORKFLOW_ACTION_DESCRIPTIONS
    HEALING_AVAILABLE = True
    logger.info("Self-healing module loaded successfully")
except ImportError:
    try:
        # Try as sibling module (when running from src directory)
        from self_healing import get_healing_store, SIMILARITY_FAILURE_THRESHOLD, MAX_HEALING_ATTEMPTS, CONFIDENCE_THRESHOLD
        from self_healing.config import WORKFLOW_ACTION_DESCRIPTIONS
        HEALING_AVAILABLE = True
        logger.info("Self-healing module loaded successfully (sibling import)")
    except ImportError as e:
        HEALING_AVAILABLE = False
        logger.warning(f"Self-healing module not available: {e}")
        def get_healing_store():
            return None
        SIMILARITY_FAILURE_THRESHOLD = 0.3
        MAX_HEALING_ATTEMPTS = 3
        CONFIDENCE_THRESHOLD = 0.7
        WORKFLOW_ACTION_DESCRIPTIONS = {}

@app.route('/heal/api/status')
def heal_api_status():
    """Get current healing system status."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available', 'available': False})
    
    store = get_healing_store()
    if not store:
        return jsonify({'error': 'Healing store not initialized', 'available': False})
    
    status = store.get_status()
    status['available'] = True
    status['config'] = {
        'similarity_threshold': SIMILARITY_FAILURE_THRESHOLD,
        'max_attempts': MAX_HEALING_ATTEMPTS,
        'confidence_threshold': CONFIDENCE_THRESHOLD
    }
    return jsonify(status)

@app.route('/heal/api/events')
def heal_api_events():
    """Get recent healing events."""
    if not HEALING_AVAILABLE:
        return jsonify({'events': []})
    
    store = get_healing_store()
    if not store:
        return jsonify({'events': []})
    
    limit = request.args.get('limit', 50, type=int)
    return jsonify({'events': store.get_events(limit)})

@app.route('/heal/api/toggle', methods=['POST'])
def heal_api_toggle():
    """Enable/disable self-healing."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available'}), 400
    
    store = get_healing_store()
    if not store:
        return jsonify({'error': 'Healing store not initialized'}), 400
    
    data = request.json or {}
    enabled = data.get('enabled', not store.enabled)
    store.enabled = enabled
    
    return jsonify({'enabled': store.enabled})

@app.route('/heal/api/clear', methods=['POST'])
def heal_api_clear():
    """Clear healing history."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available'}), 400
    
    store = get_healing_store()
    if store:
        store.clear_history()
    
    return jsonify({'success': True})

@app.route('/heal/api/descriptions')
def heal_api_descriptions():
    """Get action descriptions for all workflows."""
    if not HEALING_AVAILABLE:
        return jsonify({})
    
    return jsonify(WORKFLOW_ACTION_DESCRIPTIONS)

@app.route('/heal/api/logs')
def heal_api_logs():
    """Get live logs for monitoring."""
    if not HEALING_AVAILABLE:
        return jsonify({'logs': []})
    
    store = get_healing_store()
    if not store:
        return jsonify({'logs': []})
    
    since_id = request.args.get('since', 0, type=int)
    if since_id > 0:
        return jsonify({'logs': store.get_logs(since_id)})
    else:
        return jsonify({'logs': store.get_recent_logs(100)})

@app.route('/heal/api/scan/<workflow_name>', methods=['POST'])
def heal_api_scan(workflow_name):
    """Scan a workflow and identify clicks needing healing."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available'}), 400
    
    try:
        from self_healing.manual_heal import get_manual_healer
        healer = get_manual_healer()
        result = healer.scan_workflow(workflow_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/heal/api/heal/<workflow_name>', methods=['POST'])
def heal_api_heal(workflow_name):
    """Trigger healing for a workflow."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available'}), 400
    
    try:
        from self_healing.manual_heal import get_manual_healer
        healer = get_manual_healer()
        
        data = request.json or {}
        click_indices = data.get('click_indices')  # Optional: specific clicks to heal
        
        result = healer.heal_workflow(workflow_name, click_indices)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/heal/api/heal-click/<workflow_name>/<int:click_index>', methods=['POST'])
def heal_api_heal_click(workflow_name, click_index):
    """Heal a single specific click."""
    if not HEALING_AVAILABLE:
        return jsonify({'error': 'Self-healing not available'}), 400
    
    try:
        from self_healing.manual_heal import get_manual_healer
        healer = get_manual_healer()
        
        # Get click info and baseline
        clicks = healer.get_workflow_clicks(workflow_name)
        click = next((c for c in clicks if c['click_index'] == click_index), None)
        if not click:
            return jsonify({'error': f'Click {click_index} not found'}), 404
        
        baselines = healer.get_baselines(workflow_name)
        baseline = baselines.get(click_index)
        if not baseline:
            return jsonify({'error': f'No baseline for click {click_index}'}), 404
        
        current = healer.capture_current_screenshot(click['x'], click['y'])
        if not current:
            return jsonify({'error': 'Could not capture current screenshot'}), 500
        
        similarity = healer.compare_images(baseline, current)
        
        result = healer.heal_click(
            workflow_name=workflow_name,
            click_index=click_index,
            old_x=click['x'],
            old_y=click['y'],
            baseline=baseline,
            current=current,
            similarity=similarity
        )
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/heal/api/workflows')
def heal_api_workflows():
    """Get list of available workflows."""
    workflows = []
    # __file__ is src/vnc_stream_server.py, so parent.parent is Ubu-Cont
    recordings_dir = Path(__file__).resolve().parent.parent / 'recordings'
    if recordings_dir.exists():
        for f in recordings_dir.glob('*_default.json'):
            workflows.append(f.stem)
    return jsonify({'workflows': sorted(workflows)})

@app.route('/heal/')
def heal_dashboard():
    """Self-healing monitoring dashboard."""
    return render_template_string(HEAL_DASHBOARD_HTML)

HEAL_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Self-Healing Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        :root {
            --bg: #0a0f1a;
            --panel: #101828;
            --panel-2: #1a2744;
            --border: #1f2f4f;
            --text: #e2e8f0;
            --muted: #64748b;
            --accent: #f59e0b;
            --accent-2: #10b981;
            --danger: #ef4444;
            --success: #22c55e;
            --warning: #eab308;
        }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg);
            color: var(--text);
            min-height: 100vh;
        }
        .header {
            background: var(--panel);
            border-bottom: 1px solid var(--border);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 1.4em;
            font-weight: 600;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .header h1::before {
            content: '🔧';
        }
        .header-links {
            display: flex;
            gap: 16px;
        }
        .header-links a {
            color: #60a5fa;
            text-decoration: none;
            font-size: 0.9em;
        }
        .header-links a:hover { text-decoration: underline; }
        
        .main {
            display: grid;
            grid-template-columns: 340px 1fr;
            gap: 20px;
            padding: 20px 24px;
            max-width: 1800px;
            margin: 0 auto;
        }
        
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
        }
        .card-header {
            background: var(--panel-2);
            padding: 12px 16px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .card-header h2 {
            font-size: 0.95em;
            font-weight: 600;
            color: var(--accent);
        }
        .card-body {
            padding: 16px;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            border-radius: 8px;
            font-weight: 500;
        }
        .status-indicator.enabled {
            background: rgba(34, 197, 94, 0.15);
            color: var(--success);
        }
        .status-indicator.disabled {
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
        }
        .status-indicator.unavailable {
            background: rgba(100, 116, 139, 0.15);
            color: var(--muted);
        }
        .status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        .enabled .status-dot { background: var(--success); }
        .disabled .status-dot { background: var(--danger); }
        .unavailable .status-dot { background: var(--muted); animation: none; }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }
        .stat-box {
            background: var(--panel-2);
            border-radius: 8px;
            padding: 12px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8em;
            font-weight: 700;
            color: var(--text);
        }
        .stat-label {
            font-size: 0.75em;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: 4px;
        }
        .stat-box.success .stat-value { color: var(--success); }
        .stat-box.failed .stat-value { color: var(--danger); }
        .stat-box.rate .stat-value { color: var(--accent); }
        
        .config-item {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 0.85em;
        }
        .config-item:last-child { border-bottom: none; }
        .config-label { color: var(--muted); }
        .config-value { color: var(--text); font-weight: 500; }
        
        .control-buttons {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        .btn {
            padding: 8px 16px;
            border-radius: 6px;
            border: none;
            font-size: 0.85em;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: var(--accent);
            color: #000;
        }
        .btn-primary:hover { background: #d97706; }
        .btn-success {
            background: var(--success);
            color: #000;
        }
        .btn-success:hover { background: #16a34a; }
        .btn-danger {
            background: var(--danger);
            color: #fff;
        }
        .btn-danger:hover { background: #dc2626; }
        .btn-secondary {
            background: var(--panel-2);
            color: var(--text);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover { background: var(--border); }
        
        .workflow-list {
            max-height: 200px;
            overflow-y: auto;
        }
        .workflow-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 12px;
            background: var(--panel-2);
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 0.85em;
        }
        .workflow-item:last-child { margin-bottom: 0; }
        .workflow-name { font-weight: 500; }
        .workflow-stats {
            display: flex;
            gap: 12px;
            font-size: 0.8em;
        }
        .workflow-stats span { color: var(--muted); }
        .workflow-stats .success { color: var(--success); }
        .workflow-stats .failed { color: var(--danger); }
        
        .right-panels {
            display: flex;
            flex-direction: column;
        }
        .events-panel {
            flex: 1;
        }
        @media (max-width: 1199px) {
            .main {
                grid-template-columns: 1fr;
            }
        }
        
        .events-list {
            max-height: 600px;
            overflow-y: auto;
        }
        .event-item {
            background: var(--panel-2);
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 12px;
            border-left: 4px solid var(--border);
        }
        .event-item:last-child { margin-bottom: 0; }
        .event-item.success { border-left-color: var(--success); }
        .event-item.failed { border-left-color: var(--danger); }
        .event-item.started, .event-item.ai_request, .event-item.ai_response {
            border-left-color: var(--warning);
        }
        
        .event-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .event-workflow {
            font-weight: 600;
            color: var(--accent);
        }
        .event-time {
            font-size: 0.75em;
            color: var(--muted);
        }
        .event-status {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.7em;
            font-weight: 600;
            text-transform: uppercase;
        }
        .event-status.success { background: rgba(34, 197, 94, 0.2); color: var(--success); }
        .event-status.failed { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .event-status.started { background: rgba(234, 179, 8, 0.2); color: var(--warning); }
        .event-status.ai_request { background: rgba(59, 130, 246, 0.2); color: #3b82f6; }
        .event-status.ai_response { background: rgba(168, 85, 247, 0.2); color: #a855f7; }
        
        .event-details {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 8px;
            font-size: 0.8em;
        }
        .event-detail {
            background: var(--panel);
            padding: 6px 10px;
            border-radius: 4px;
        }
        .event-detail-label {
            color: var(--muted);
            font-size: 0.85em;
        }
        .event-detail-value {
            color: var(--text);
            font-weight: 500;
        }
        
        .event-reasoning {
            margin-top: 8px;
            padding: 8px 10px;
            background: var(--panel);
            border-radius: 4px;
            font-size: 0.8em;
            color: var(--muted);
            font-style: italic;
        }
        
        .no-events {
            text-align: center;
            padding: 40px;
            color: var(--muted);
        }
        .no-events .icon {
            font-size: 3em;
            margin-bottom: 12px;
        }
        
        .active-healing {
            background: linear-gradient(45deg, rgba(234, 179, 8, 0.1), rgba(245, 158, 11, 0.1));
            border: 1px solid var(--warning);
            animation: activeGlow 2s infinite;
        }
        @keyframes activeGlow {
            0%, 100% { box-shadow: 0 0 5px rgba(245, 158, 11, 0.3); }
            50% { box-shadow: 0 0 20px rgba(245, 158, 11, 0.5); }
        }
        
        .refresh-indicator {
            font-size: 0.75em;
            color: var(--muted);
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Self-Healing Dashboard</h1>
        <div class="header-links">
            <a href="/">Live Control</a>
            <a href="/runs/">Runs</a>
            <span class="refresh-indicator">Auto-refresh: <span id="refresh-countdown">5</span>s</span>
        </div>
    </div>
    
    <div class="main">
        <div class="sidebar">
            <!-- System Status -->
            <div class="card">
                <div class="card-header">
                    <h2>System Status</h2>
                </div>
                <div class="card-body">
                    <div id="status-indicator" class="status-indicator unavailable">
                        <div class="status-dot"></div>
                        <span>Loading...</span>
                    </div>
                </div>
            </div>
            
            <!-- Statistics -->
            <div class="card">
                <div class="card-header">
                    <h2>Statistics</h2>
                </div>
                <div class="card-body">
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-value" id="stat-total">0</div>
                            <div class="stat-label">Total Attempts</div>
                        </div>
                        <div class="stat-box rate">
                            <div class="stat-value" id="stat-rate">0%</div>
                            <div class="stat-label">Success Rate</div>
                        </div>
                        <div class="stat-box success">
                            <div class="stat-value" id="stat-success">0</div>
                            <div class="stat-label">Successful</div>
                        </div>
                        <div class="stat-box failed">
                            <div class="stat-value" id="stat-failed">0</div>
                            <div class="stat-label">Failed</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Configuration -->
            <div class="card">
                <div class="card-header">
                    <h2>Configuration</h2>
                </div>
                <div class="card-body">
                    <div class="config-item">
                        <span class="config-label">Similarity Threshold</span>
                        <span class="config-value" id="config-threshold">-</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">Max Attempts</span>
                        <span class="config-value" id="config-attempts">-</span>
                    </div>
                    <div class="config-item">
                        <span class="config-label">AI Confidence</span>
                        <span class="config-value" id="config-confidence">-</span>
                    </div>
                </div>
            </div>
            
            <!-- Controls -->
            <div class="card">
                <div class="card-header">
                    <h2>Controls</h2>
                </div>
                <div class="card-body">
                    <div class="control-buttons">
                        <button class="btn btn-success" id="btn-enable" onclick="toggleHealing(true)">Enable</button>
                        <button class="btn btn-danger" id="btn-disable" onclick="toggleHealing(false)">Disable</button>
                        <button class="btn btn-secondary" onclick="clearHistory()">Clear Logs</button>
                    </div>
                </div>
            </div>
            
            <!-- Manual Heal -->
            <div class="card" style="border-color: var(--accent);">
                <div class="card-header">
                    <h2>Manual Heal</h2>
                </div>
                <div class="card-body">
                    <div style="margin-bottom:12px;">
                        <label style="font-size:0.8em;color:var(--muted);display:block;margin-bottom:4px;">Workflow</label>
                        <select id="workflow-select" style="width:100%;padding:8px;background:var(--panel-2);border:1px solid var(--border);border-radius:6px;color:var(--text);">
                            <option value="">Select workflow...</option>
                        </select>
                    </div>
                    <div class="control-buttons">
                        <button class="btn btn-secondary" onclick="scanWorkflow()" id="btn-scan">Scan</button>
                        <button class="btn btn-primary" onclick="healWorkflow()" id="btn-heal">Heal All</button>
                    </div>
                    <div id="scan-results" style="margin-top:12px;font-size:0.85em;"></div>
                </div>
            </div>
            
            <!-- Workflows Stats -->
            <div class="card">
                <div class="card-header">
                    <h2>By Workflow</h2>
                </div>
                <div class="card-body">
                    <div class="workflow-list" id="workflow-list">
                        <div class="no-events">No workflow data</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="right-panels">
            <!-- Live Logs Panel -->
            <div class="card" style="margin-bottom:16px;">
                <div class="card-header">
                    <h2>Live Logs</h2>
                    <button class="btn btn-secondary" style="padding:4px 8px;font-size:0.75em;" onclick="clearLogs()">Clear</button>
                </div>
                <div class="card-body" style="padding:0;">
                    <div id="live-logs" style="height:250px;overflow-y:auto;font-family:monospace;font-size:0.75em;background:#000;padding:8px;">
                        <div style="color:var(--muted);">Waiting for events...</div>
                    </div>
                </div>
            </div>
            
            <!-- Events Panel -->
            <div class="card events-panel">
                <div class="card-header">
                    <h2>Healing Events</h2>
                    <span id="active-count" style="color:var(--warning);font-size:0.85em;"></span>
                </div>
                <div class="card-body">
                    <div class="events-list" id="events-list">
                        <div class="no-events">
                            <div class="icon">🔧</div>
                            <div>No healing events yet</div>
                            <div style="font-size:0.85em;margin-top:8px;">Use Manual Heal to test the system</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let refreshInterval;
        let countdown = 5;
        
        function formatTime(isoString) {
            if (!isoString) return '-';
            const d = new Date(isoString);
            return d.toLocaleTimeString();
        }
        
        function formatCoords(coords) {
            if (!coords || !Array.isArray(coords)) return '-';
            return `(${coords[0]}, ${coords[1]})`;
        }
        
        async function fetchStatus() {
            try {
                const resp = await fetch('/heal/api/status');
                return await resp.json();
            } catch (e) {
                console.error('Failed to fetch status:', e);
                return null;
            }
        }
        
        function updateStatusIndicator(status) {
            const el = document.getElementById('status-indicator');
            if (!status || !status.available) {
                el.className = 'status-indicator unavailable';
                el.innerHTML = '<div class="status-dot"></div><span>Not Available</span>';
                return;
            }
            
            if (status.stats.enabled) {
                el.className = 'status-indicator enabled';
                el.innerHTML = '<div class="status-dot"></div><span>Active & Monitoring</span>';
            } else {
                el.className = 'status-indicator disabled';
                el.innerHTML = '<div class="status-dot"></div><span>Disabled</span>';
            }
            
            // Update button states
            document.getElementById('btn-enable').disabled = status.stats.enabled;
            document.getElementById('btn-disable').disabled = !status.stats.enabled;
        }
        
        function updateStats(status) {
            if (!status || !status.stats) return;
            
            const stats = status.stats;
            document.getElementById('stat-total').textContent = stats.total_attempts;
            document.getElementById('stat-success').textContent = stats.successful;
            document.getElementById('stat-failed').textContent = stats.failed;
            document.getElementById('stat-rate').textContent = stats.success_rate.toFixed(0) + '%';
            
            // Config
            if (status.config) {
                document.getElementById('config-threshold').textContent = (status.config.similarity_threshold * 100).toFixed(0) + '%';
                document.getElementById('config-attempts').textContent = status.config.max_attempts;
                document.getElementById('config-confidence').textContent = (status.config.confidence_threshold * 100).toFixed(0) + '%';
            }
            
            // Active count
            const activeEl = document.getElementById('active-count');
            if (stats.active_count > 0) {
                activeEl.textContent = `${stats.active_count} healing in progress...`;
            } else {
                activeEl.textContent = '';
            }
            
            // Workflows
            updateWorkflowList(stats.by_workflow);
        }
        
        function updateWorkflowList(byWorkflow) {
            const el = document.getElementById('workflow-list');
            if (!byWorkflow || Object.keys(byWorkflow).length === 0) {
                el.innerHTML = '<div class="no-events" style="padding:12px;">No workflow data yet</div>';
                return;
            }
            
            let html = '';
            for (const [name, data] of Object.entries(byWorkflow)) {
                const displayName = name.replace('_default', '').replace('_', ' ');
                html += `
                    <div class="workflow-item">
                        <span class="workflow-name">${displayName}</span>
                        <div class="workflow-stats">
                            <span class="success">${data.success} ✓</span>
                            <span class="failed">${data.failed} ✗</span>
                            <span>${data.attempts} total</span>
                        </div>
                    </div>
                `;
            }
            el.innerHTML = html;
        }
        
        function updateEvents(status) {
            const el = document.getElementById('events-list');
            
            // Combine active and recent
            const active = status.active || [];
            const recent = status.recent || [];
            
            if (active.length === 0 && recent.length === 0) {
                el.innerHTML = `
                    <div class="no-events">
                        <div class="icon">🔧</div>
                        <div>No healing events yet</div>
                        <div style="font-size:0.85em;margin-top:8px;">Events will appear here when the system attempts to heal failed clicks</div>
                    </div>
                `;
                return;
            }
            
            let html = '';
            
            // Active events first
            for (const event of active) {
                html += renderEvent(event, true);
            }
            
            // Recent events
            for (const event of recent) {
                // Skip if already shown as active
                if (active.find(a => a.id === event.id)) continue;
                html += renderEvent(event, false);
            }
            
            el.innerHTML = html;
        }
        
        function renderEvent(event, isActive) {
            const statusClass = event.status;
            const activeClass = isActive ? 'active-healing' : '';
            
            let detailsHtml = `
                <div class="event-detail">
                    <div class="event-detail-label">Click Index</div>
                    <div class="event-detail-value">#${event.click_index}</div>
                </div>
                <div class="event-detail">
                    <div class="event-detail-label">Similarity</div>
                    <div class="event-detail-value">${(event.similarity * 100).toFixed(1)}%</div>
                </div>
                <div class="event-detail">
                    <div class="event-detail-label">Old Coords</div>
                    <div class="event-detail-value">${formatCoords(event.old_coords)}</div>
                </div>
            `;
            
            if (event.new_coords) {
                detailsHtml += `
                    <div class="event-detail">
                        <div class="event-detail-label">New Coords</div>
                        <div class="event-detail-value" style="color:var(--success)">${formatCoords(event.new_coords)}</div>
                    </div>
                `;
            }
            
            if (event.ai_confidence > 0) {
                detailsHtml += `
                    <div class="event-detail">
                        <div class="event-detail-label">AI Confidence</div>
                        <div class="event-detail-value">${(event.ai_confidence * 100).toFixed(0)}%</div>
                    </div>
                `;
            }
            
            if (event.duration_ms > 0) {
                detailsHtml += `
                    <div class="event-detail">
                        <div class="event-detail-label">Duration</div>
                        <div class="event-detail-value">${(event.duration_ms / 1000).toFixed(1)}s</div>
                    </div>
                `;
            }
            
            let reasoningHtml = '';
            if (event.ai_reasoning) {
                reasoningHtml = `<div class="event-reasoning">${event.ai_reasoning}</div>`;
            }
            if (event.error_message) {
                reasoningHtml = `<div class="event-reasoning" style="color:var(--danger);">${event.error_message}</div>`;
            }
            
            return `
                <div class="event-item ${statusClass} ${activeClass}">
                    <div class="event-header">
                        <div>
                            <span class="event-workflow">${event.workflow.replace('_default', '')}</span>
                            <span class="event-status ${statusClass}">${event.status.replace('_', ' ')}</span>
                        </div>
                        <span class="event-time">${formatTime(event.timestamp)}</span>
                    </div>
                    <div class="event-details">
                        ${detailsHtml}
                    </div>
                    ${reasoningHtml}
                </div>
            `;
        }
        
        async function refreshData() {
            const status = await fetchStatus();
            if (status) {
                updateStatusIndicator(status);
                updateStats(status);
                updateEvents(status);
            }
        }
        
        async function toggleHealing(enabled) {
            try {
                await fetch('/heal/api/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({enabled})
                });
                refreshData();
            } catch (e) {
                console.error('Failed to toggle:', e);
            }
        }
        
        async function clearHistory() {
            try {
                await fetch('/heal/api/clear', {method: 'POST'});
                document.getElementById('live-logs').innerHTML = '<div style="color:var(--muted);">Logs cleared</div>';
                refreshData();
            } catch (e) {
                console.error('Failed to clear:', e);
            }
        }
        
        function clearLogs() {
            document.getElementById('live-logs').innerHTML = '<div style="color:var(--muted);">Logs cleared</div>';
            lastLogId = 0;
        }
        
        // Live Logs
        let lastLogId = 0;
        
        async function fetchLogs() {
            try {
                const resp = await fetch(`/heal/api/logs?since=${lastLogId}`);
                const data = await resp.json();
                if (data.logs && data.logs.length > 0) {
                    const logsEl = document.getElementById('live-logs');
                    for (const log of data.logs) {
                        if (log.id > lastLogId) {
                            lastLogId = log.id;
                            const color = log.level === 'ERROR' ? 'var(--danger)' : 
                                          log.level === 'WARN' ? 'var(--warning)' : 
                                          log.level === 'INFO' ? '#8be9fd' : 'var(--muted)';
                            const time = new Date(log.timestamp).toLocaleTimeString();
                            const line = document.createElement('div');
                            line.innerHTML = `<span style="color:var(--muted)">[${time}]</span> <span style="color:${color}">${log.message}</span>`;
                            logsEl.appendChild(line);
                            logsEl.scrollTop = logsEl.scrollHeight;
                        }
                    }
                }
            } catch (e) {
                console.error('Failed to fetch logs:', e);
            }
        }
        
        // Manual Heal Functions
        async function loadWorkflows() {
            try {
                const resp = await fetch('/heal/api/workflows');
                const data = await resp.json();
                const select = document.getElementById('workflow-select');
                select.innerHTML = '<option value="">Select workflow...</option>';
                for (const w of data.workflows || []) {
                    const opt = document.createElement('option');
                    opt.value = w;
                    opt.textContent = w.replace('_default', '');
                    select.appendChild(opt);
                }
            } catch (e) {
                console.error('Failed to load workflows:', e);
            }
        }
        
        async function scanWorkflow() {
            const workflow = document.getElementById('workflow-select').value;
            if (!workflow) {
                alert('Select a workflow first');
                return;
            }
            
            const resultsEl = document.getElementById('scan-results');
            resultsEl.innerHTML = '<div style="color:var(--warning)">Scanning...</div>';
            document.getElementById('btn-scan').disabled = true;
            
            try {
                const resp = await fetch(`/heal/api/scan/${workflow}`, {method: 'POST'});
                const data = await resp.json();
                
                if (data.error) {
                    resultsEl.innerHTML = `<div style="color:var(--danger)">${data.error}</div>`;
                    return;
                }
                
                let html = `<div style="margin-bottom:8px;">
                    <strong>${data.total_clicks}</strong> clicks, 
                    <strong>${data.with_baselines}</strong> with baselines,
                    <strong style="color:${data.needs_healing > 0 ? 'var(--danger)' : 'var(--success)'}">${data.needs_healing}</strong> need healing
                </div>`;
                
                if (data.clicks) {
                    for (const c of data.clicks) {
                        const simPct = c.similarity != null ? (c.similarity * 100).toFixed(0) + '%' : '-';
                        const status = c.needs_healing ? '❌' : (c.has_baseline ? '✅' : '⚪');
                        const color = c.needs_healing ? 'var(--danger)' : (c.similarity > 0.7 ? 'var(--success)' : 'var(--warning)');
                        html += `<div style="padding:4px 0;border-bottom:1px solid var(--border);">
                            ${status} Click #${c.click_index}: <span style="color:${color}">${simPct}</span>
                            <span style="color:var(--muted);font-size:0.9em;">(${c.x}, ${c.y})</span>
                        </div>`;
                    }
                }
                
                resultsEl.innerHTML = html;
            } catch (e) {
                resultsEl.innerHTML = `<div style="color:var(--danger)">Error: ${e}</div>`;
            } finally {
                document.getElementById('btn-scan').disabled = false;
            }
        }
        
        async function healWorkflow() {
            const workflow = document.getElementById('workflow-select').value;
            if (!workflow) {
                alert('Select a workflow first');
                return;
            }
            
            if (!confirm(`Start healing ${workflow}? Watch the Live Logs panel for progress.`)) {
                return;
            }
            
            const resultsEl = document.getElementById('scan-results');
            resultsEl.innerHTML = '<div style="color:var(--accent)">Healing in progress... Watch Live Logs!</div>';
            document.getElementById('btn-heal').disabled = true;
            
            try {
                const resp = await fetch(`/heal/api/heal/${workflow}`, {method: 'POST'});
                const data = await resp.json();
                
                if (data.error) {
                    resultsEl.innerHTML = `<div style="color:var(--danger)">${data.error}</div>`;
                    return;
                }
                
                let html = `<div style="padding:8px;background:var(--panel-2);border-radius:6px;">
                    <strong>Heal Complete!</strong><br>
                    Healed: <span style="color:var(--success)">${data.healed}</span> | 
                    Failed: <span style="color:var(--danger)">${data.failed}</span>
                </div>`;
                
                resultsEl.innerHTML = html;
                refreshData();
            } catch (e) {
                resultsEl.innerHTML = `<div style="color:var(--danger)">Error: ${e}</div>`;
            } finally {
                document.getElementById('btn-heal').disabled = false;
            }
        }
        
        function startAutoRefresh() {
            countdown = 5;
            document.getElementById('refresh-countdown').textContent = countdown;
            
            if (refreshInterval) clearInterval(refreshInterval);
            
            refreshInterval = setInterval(() => {
                countdown--;
                document.getElementById('refresh-countdown').textContent = countdown;
                
                if (countdown <= 0) {
                    countdown = 5;
                    refreshData();
                }
                
                // Also fetch logs more frequently
                fetchLogs();
            }, 1000);
        }
        
        // Initial load
        loadWorkflows();
        refreshData();
        fetchLogs();
        startAutoRefresh();
    </script>
</body>
</html>
"""

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
