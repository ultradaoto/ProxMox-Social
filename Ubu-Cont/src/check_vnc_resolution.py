
import sys
import os
import time
import logging
from vncdotool import api as vnc_api

# Use existing config logic or hardcode for test
VNC_HOST = "192.168.100.101"
VNC_PORT = 5900
VNC_PASSWORD = "Pa$$word"

logging.basicConfig(level=logging.INFO)

def main():
    print(f"Connecting to {VNC_HOST}:{VNC_PORT}...")
    try:
        client = vnc_api.connect(f"{VNC_HOST}::{VNC_PORT}", password=VNC_PASSWORD)
        print("Connected.")
        
        # Refresh to get screen
        client.refreshScreen()
        
        if client.screen:
            w, h = client.screen.size
            print(f"Server Screen Resolution: {w}x{h}")
            if w == 1600 and h == 1200:
                print("✅ Resolution CORRECT: 1600x1200")
            else:
                print(f"❌ Resolution MISMATCH: Expected 1600x1200, got {w}x{h}")
                print("   Action required: Check Windows Display Settings.")
        else:
            print("❌ Could not get screen size.")
            
        client.disconnect()
    except Exception as e:
        print(f"❌ Connection failed: {e}")

if __name__ == "__main__":
    main()
