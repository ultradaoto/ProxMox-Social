import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ForceRelogin")

PASSWORD = "Pa$$word"
OUTPUT_FILE = "VNC-screens/relogin_verification.png"

def main():
    logger.info("Starting Force Relogin Sequence...")
    
    # Init Controllers
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    # 1. FORCE LOCK TO CLEAR STATE
    logger.info("Sending Win+L to LOCK workstation...")
    input_ctrl.hotkey('win', 'l')
    time.sleep(5) # Wait for lock animation
    
    # 2. Wake and Orient
    logger.info("Waking screen (Jiggle)...")
    input_ctrl.move_to(100, 100)
    time.sleep(0.5)
    input_ctrl.move_to(200, 200)
    time.sleep(2.0) # Wait for screen to wake
    
    # 3. Dismiss Lock Screen
    logger.info("Dismissing Lock Screen (Click & Enter)...")
    input_ctrl.click('left')
    time.sleep(1.0)
    input_ctrl.hotkey('enter')
    time.sleep(2.0) # Wait for Password Field animation
    
    # 4. Strict Clear (Ctrl+A -> Delete)
    logger.info("Clearing Password Field...")
    input_ctrl.hotkey('ctrl', 'a')
    time.sleep(0.5)
    input_ctrl.keyboard._send_key('delete', 'press')
    time.sleep(0.5)
    
    # 5. Type Password
    logger.info("Typing Password...")
    # Manual typing loop from login_windows.py logic
    for char in PASSWORD:
        if char == '$':
            input_ctrl.keyboard._send_key('shift', 'down')
            time.sleep(0.05)
            input_ctrl.keyboard._send_key('4', 'press')
            time.sleep(0.05)
            input_ctrl.keyboard._send_key('shift', 'up')
        elif char.isupper():
            input_ctrl.keyboard._send_key('shift', 'down')
            time.sleep(0.05)
            input_ctrl.keyboard._send_key(char.lower(), 'press')
            time.sleep(0.05)
            input_ctrl.keyboard._send_key('shift', 'up')
        else:
             input_ctrl.keyboard._send_key(char, 'press')
        time.sleep(0.1)
        
    time.sleep(1.0)
    
    # 6. Submit
    logger.info("Submitting (Enter)...")
    input_ctrl.hotkey('enter')
    
    # 7. Wait for Login
    logger.info("Waiting 10 seconds for login...")
    time.sleep(10)
    
    # 8. Capture Verification
    logger.info(f"Capturing verification screenshot to {OUTPUT_FILE}...")
    screen = vision.capture_screen()
    
    import cv2
    h, w, c = screen.shape
    logger.info(f"Captured Screenshot Resolution: {w}x{h}")
    
    cv2.imwrite(OUTPUT_FILE, screen)
    logger.info("Done.")

if __name__ == "__main__":
    main()
