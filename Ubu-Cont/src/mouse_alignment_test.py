
import sys
import os
import time
import logging

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AlignmentTest")

def main():
    logger.info("Initializing InputController...")
    input_ctrl = InputController()
    input_ctrl.connect()

    # Resolution 1600x1200
    WIDTH = 1600
    HEIGHT = 1200
    
    # 1. Exact Center
    center_x = WIDTH // 2
    center_y = HEIGHT // 2
    
    logger.info(f"Step 1: Clicking Center ({center_x}, {center_y})")
    input_ctrl.move_to(center_x, center_y)
    # Wait for move to complete (human-like movement might take a moment)
    time.sleep(1) 
    input_ctrl.click('left')
    
    logger.info("Waiting 5 seconds...")
    time.sleep(5)
    
    # 2. Four Corners
    corners = [
        (0, 0),             # Top-Left
        (WIDTH, 0),         # Top-Right
        (WIDTH, HEIGHT),    # Bottom-Right
        (0, HEIGHT)         # Bottom-Left
    ]
    
    for i, (x, y) in enumerate(corners):
        logger.info(f"Step 2.{i+1}: Clicking Corner ({x}, {y})")
        
        input_ctrl.move_to(x, y)
        time.sleep(1)
        input_ctrl.click('left')
        
        if i < len(corners) - 1:
            logger.info("Waiting 5 seconds...")
            time.sleep(5)
            
    logger.info("Alignment Test Complete.")

if __name__ == "__main__":
    main()
