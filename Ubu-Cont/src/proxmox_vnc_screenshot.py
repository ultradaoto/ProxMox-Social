#!/usr/bin/env python3
"""
Capture screenshot via Proxmox's built-in VNC (not TightVNC in guest).
Proxmox VNC port = 5900 + VMID
For Windows VM (VMID 101): port 6001
"""
import sys
import time
import cv2
from vncdotool import api

# Proxmox Host VNC for Windows VM (VMID 101)
PROXMOX_HOST = "192.168.100.1"
PROXMOX_VNC_PORT = 5901  # Proxmox usually uses 5900 + offset, try 5901 first
# Alternative: could be 6001 (5900 + 101)

OUTPUT_FILE = sys.argv[1] if len(sys.argv) > 1 else "proxmox_screenshot.png"

def try_vnc(host, port, password=None):
    """Try connecting to VNC at given host:port"""
    print(f"Trying {host}:{port}...")
    try:
        if password:
            client = api.connect(f'{host}::{port}', password=password)
        else:
            client = api.connect(f'{host}::{port}')
        
        print("Connected! Refreshing screen...")
        client.refreshScreen()
        time.sleep(1)
        
        print(f"Capturing to {OUTPUT_FILE}...")
        client.captureScreen(OUTPUT_FILE)
        client.disconnect()
        
        img = cv2.imread(OUTPUT_FILE)
        if img is not None:
            mean_val = img.mean()
            print(f"Result: {img.shape[1]}x{img.shape[0]} px, mean: {mean_val:.2f}")
            return mean_val > 5
        return False
    except Exception as e:
        print(f"Failed: {e}")
        return False

# Try different Proxmox VNC ports
ports_to_try = [5901, 6001, 5902, 5900]

for port in ports_to_try:
    if try_vnc(PROXMOX_HOST, port):
        print(f"\n✅ SUCCESS with port {port}!")
        break
else:
    print("\n❌ All ports failed or returned black images")
