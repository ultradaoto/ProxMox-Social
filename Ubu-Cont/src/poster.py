#!/usr/bin/env python3
"""
Visual Poster Agent
- Visually scrapes the dashboard for "OPEN URL" and "Copy Title/Body" buttons.
- Uses Vision AI to find elements and Input Controller to click/type.
"""

import sys
import os
import time
import logging
from typing import Tuple, Optional

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision_controller import VisionController
from input_controller import InputController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("VisualPoster")

class VisualPoster:
    def __init__(self):
        self.vision = VisionController()
        self.input = InputController()
        try:
            self.input.connect()
            logger.info("Input controller connected successfully.")
        except Exception as e:
            logger.error(f"Failed to connect input controller: {e}")
            sys.exit(1)

    def find_and_click(self, description: str, double_click: bool = False) -> bool:
        """Find an element by description and click it."""
        logger.info(f"Looking for: {description}")
        try:
            # VisionController.find_element returns (x, y)
            coords = self.vision.find_element(description)
            logger.info(f"Found at {coords}. Clicking...")
            
            # Move and Click
            self.input.move_to(coords[0], coords[1])
            time.sleep(0.5)
            self.input.click('left')
            
            if double_click:
                time.sleep(0.1)
                self.input.click('left')
                
            return True
        except Exception as e:
            logger.error(f"Failed to find/click '{description}': {e}")
            return False

    def run_posting_flow(self):
        """
        Main Posting Workflow:
        1. Find and Click 'Copy Title' on Dashboard
        2. Find and Click 'OPEN URL' on Dashboard (opens new tab/window)
        3. Wait for load
        4. Find 'Write something...' / Title Input -> Click -> Paste Title
        5. Switch back to Dashboard (Alt+Tab? or finding the dashboard tab?)
           - Strategy: Taking the simpler approach of assuming Alt+Tab works 
             or asking user to keep windows arranged.
           - User said "see the OPEN URL button, the copy title... and also see the page where it needs to post".
           - This implies both might be visible or we navigate. 
           - Let's try Alt+Tab switching strategy first as it is standard.
        """
        
        logger.info("=== STARTING VISUAL POSTING FLOW ===")
        
        # --- PHASE 1: COPY TITLE ---
        if not self.find_and_click("The blue button that says 'Copy title'"):
            logger.warning("Could not find 'Copy title'. Retrying once...")
            time.sleep(2)
            if not self.find_and_click("The blue button that says 'Copy title'"):
                logger.error("Aborting flow: Cannot find 'Copy title'")
                return

        logger.info("Title copied to clipboard.")
        time.sleep(1)

        # --- PHASE 2: OPEN POST PAGE ---
        # Note: If page is already open, clicking OPEN URL might open a duplicate or focus it.
        # Let's assume hitting OPEN URL is the safe way to get there.
        if not self.find_and_click("The green or blue button that says 'OPEN URL'"):
            logger.error("Aborting flow: Cannot find 'OPEN URL'")
            return
            
        logger.info("Opened URL. Waiting for page load...")
        time.sleep(5) # Wait for browser

        # --- PHASE 3: PASTE TITLE ---
        # We need to find the title input.
        logger.info("Looking for post input...")
        
        # Try finding the "Write something" trigger first (common in Skool)
        if self.find_and_click("The text area with placeholder 'Write something'", double_click=False):
            logger.info("Clicked 'Write something' entry...")
            time.sleep(2) # Wait for modal expansion
        
        # Now find the actual Title field
        if self.find_and_click("The input field labeled 'Title'"):
            logger.info("Focused Title field. Pasting...")
            time.sleep(0.5)
            self.input.hotkey('ctrl', 'v')
            time.sleep(1)
        else:
            logger.error("Could not find Title field to paste into.")
            # Continuing anyway in case it's auto-focused

        # --- PHASE 4: GET BODY (SWITCH BACK) ---
        logger.info("Switching back to Dashboard to copy body (Alt+Tab)...")
        self.input.hotkey('alt', 'tab')
        time.sleep(2) 
        
        if not self.find_and_click("The blue button that says 'Copy body'"):
             logger.error("Could not find 'Copy body' button.")
             return
             
        logger.info("Body copied to clipboard.")
        time.sleep(1)
        
        # --- PHASE 5: PASTE BODY (SWITCH FORWARD) ---
        logger.info("Switching back to Post Page (Alt+Tab)...")
        self.input.hotkey('alt', 'tab')
        time.sleep(2)
        
        # Find Body text area
        if self.find_and_click("The text area for the post content/body"):
            logger.info("Focused Body field. Pasting...")
            time.sleep(0.5)
            self.input.hotkey('ctrl', 'v')
            time.sleep(1)
        else:
             logger.error("Could not find Body field.")
             return

        # --- PHASE 6: GET IMAGE (SWITCH BACK) ---
        logger.info("Switching back to Dashboard to copy image (Alt+Tab)...")
        self.input.hotkey('alt', 'tab')
        time.sleep(2)
        
        if not self.find_and_click("The blue button that says 'Copy IMG' or 'Copy Image'"):
             logger.warning("Could not find 'Copy IMG' button. Skipping image.")
        else:
            logger.info("Copy IMG clicked (assuming path or image is on clipboard).")
            time.sleep(1)
            
            # --- PHASE 7: PASTE/UPLOAD IMAGE (SWITCH FORWARD) ---
            logger.info("Switching back to Post Page (Alt+Tab)...")
            self.input.hotkey('alt', 'tab')
            time.sleep(2)
            
            # Find Image Upload button
            # Usually strict "Image" or a paperclip or "Video"/"Attachment"
            if self.find_and_click("The 'Image', 'Photo', 'Upload' or paperclip button"):
                logger.info("Clicked Upload button. Waiting for dialog...")
                time.sleep(2)
                
                # Assume File Dialog is open. Paste (Path) and Enter.
                logger.info("Pasting path into File Dialog...")
                self.input.hotkey('ctrl', 'v')
                time.sleep(1)
                self.input.hotkey('enter')
                time.sleep(3) # Wait for upload
            else:
                logger.error("Could not find Image/Upload button.")

        # --- PHASE 8: POST ---
        logger.info("Ensuring focus and scrolling down to find 'Post' button...")
        
        # 1. Click safely in the middle-left to ensure browser focus (avoiding right side/scrollbar)
        # Using a fixed coordinate likely to be content area
        self.input.move_to(500, 500)
        self.input.click('left')
        time.sleep(0.5)

        # 2. Scroll down using keyboard (Arrow Down) for better control or PageDown
        # User requested "scroll down a little bit"
        logger.info("Sending Arrow Down keys...")
        for _ in range(5):
            self.input.hotkey('down')
            time.sleep(0.1)
        
        time.sleep(1)

        logger.info("Looking for 'Post' button...")
        if self.find_and_click("The 'Post' button to submit the post"):
            logger.info("Clicked Post! Success?")
        else:
            logger.error("Could not find Post button.")

        logger.info("=== FLOW COMPLETE ===")

    def run_continuous(self):
        """Looping mode (optional, for now just runs once per start)"""
        while True:
            self.run_posting_flow()
            logger.info("Waiting 60s before next scan...")
            time.sleep(60)

if __name__ == "__main__":
    agent = VisualPoster()
    # Run once for now, or loop if arguments say so
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        agent.run_continuous()
    else:
        agent.run_posting_flow()
