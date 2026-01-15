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

# HTML with Interactive Click & Keyboard Handler
VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Windows VNC Live (Interactive)</title>
    <style>
        body { 
            margin: 0; 
            background: #1a1a2e; 
            display: flex; 
            flex-direction: column;
            align-items: center; 
            padding: 20px;
            font-family: 'Segoe UI', Arial, sans-serif;
            color: #dfe6e9;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; font-weight: 300; }
        .status { color: #00ff88; margin-bottom: 10px; font-size: 0.9em; }
        .container {
            position: relative;
            box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
            border-radius: 8px;
            overflow: hidden;
            border: 2px solid #00d4ff;
            outline: none; /* Focus outline */
        }
        .container:focus {
            border-color: #00ff88;
            box-shadow: 0 0 40px rgba(0, 255, 136, 0.3);
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
            gap: 15px;
        }
        button {
            background: #0984e3;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            color: white;
            transition: background 0.2s;
        }
        button:hover { background: #74b9ff; }
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
    </style>
</head>
<body>
    <h1>Windows 10 Live Control</h1>
    <div class="status">Streaming from {{ vnc_host }} | Interactive Mode Active</div>
    
    <div class="container" tabindex="0" id="view-container">
        <img id="stream" src="/stream" alt="VNC Stream">
    </div>

    <div class="info" id="coords">Click inside to type / Move mouse</div>
    <div class="instructions">Focus image to enable keyboard control</div>

    <div class="controls">
        <button onclick="sendHotkey(['ctrl', 'alt', 'delete'])" style="background: #d63031;">Ctrl+Alt+Del</button>
        <button onclick="snapshot()">Ref Snap</button>
        <button onclick="location.reload()">Reconnect</button>
    </div>

    <script>
        const TARGET_WIDTH = 1600;
        const TARGET_HEIGHT = 1200;
        const img = document.getElementById('stream');
        const container = document.getElementById('view-container');
        const info = document.getElementById('coords');

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
            info.innerText = `Pos: ${x}, ${y}`;
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
