cursor has a browser viewer and I could keep that window open and see it like a live feed through a webage I think that's a really good idea so can you have the Python create a local host live stream view of the VNC so that the Ubuntu machine can take screenshots from the live feed that's already on Ubuntu and allow me as well to see the Windows computer as well this would be like fantastic so powerful Let's make this work

This is a great idea - having a browser-based live view that also serves as the frame source for your AI. Let me build this for you.
VNC-to-Web Bridge with Frame Capture API
Create this file on your Ubuntu machine:
python#!/usr/bin/env python3
"""
VNC Live Stream Server
- Connects to Windows VNC
- Serves live MJPEG stream via web browser
- Provides /snapshot endpoint for AI frame capture
"""

from flask import Flask, Response, render_template_string, jsonify
from vncdotool import api as vnc_api
import threading
import time
import io
import numpy as np
from PIL import Image

app = Flask(__name__)

# Configuration
VNC_HOST = "192.168.100.XXX"  # Your Windows 10 VM IP
VNC_PORT = 5900
VNC_PASSWORD = "your_vnc_password"
TARGET_FPS = 10

# Global frame storage
current_frame = None
frame_lock = threading.Lock()
vnc_client = None
def vnc_capture_loop():
    """Continuously capture frames from VNC."""
    global current_frame, vnc_client
    
    while True:
        try:
            # Connect to VNC
            vnc_client = vnc_api.connect(f"{VNC_HOST}:{VNC_PORT}", password=VNC_PASSWORD)
            print(f"Connected to VNC at {VNC_HOST}:{VNC_PORT}")
            
            while True:
                # Capture screen
                screenshot = vnc_client.screen
                
                # Convert to PIL Image
                img = Image.fromarray(np.array(screenshot))
                
                with frame_lock:
                    current_frame = img.copy()
                
                time.sleep(1.0 / TARGET_FPS)
                
        except Exception as e:
            print(f"VNC Error: {e}, reconnecting in 5s...")
            time.sleep(5)


def generate_mjpeg():
    """Generate MJPEG stream for browser."""
    while True:
        with frame_lock:
            if current_frame is None:
                time.sleep(0.1)
                continue
            
            # Convert to JPEG
            buf = io.BytesIO()
            current_frame.save(buf, format='JPEG', quality=70)
            frame_bytes = buf.getvalue()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        time.sleep(1.0 / TARGET_FPS)


# HTML template for the viewer
VIEWER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Windows VNC Live View</title>
    <style>
        body { 
            margin: 0; 
            background: #1a1a2e; 
            display: flex; 
            flex-direction: column;
            align-items: center; 
            padding: 20px;
            font-family: Arial, sans-serif;
        }
        h1 { color: #00d4ff; margin-bottom: 10px; }
        .status { color: #00ff88; margin-bottom: 10px; }
        #stream { 
            border: 2px solid #00d4ff; 
            border-radius: 8px;
            max-width: 100%;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
        }
        .controls {
            margin-top: 15px;
            display: flex;
            gap: 10px;
        }
        button {
            background: #00d4ff;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover { background: #00a8cc; }
    </style>
</head>
<body>
    <h1>Windows 10 Live View</h1>
    <div class="status">Streaming from {{ vnc_host }} @ {{ fps }} FPS</div>
    <img id="stream" src="/stream" alt="VNC Stream">
    <div class="controls">
        <button onclick="snapshot()">Take Snapshot</button>
        <button onclick="location.reload()">Reconnect</button>
    </div>
    <script>
        async function snapshot() {
            const resp = await fetch('/snapshot');
            const data = await resp.json();
            alert('Snapshot saved: ' + data.path);
        }
    </script>
</body>
</html>

@app.route('/')
def index():
    """Main viewer page."""
    return render_template_string(VIEWER_HTML, vnc_host=VNC_HOST, fps=TARGET_FPS)


@app.route('/stream')
def stream():
    """MJPEG video stream endpoint."""
    return Response(
        generate_mjpeg(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )
@app.route('/snapshot')
def snapshot():
    """Get current frame as file (for AI processing)."""
    with frame_lock:
        if current_frame is None:
            return jsonify({"error": "No frame available"}), 503
        
        # Save to file
        path = f"/tmp/vnc_snapshot_{int(time.time())}.png"
        current_frame.save(path)
        
        return jsonify({
            "path": path,
            "width": current_frame.width,
            "height": current_frame.height,
            "timestamp": time.time()
        })
@app.route('/frame')
def frame():
    """Get current frame as raw JPEG (for direct AI use)."""
    with frame_lock:
        if current_frame is None:
            return "No frame", 503
        
        buf = io.BytesIO()
        current_frame.save(buf, format='JPEG', quality=95)
        buf.seek(0)
        
        return Response(buf.getvalue(), mimetype='image/jpeg')


@app.route('/frame/numpy')
def frame_numpy():
    """Get frame dimensions and raw bytes info for AI."""
    with frame_lock:
        if current_frame is None:
            return jsonify({"error": "No frame"}), 503
        
        arr = np.array(current_frame)
        return jsonify({
            "shape": arr.shape,
            "dtype": str(arr.dtype),
            "width": current_frame.width,
            "height": current_frame.height
        })

if __name__ == '__main__':
    # Start VNC capture thread
    vnc_thread = threading.Thread(target=vnc_capture_loop, daemon=True)
    vnc_thread.start()
    
    print("Starting VNC Live Stream Server...")
    print("Open http://localhost:5555 in your browser")
    print("AI can grab frames from http://localhost:5555/frame")
    
    app.run(host='0.0.0.0', port=5555, threaded=True)



    Install Dependencies
bashpip install flask pillow numpy vncdotool
Usage

Update the config at the top (VNC_HOST, VNC_PASSWORD)
Run it:

bashpython vnc_stream_server.py

Open in Cursor's browser or any browser: http://localhost:5555


For Your AI Script
Grab frames easily:
pythonimport requests
from PIL import Image
from io import BytesIO

def get_frame():
    """Get current frame from VNC stream."""
    response = requests.get("http://localhost:5555/frame")
    return Image.open(BytesIO(response.content))

def get_frame_numpy():
    """Get frame as numpy array for vision models."""
    import numpy as np
    img = get_frame()
    return np.array(img)

# Use it
frame = get_frame_numpy()
# Send to your Qwen2.5-VL model...


Now you can RDP into Ubuntu, open http://localhost:5555 in Cursor's browser panel, and watch Windows live while your AI grabs frames from the same feed. Want me to adjust the resolution, FPS, or add any other features?