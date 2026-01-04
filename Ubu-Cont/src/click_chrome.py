#!/usr/bin/env python3
"""
Click Chrome in taskbar - uses Vision API to find Chrome and clicks it.
"""
import sys
import time
import json
import socket
import base64
import requests
import cv2
from vncdotool import api

# Config
VNC_HOST = "192.168.100.101"
VNC_PORT = 5900
VNC_PASSWORD = "Pa$$word"
HOST_IP = "192.168.100.1"
HID_MOUSE_PORT = 8888

# Load API key
with open('config.json', 'r') as f:
    config = json.load(f)
    API_KEY = config['vision']['api_key']
    MODEL = config['vision']['model_name']

def capture_screen(filename):
    """Capture VNC screenshot with proper delays"""
    print(f"Capturing screen to {filename}...")
    client = api.connect(f'{VNC_HOST}::{VNC_PORT}', password=VNC_PASSWORD)
    time.sleep(3)
    client.refreshScreen()
    time.sleep(2)
    client.refreshScreen()
    time.sleep(1)
    client.captureScreen(filename)
    client.disconnect()
    
    img = cv2.imread(filename)
    if img is not None and img.mean() > 5:
        print(f"  Screenshot OK: {img.shape[1]}x{img.shape[0]}")
        return img.shape[1], img.shape[0]  # width, height
    else:
        print("  Screenshot appears black!")
        return None, None

def find_chrome_with_vision(image_path, width, height):
    """Use Vision API to find Chrome icon location"""
    print("Asking Vision AI to find Chrome icon...")
    
    with open(image_path, "rb") as f:
        img_base64 = base64.b64encode(f.read()).decode('utf-8')
    
    prompt = """
Look at this Windows desktop screenshot. Find the Google Chrome icon in the taskbar at the bottom.
Return a JSON object with:
{
  "found": true/false,
  "x": pixel x coordinate of center of Chrome icon (0 is left edge),
  "y": pixel y coordinate of center of Chrome icon (0 is top edge),
  "description": "brief description of what you see"
}
The screen resolution is """ + f"{width}x{height}" + """. Give absolute pixel coordinates.
"""
    
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]
            }],
            "response_format": {"type": "json_object"}
        },
        timeout=30
    )
    
    if response.status_code == 200:
        content = response.json()['choices'][0]['message']['content']
        print(f"  Vision response: {content[:200]}")
        data = json.loads(content)
        return data
    else:
        print(f"  Vision API error: {response.status_code}")
        return None

def click_at(x, y):
    """Send absolute mouse move and click to HID port"""
    print(f"Clicking at ({x}, {y}) using ABSOLUTE positioning...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((HOST_IP, HID_MOUSE_PORT))
        
        # Move to ABSOLUTE position (new command from STATUS.md update)
        sock.sendall(json.dumps({"type": "abs", "x": int(x), "y": int(y)}).encode() + b'\n')
        time.sleep(0.3)
        
        # Click
        sock.sendall(json.dumps({"type": "click", "button": "left"}).encode() + b'\n')
        
        sock.close()
        print("  Click sent!")
        return True
    except Exception as e:
        print(f"  Click error: {e}")
        return False

def main():
    print("=== CLICK CHROME IN TASKBAR ===\n")
    
    # Step 1: Capture screenshot
    width, height = capture_screen("chrome_find.png")
    if not width:
        print("Failed to capture screen!")
        return
    
    # Step 2: Find Chrome with Vision
    result = find_chrome_with_vision("chrome_find.png", width, height)
    if not result or not result.get('found'):
        print("Chrome not found by Vision AI!")
        print(f"Response: {result}")
        return
    
    x, y = result.get('x'), result.get('y')
    print(f"\nChrome found at: ({x}, {y})")
    print(f"Description: {result.get('description', 'N/A')}")
    
    # Step 3: Click it
    click_at(x, y)
    
    # Wait and take after screenshot
    print("\nWaiting 3 seconds for Chrome to open...")
    time.sleep(3)
    capture_screen("chrome_after.png")
    print("\n=== DONE ===")

if __name__ == "__main__":
    main()
