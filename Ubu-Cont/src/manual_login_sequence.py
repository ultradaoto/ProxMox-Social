
import sys
import os
import time
import logging
import cv2

# Adjust path to find sibling modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Constants
PASSWORD = "Pa$$word"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VNC-screens")
INITIAL_SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, "manual_login_step1_initial.png")
FINAL_SCREENSHOT_PATH = os.path.join(OUTPUT_DIR, "manual_login_step2_final.png")

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("ManualLogin")
    
    logger.info("Initializing controllers...")
    vision = VisionController()
    input_ctrl = InputController()
    input_ctrl.connect()

    # 1. Take a picture now
    logger.info("Step 1: Taking initial picture...")
    screen = vision.capture_screen()
    if screen is not None:
        cv2.imwrite(INITIAL_SCREENSHOT_PATH, screen)
        logger.info(f"Saved initial state to {INITIAL_SCREENSHOT_PATH}")
    else:
        logger.error("Failed to capture screen!")
        return

    # 2. Click where the password thing is
    logger.info("Step 2: Locating and clicking password field...")
    try:
        # We try to find the password field. If prompt is generic, VisionController might struggle if screen is blank/saver.
        # But user instruction is "Obviously we'll click where the password thing is".
        coords = vision.find_element("The password input field.")
        logger.info(f"Found password field at {coords}")
        
        input_ctrl.move_to(coords[0], coords[1])
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(0.2)
        # Double click to ensure focus
        input_ctrl.click('left')
        time.sleep(0.5)
    except Exception as e:
        logger.warning(f"Vision failed to find password field: {e}")
        logger.info("Fallback: Clicking center of screen (1920x1080 -> 960, 540)")
        input_ctrl.move_to(960, 540) 
        input_ctrl.click('left')
        time.sleep(1)

    # 3. Type the password
    logger.info("Step 3: Typing password...")
    try:
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
            
            # Use small random delay or fixed delay
            time.sleep(0.1)
    except Exception as e:
        logger.error(f"Error typing password: {e}")

    # 4. Hit enter
    logger.info("Step 4: Hitting Enter...")
    try:
        input_ctrl.keyboard._send_key('enter', 'press')
    except Exception as e:
        logger.error(f"Error sending Enter: {e}")

    # 5. Wait 10 seconds
    logger.info("Step 5: Waiting 10 seconds...")
    time.sleep(10)

    # 6. Take a picture of what you see
    logger.info("Step 6: Taking final picture...")
    screen = vision.capture_screen()
    if screen is not None:
        cv2.imwrite(FINAL_SCREENSHOT_PATH, screen)
        logger.info(f"Saved final state to {FINAL_SCREENSHOT_PATH}")
    else:
        logger.error("Failed to capture final screen!")

if __name__ == "__main__":
    main()
