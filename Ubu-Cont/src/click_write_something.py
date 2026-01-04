
import sys
import os
import time
import logging

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision_controller import VisionController
from input_controller import InputController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ClickWriteSomething")

def main():
    logger.info("Initializing controllers...")
    vision = VisionController()
    input_ctrl = InputController()
    input_ctrl.connect()

    target_description = "The input field with the placeholder text 'Write something'"
    
    logger.info(f"Looking for: {target_description}")
    
    try:
        # 1. Find the element
        start_time = time.time()
        coords = vision.find_element(target_description)
        duration = time.time() - start_time
        
        target_x, target_y = coords
        logger.info(f"Found target at ({target_x}, {target_y}) in {duration:.2f}s")
        
        # 2. Move and Click
        logger.info(f"Moving mouse to ({target_x}, {target_y})...")
        input_ctrl.move_to(target_x, target_y)
        time.sleep(0.5) 
        
        logger.info("Clicking...")
        input_ctrl.click('left')
        
        logger.info("Action Complete.")
        
    except Exception as e:
        logger.error(f"Failed to find or click element: {e}")
        # Capture debug screenshot
        vision.capture_screen("debug_write_something_failure.png")
        logger.info("Saved debug_write_something_failure.png")

if __name__ == "__main__":
    main()
