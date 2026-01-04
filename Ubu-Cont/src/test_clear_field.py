import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestClear")

OUTPUT_FILE = "VNC-screens/capture_06_after_ctrl_a_del.png"

def main():
    logger.info("Starting Field Clear Test (Ctrl+A -> Del)...")
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    # 1. Locate Field
    logger.info("Locating password field via Vision...")
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
        
    except Exception as e:
        logger.warning(f"Vision find failed ({e}). Defaulting to center.")
        input_ctrl.move_to(640, 490)
        input_ctrl.click('left')

    # 2. Perform Clear
    logger.info("Sending Ctrl+A (strict sequence)...")
    # Explicit Key Down/Up as requested
    input_ctrl.keyboard._send_key('ctrl', 'down')
    time.sleep(0.2) 
    input_ctrl.keyboard._send_key('a', 'press')
    time.sleep(0.2)
    input_ctrl.keyboard._send_key('ctrl', 'up')
    time.sleep(0.5)
    
    logger.info("Sending Delete (PRESS)...")
    input_ctrl.keyboard._send_key('delete', 'press')
    time.sleep(0.2)
    
    # 3. Capture
    logger.info("Waiting 2 seconds...")
    time.sleep(2)
    
    OUTPUT_FILE = "VNC-screens/capture_07_strict_clear.png"
    logger.info(f"Capturing screen to {OUTPUT_FILE}...")
    screen = vision.capture_screen()
    
    import cv2
    cv2.imwrite(OUTPUT_FILE, screen)
    logger.info("Done.")

if __name__ == "__main__":
    main()
