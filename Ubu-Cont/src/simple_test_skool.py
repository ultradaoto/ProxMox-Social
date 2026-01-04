import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController
from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleTest")

URL = "https://social.sterlingcooley.com/test/skool/"

def main():
    logger.info("Starting Simple Custom Skool Test...")
    input_ctrl = InputController()
    input_ctrl.connect()
    vision = VisionController()

    # 1. Ensure we are on the page / Refresh
    logger.info("Navigating/Refreshing...")
    # Navigate to be sure
    input_ctrl.hotkey('ctrl', 'l')
    time.sleep(1.0)
    input_ctrl.type_text(URL, wpm=100)
    time.sleep(0.5)
    input_ctrl.hotkey('enter')
    
    logger.info("Waiting 8 seconds for page load...")
    time.sleep(8)
    
    # Explicit Refresh as requested
    logger.info("Refreshing page (Ctrl+R)...")
    input_ctrl.hotkey('ctrl', 'r')
    time.sleep(5)

    # 2. Key Interaction Loop
    steps = [
        {
            "name": "Title",
            "prompt": "The input field for the Post Title. It might say 'Title' or be the top text box.",
            "text": "hello"
        },
        {
            "name": "Body",
            "prompt": "The text area for the Post content or body. It usually says 'Write something...'",
            "text": "hello"
        },
        {
            "name": "Post Button",
            "prompt": "The 'Post' button to submit the post.",
            "action": "click_only"
        }
    ]

    for step in steps:
        logger.info(f"--- Step: {step['name']} ---")
        try:
            coords = vision.find_element(step['prompt'])
            logger.info(f"Found {step['name']} at {coords}")
            
            if coords == (0,0):
                logger.warning(f"Vision returned (0,0) for {step['name']}. Trying anyway but suspicious.")
            
            # Click
            input_ctrl.move_to(coords[0], coords[1])
            time.sleep(0.5)
            input_ctrl.click('left')
            time.sleep(0.2)
            input_ctrl.click('left') # Double click to be sure of focus
            time.sleep(0.5)
            
            # Action
            if step.get('action') == 'click_only':
                logger.info(f"Clicked {step['name']}.")
            else:
                logger.info(f"Typing '{step['text']}'...")
                input_ctrl.type_text(step['text'], wpm=40)
            
            time.sleep(1.0)
            
        except Exception as e:
            logger.error(f"Failed step {step['name']}: {e}")

    logger.info("Test Complete. Capturing result...")
    time.sleep(2)
    screen = vision.capture_screen()
    import cv2
    cv2.imwrite("VNC-screens/simple_test_result.png", screen)

if __name__ == "__main__":
    main()
