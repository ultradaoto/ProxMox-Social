import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ClearError")

OUTPUT_FILE = "VNC-screens/capture_04_after_enter.png"

def main():
    logger.info("Starting Clear Error Procedure...")
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    logger.info("Sending 'Enter' to dismiss dialog/submit bad text...")
    try:
        input_ctrl.hotkey('enter')
    except Exception as e:
        logger.error(f"Error sending enter: {e}")
        
    logger.info("Waiting 3 seconds...")
    time.sleep(3)
    
    logger.info(f"Capturing screen to {OUTPUT_FILE}...")
    screen = vision.capture_screen()
    
    import cv2
    cv2.imwrite(OUTPUT_FILE, screen)
    logger.info("Done.")

if __name__ == "__main__":
    main()
