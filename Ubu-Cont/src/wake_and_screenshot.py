#!/usr/bin/env python3
"""
Wake Windows and capture - sends HID to wake display before VNC capture.
"""
import sys
import time
import json
import socket
import cv2
from vncdotool import api

# Config
VNC_HOST = "192.168.100.101"  # Windows VM
VNC_PORT = 5900
VNC_PASSWORD = "Pa$$word"
HOST_IP = "192.168.100.1"
HID_MOUSE_PORT = 8888

OUTPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "wake_screenshot.png"

def send_mouse_jiggle():
    """Send mouse movement to wake display"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((HOST_IP, HID_MOUSE_PORT))
        
        # Move mouse to wake display
        for _ in range(3):
            sock.sendall(json.dumps({"type": "move", "x": 10, "y": 10}).encode() + b'\n')
            time.sleep(0.1)
            sock.sendall(json.dumps({"type": "move", "x": -10, "y": -10}).encode() + b'\n')
            time.sleep(0.1)
        
        sock.close()
        return True
    except Exception as e:
        print(f"HID wake error (non-fatal): {e}")
        return False

print("Step 1: Sending mouse jiggle to wake display...")
send_mouse_jiggle()

print("Step 2: Waiting 2 seconds for display to wake...")
time.sleep(2)

print(f"Step 3: Connecting to VNC at {VNC_HOST}:{VNC_PORT}...")
try:
    client = api.connect(f'{VNC_HOST}::{VNC_PORT}', password=VNC_PASSWORD)
    print("Connected! Waiting 3 seconds for connection to stabilize...")
    
    time.sleep(3)  # Critical: longer initial wait
    client.refreshScreen()
    time.sleep(2)
    client.refreshScreen()
    time.sleep(1)
    
    print(f"Step 4: Capturing to {OUTPUT_FILE}...")
    client.captureScreen(OUTPUT_FILE)
    client.disconnect()
    
    # Verify
    img = cv2.imread(OUTPUT_FILE)
    if img is not None:
        mean_val = img.mean()
        if mean_val < 5:
            print(f"⚠️  Image still black (mean: {mean_val:.2f})")
            print("   Try: Move mouse on Windows, disable screensaver, check TightVNC settings")
        else:
            print(f"✅ SUCCESS: {img.shape[1]}x{img.shape[0]} px, mean brightness: {mean_val:.2f}")
    else:
        print("❌ Failed to read image file")
        
except Exception as e:
    print(f"❌ VNC Error: {e}")
    sys.exit(1)
