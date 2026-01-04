import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestTitle")

URL = "https://social.sterlingcooley.com/test/skool/"

def main():
    logger.info("Starting Simple Title Typing Test...")
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    # 1. Focus Browser / Navigate
    logger.info("Attempting Navigation (Ctrl+L)...")
    input_ctrl.hotkey('ctrl', 'l')
    time.sleep(1.0)
    input_ctrl.type_text(URL, wpm=100)
    time.sleep(0.5)
    input_ctrl.hotkey('enter')
    
    logger.info("Waiting 5 seconds for page load...")
    time.sleep(5)

    # 2. Find Input
    logger.info("Looking for 'Write something' input...")
    target_coords = None
    try:
        # Using a very specific prompt
        target_coords = vision.find_element("The text input area that says 'Write something...'. It is usually a white box near the top of the feed.")
        logger.info(f"Vision found target at: {target_coords}")
    except Exception as e:
        logger.error(f"Vision failed: {e}")
        # Fallback to center logic if Vision fails? 
        # But user says 'nothing happens', so let's rely on finding it.
    
    if target_coords and target_coords != (0, 0):
        x, y = target_coords
        logger.info(f"Vision found target at: {x}, {y}")
    else:
        logger.warning("Vision failed or returned (0,0). FORCING BLIND CLICK at (640, 350) per user request.")
        x, y = 640, 350

    logger.info(f"Clicking at ({x}, {y})...")
    input_ctrl.move_to(x, y)
    time.sleep(0.5)
    input_ctrl.click('left')
    time.sleep(0.2)
    
    # Double check focus?
    input_ctrl.click('left')
    time.sleep(0.5)

    # 3. Type Title
    logger.info("Typing 'TEST TITLE'...")
    input_ctrl.type_text("TEST TITLE", wpm=40)
    
    logger.info("Done.")
    
    # 4. Capture result
    time.sleep(1)
    screen = vision.capture_screen()
    import cv2
    cv2.imwrite("VNC-screens/test_title_result_blind.png", screen)

if __name__ == "__main__":
    main()
