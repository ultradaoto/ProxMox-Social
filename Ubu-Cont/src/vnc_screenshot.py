#!/usr/bin/env python3
"""
Improved VNC Screenshot - waits for framebuffer update before capture.
"""
import sys
import time
import json
import cv2
from vncdotool import api

# Load config
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        # Config has Ubuntu IP, but we need Windows for screenshot
        VNC_HOST = "192.168.100.101"  # Windows VM
        VNC_PORT = config['vnc']['vnc_port']
        VNC_PASSWORD = config['vnc']['vnc_password']
except Exception as e:
    print(f"Config error: {e}")
    VNC_HOST = "192.168.100.101"
    VNC_PORT = 5900
    VNC_PASSWORD = "Pa$$word"

OUTPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "vnc_screenshot.png"

print(f"Connecting to VNC at {VNC_HOST}:{VNC_PORT}...")

try:
    client = api.connect(f'{VNC_HOST}::{VNC_PORT}', password=VNC_PASSWORD)
    print("Connected! Requesting full framebuffer refresh...")
    
    # Request full screen refresh to ensure we get actual content
    client.refreshScreen()
    
    # Small delay to allow framebuffer to populate
    time.sleep(1.0)
    
    # Capture
    print(f"Capturing to {OUTPUT_FILE}...")
    client.captureScreen(OUTPUT_FILE)
    
    client.disconnect()
    
    # Verify the image isn't black
    img = cv2.imread(OUTPUT_FILE)
    if img is not None:
        # Check if image is mostly black (mean < 5)
        mean_val = img.mean()
        if mean_val < 5:
            print(f"WARNING: Image appears to be black (mean pixel value: {mean_val:.2f})")
            print("Possible causes: display is off, screensaver, or VNC issue")
        else:
            print(f"SUCCESS: Screenshot saved ({img.shape[1]}x{img.shape[0]} px, mean: {mean_val:.2f})")
    else:
        print("ERROR: Failed to read captured image")
        
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
