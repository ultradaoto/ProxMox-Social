
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
logger = logging.getLogger("CopyPasteTest")

def main():
    logger.info("Initializing controllers...")
    vision = VisionController()
    input_ctrl = InputController()
    input_ctrl.connect()

    # --- STEP 1: CLICK COPY TITLE ---
    target_1 = "The blue button that says 'Copy title' on the right side of the screen"
    logger.info(f"Step 1: Looking for '{target_1}'")
    try:
        coords = vision.find_element(target_1)
        logger.info(f"Found at {coords}. Clicking...")
        input_ctrl.move_to(coords[0], coords[1])
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(1) # Wait for copy to happen
    except Exception as e:
        logger.error(f"Step 1 Failed: {e}")
        return

    # --- STEP 2: CLICK 'WRITE SOMETHING' ---
    target_2 = "The text area with placeholder 'Write something'"
    logger.info(f"Step 2: Looking for '{target_2}'")
    try:
        coords = vision.find_element(target_2)
        logger.info(f"Found at {coords}. Clicking...")
        input_ctrl.move_to(coords[0], coords[1])
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(2) # Wait for modal to open
    except Exception as e:
        logger.error(f"Step 2 Failed: {e}")
        # Continue? If modal doesn't open, next step will fail.
        return

    # --- STEP 3: CLICK 'TITLE' INPUT ---
    # The modal should be open now. We look for the "Title" field.
    target_3 = "The input field labeled 'Title'"
    logger.info(f"Step 3: Looking for '{target_3}'")
    try:
        # We might need to refresh what vision sees if the screen changed
        # find_element calls capture_screen internaly? 
        # Yes, VisionController.find_element calls capture_screen if image_path not provided.
        coords = vision.find_element(target_3)
        logger.info(f"Found at {coords}. Clicking...")
        input_ctrl.move_to(coords[0], coords[1])
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(1) # Wait for focus
    except Exception as e:
        logger.error(f"Step 3 Failed: {e}")
        return

    # --- STEP 4: PASTE (CTRL+V) ---
    logger.info("Step 4: Performing Ctrl+V...")
    # Using 'ctrl' as confirmed in our earlier fix
    input_ctrl.hotkey('ctrl', 'v')
    
    time.sleep(1)
    logger.info("Test Sequence Complete.")
    
    # Optional: Verify
    vision.capture_screen("test_copy_paste_result.png")
    logger.info("Saved result to test_copy_paste_result.png")

if __name__ == "__main__":
    main()
