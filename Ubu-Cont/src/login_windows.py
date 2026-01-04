import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LoginWindows")

PASSWORD = "Pa$$word"
OUTPUT_FILE = "VNC-screens/login_success_verification.png"

def main():
    logger.info("Starting Windows Login Procedure...")
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    # 0. Dismiss Error Dialog (if present)
    logger.info("Dismissing Error Dialog info...")
    try:
        ok_btn = vision.find_element("The 'OK' button on the error dialog.")
        input_ctrl.move_to(ok_btn[0], ok_btn[1])
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(1.0)
    except:
        logger.info("No 'OK' button found, sending Enter/Space just in case.")
        input_ctrl.hotkey('enter')
        time.sleep(1.0)

    # 0. Pre-Check: Are we already logged in?
    logger.info("Checking if already logged in...")
    try:
        # Check for Desktop indicators or lack of Login Field
        # We'll try to find the password field. If NOT found, we assume maybe logged in or lock screen.
        # But let's look for "Desktop" or "Browser" first? 
        # Actually, finding the password field is the most specific signal for "Need to Login".
        pass 
    except:
        pass

    # 1. Locate Password Field
    logger.info("Locating password field via Vision...")
    password_field_found = False
    try:
        coords = vision.find_element("The password input field where I need to type the password.")
        target_x, target_y = coords
        logger.info(f"Targeting password field at ({target_x}, {target_y})")
        
        # Move and Click
        input_ctrl.move_to(target_x, target_y)
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(0.2)
        # Double click to ensure focus
        input_ctrl.click('left')
        time.sleep(0.5)
        password_field_found = True
        
    except Exception as e:
        logger.warning(f"Vision did NOT find password field: {e}")
        logger.info("Checking if we are already on Desktop...")
        # Capture screen check
        screen = vision.capture_screen()
        check = vision.analyze_screen("Are we already logged in (Desktop/Browser visible)? YES or NO", image_array=screen)
        if "YES" in check.upper():
            logger.info("Likely already logged in. Aborting login sequence.")
            cv2.imwrite(OUTPUT_FILE, screen)
            return
        else:
            logger.warning("Not logged in, but couldn't find password field. Is it the Lock Screen? Clicking center to wake.")
            input_ctrl.move_to(640, 400)
            input_ctrl.click('left')
            time.sleep(1.0)
            # Try finding again?
            try:
                 coords = vision.find_element("The password input field.")
                 input_ctrl.move_to(coords[0], coords[1])
                 input_ctrl.click('left')
                 password_field_found = True
            except:
                 logger.error("Still cannot find password field. Aborting.")
                 return

    if password_field_found:
        # 2. Strict Clear (Ctrl+A -> Delete)
        logger.info("Clearing field (Strict Ctrl+A -> Delete)...")
        
        # Ctrl+A
        input_ctrl.keyboard._send_key('ctrl', 'down')
        time.sleep(0.2) 
        input_ctrl.keyboard._send_key('a', 'press')
        time.sleep(0.2)
        input_ctrl.keyboard._send_key('ctrl', 'up')
        time.sleep(0.5)
        
        # Delete
        input_ctrl.keyboard._send_key('delete', 'press')
        time.sleep(0.2)

        # 3. Enter Password (Manual Type to avoid extra space)
        logger.info("Typing Password (No trailing space)...")
        for char in PASSWORD:
            # Check for special chars that need shift? 
            # Simpler to trust input_ctrl._send_key handles basic chars or use internal map
            # But input_ctrl.keyboard._send_key takes a 'key' name. 
            # For simple chars, we might need to be careful.
            # Let's rely on type_text but with a patched version or manual send
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
        
        time.sleep(0.5)
        
        # 4. Submit
        logger.info("Submitting...")
        input_ctrl.hotkey('enter')
        
    # 5. Verify
    logger.info("Waiting 10 seconds for Desktop...")
    time.sleep(10) # Give Windows time to welcome/load profile
    
    logger.info(f"Capturing verification screenshot to {OUTPUT_FILE}...")
    screen = vision.capture_screen()
    
    import cv2
    cv2.imwrite(OUTPUT_FILE, screen)
    
    # Optional Analysis
    state = vision.analyze_screen("Are we on the Windows Desktop? YES or NO.", image_array=screen)
    logger.info(f"Login Result (Vision): {state}")

if __name__ == "__main__":
    main()
