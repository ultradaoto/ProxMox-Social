import sys
import os
import logging
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision_controller import VisionController
from input_controller import InputController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EnsureLogin")

PASSWORD = "Pa$$word"

def main():
    logger.info("Starting Auto-Login Procedure...")
    vision = VisionController()
    input_ctrl = InputController()
    input_ctrl.connect()
    
    # 1. Wake & Capture
    # We assume screen might be sleeping, so let's jiggle first just in case
    logger.info("Step 1: Waking screen...")
    input_ctrl.move_to(500, 500)
    time.sleep(1)
    
    screen = vision.capture_screen()
    
    # 2. Analyze State
    logger.info("Step 2: Checking state...")
    state = vision.analyze_screen(
        prompt="What is on the screen? Options: 'BLACK', 'LOCK_SCREEN' (time/date), 'LOGIN_PROMPT' (password field), 'DESKTOP' (icons/taskbar). Return ONE word.",
        image_array=screen
    )
    logger.info(f"Detected State: {state}")
    
    if "DESKTOP" in state.upper():
        logger.info("Already logged in.")
        return
        
    if "BLACK" in state.upper():
        logger.info("Screen is black, sending key to wake...")
        input_ctrl.hotkey('space')
        time.sleep(2)
        screen = vision.capture_screen()
        state = vision.analyze_screen("What is on the screen now? LOCK_SCREEN, LOGIN_PROMPT, DESKTOP", image_array=screen)
        logger.info(f"New State: {state}")

    # 3. Handle Lock Screen -> Login Prompt
    if "LOCK" in state.upper() or "TIME" in state.upper():
        logger.info("Lock screen detected. Clicking to show password field...")
        # Click center/bottom
        input_ctrl.click('left') 
        time.sleep(0.5)
        # Sometimes spacebar helps
        input_ctrl.hotkey('space')
        time.sleep(2.0)
        
        # Re-check
        screen = vision.capture_screen()
        state = vision.analyze_screen("Is the password field visible now? YES or NO", image_array=screen)
        logger.info(f"Password field visible? {state}")
    
    # 4. Login
    logger.info("Locating password field via Vision...")
    try:
        # Find exact coordinates
        coords = vision.find_element("The password input field where I need to type the password.")
        target_x, target_y = coords
        
        logger.info(f"Targeting password field at ({target_x}, {target_y})")
        input_ctrl.move_to(target_x, target_y)
        time.sleep(0.5)
        input_ctrl.click('left')
        time.sleep(0.5)
        # Double click to be sure we focus and maybe select text
        input_ctrl.click('left', count=2)
        time.sleep(0.5)
        
    except Exception as e:
        logger.warning(f"Vision find failed ({e}). Defaulting to center screen.")
        input_ctrl.move_to(640, 400) # Approx center for 1280x800 usually
        input_ctrl.click('left')
    
    logger.info("Clearing existing text...")
    
    logger.info("Clearing existing text (Brute Force: 30 Backspaces)...")
    
    # Brute force backspace
    for i in range(30):
        input_ctrl.hotkey('backspace')
        time.sleep(0.05) # fast but distinct

    logger.info("Typing password slowly...")
    # Slower typing to ensure no dropped keys
    input_ctrl.type_text(PASSWORD, wpm=30) 
    time.sleep(0.5)
    input_ctrl.hotkey('enter')
    
    logger.info("Waiting for desktop...")
    time.sleep(5.0)
    
    # 5. Verify
    screen = vision.capture_screen()
    final_check = vision.analyze_screen("Are we on the Windows Desktop now? YES or NO", image_array=screen)
    
    if "YES" in final_check.upper():
        logger.info("Login SUCCESS. Desktop detected.")
    else:
        logger.error(f"Login Verification FAILED. Vision says: {final_check}")

if __name__ == "__main__":
    main()
