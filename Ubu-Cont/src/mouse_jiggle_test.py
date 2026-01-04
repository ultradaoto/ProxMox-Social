#!/usr/bin/env python3
"""
Mouse Jiggle Test - Sends diagonal mouse movements to HID port for 3 minutes.
"""
import socket
import json
import time
import sys

# Configuration (from config.json)
HOST_IP = "192.168.100.1"
HID_MOUSE_PORT = 8888

JIGGLE_PIXELS = 10
DURATION_SECONDS = 180  # 3 minutes
INTERVAL = 1.0  # 1 second between jiggles

def send_mouse_move(sock, dx, dy):
    """Send relative mouse move command."""
    cmd = {
        "type": "move",
        "x": dx,
        "y": dy
    }
    try:
        sock.sendall(json.dumps(cmd).encode() + b'\n')
        return True
    except Exception as e:
        print(f"Send error: {e}")
        return False

def main():
    print(f"Connecting to HID Mouse at {HOST_IP}:{HID_MOUSE_PORT}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((HOST_IP, HID_MOUSE_PORT))
        print("Connected!")
    except Exception as e:
        print(f"Connection failed: {e}")
        sys.exit(1)
    
    print(f"Jiggling mouse diagonally by {JIGGLE_PIXELS}px for {DURATION_SECONDS}s...")
    print("Press Ctrl+C to stop early.\n")
    
    start_time = time.time()
    direction = 1  # 1 = down-right, -1 = up-left
    count = 0
    
    try:
        while time.time() - start_time < DURATION_SECONDS:
            dx = JIGGLE_PIXELS * direction
            dy = JIGGLE_PIXELS * direction
            
            if send_mouse_move(sock, dx, dy):
                count += 1
                elapsed = int(time.time() - start_time)
                remaining = DURATION_SECONDS - elapsed
                print(f"[{elapsed:3d}s] Moved ({dx:+3d}, {dy:+3d}) - {remaining}s remaining", end='\r')
            
            direction *= -1  # Alternate direction
            time.sleep(INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nStopped by user.")
    finally:
        sock.close()
        print(f"\nDone! Sent {count} jiggle commands.")

if __name__ == "__main__":
    main()
