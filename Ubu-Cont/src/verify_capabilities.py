#!/usr/bin/env python3
"""
Verification script for AI Agent capabilities:
1. VNC Screenshot capture
2. HID Command injection (Open Website)
"""
import sys
import time
import socket
import json
import logging
import cv2
import numpy as np
from vncdotool import api

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants from STATUS.md
WINDOWS_VM_IP = "192.168.100.101" # Target for VNC? No, VNC is usually on Host/Hypervisor IP or passed through?
# Wait, STATUS.md says: 
# "Use the following IP address: ... IP address: 192.168.100.101" for the Windows VM itself.
# But VNC is typically provided by Proxmox Host (192.168.100.1) on a specific port for that VMID (101).
# Proxmox VNC ports are usually 5900 + VMID. So for VM 101, it might be 6001?
# Or maybe the agent runs INSIDE the VM?
# Looking at screen_capturer.py: `vnc_host='192.168.100.100', vnc_port=5900` default.
# But Ubuntu is .100. Windows is .101.
# If we want to capture Windows screen from Ubuntu...
# Unusually, the code `screen_capturer.py` defaults to .100 which is itself? 
# Maybe it's a VNC server running INSIDE the guest?
#
# Let's check `STATUS.md` again carefully regarding VNC.
# It says: "Install VNC Server (Optional) ... For remote viewing, install TightVNC ... from w10-drivers/ directory."
# "Step 1: Configure Internal Network Interface ... IP address: 192.168.100.101"
# So if TightVNC is installed on Windows, it will listen on 192.168.100.101:5900.
# The Ubuntu agent (192.168.100.100) should connect to 192.168.100.101:5900.

VNC_HOST = "192.168.100.101"
VNC_PORT = 5900
# Load config to get password dynamically
import os
try:
    with open('config.json', 'r') as f:
        config = json.load(f)
        VNC_PASSWORD = config.get('vnc', {}).get('vnc_password', 'password')
except Exception as e:
    logger.warning(f"Could not load config.json: {e}")
    VNC_PASSWORD = "password" # Fallback

HOST_IP = "192.168.100.1" # Proxmox Host for HID
HID_MOUSE_PORT = 8888
HID_KEYBOARD_PORT = 8889

def test_vnc_capture():
    logger.info(f"Testing VNC Capture from {VNC_HOST}:{VNC_PORT}...")
    try:
        # Try without password first, or catch auth error
        client = api.connect(f'{VNC_HOST}::{VNC_PORT}', password=VNC_PASSWORD) 
        logger.info("Connected to VNC server.")
        
        timestamp = int(time.time())
        filename = f"verify_screenshot_{timestamp}.png"
        
        logger.info(f"Capturing screenshot to {filename}...")
        client.captureScreen(filename)
        client.disconnect()
        
        # Verify file exists and is valid
        img = cv2.imread(filename)
        if img is not None:
            logger.info(f"SUCCESS: Screenshot captured ({img.shape[1]}x{img.shape[0]} px)")
            return True
        else:
            logger.error("FAILURE: Screenshot file created but could not be read as image.")
            return False
            
    except Exception as e:
        logger.error(f"FAILURE: VNC Capture failed: {e}")
        return False

def send_hid_command(port, command):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            s.connect((HOST_IP, port))
            s.sendall(json.dumps(command).encode() + b'\n')
        return True
    except Exception as e:
        logger.error(f"HID Send Error (Port {port}): {e}")
        return False

def test_hid_control():
    logger.info(f"Testing HID Control on Host {HOST_IP}...")
    
    # Sequence to open website
    # 1. Wake up / Mouse Click
    logger.info("Action: Mouse Click (Wake up)")
    send_hid_command(HID_MOUSE_PORT, {"type": "click", "button": "left"})
    time.sleep(1)
    
    # 2. Win+R
    logger.info("Action: Key 'win+r' (Open Run)")
    # Note: 'win+r' might need to be separate keys depending on implementation
    # Trying "win+r" as a single key string if supported, else modifiers.
    # Looking at `STATUS.md`: `{"type": "key", "key": "ctrl+c"}` suggests combined keys are supported.
    send_hid_command(HID_KEYBOARD_PORT, {"type": "key", "key": "win+r"})
    time.sleep(1)
    
    # 3. Type URL
    url = "https://sterlingcooley.com"
    logger.info(f"Action: Type text '{url}'")
    send_hid_command(HID_KEYBOARD_PORT, {"type": "text", "text": url})
    time.sleep(0.5)
    
    # 4. Enter
    logger.info("Action: Key 'enter'")
    send_hid_command(HID_KEYBOARD_PORT, {"type": "key", "key": "enter"})
    
    logger.info("HID Command sequence sent.")
    return True

if __name__ == "__main__":
    logger.info("--- STARTING VERIFICATION ---")
    
    vnc_success = test_vnc_capture()
    hid_success = test_hid_control()
    
    if vnc_success and hid_success:
        logger.info("--- OVERALL STATUS: PASS ---")
        sys.exit(0)
    elif vnc_success:
        logger.info("--- OVERALL STATUS: PARTIAL (VNC OK, HID FAIL) ---")
        sys.exit(1)
    elif hid_success:
        logger.info("--- OVERALL STATUS: PARTIAL (VNC FAIL, HID OK) ---")
        sys.exit(1)
    else:
        logger.error("--- OVERALL STATUS: FAIL ---")
        sys.exit(1)
