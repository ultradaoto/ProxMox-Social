
import sys
import os
import time
import logging
import cv2

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from vision_controller import VisionController

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VerifyDualAccess")

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VNC-screens", "dual_access_test.png")

def main():
    logger.info("Initializing VisionController...")
    # This should use the new logic that attempts to fetch from localhost:5555 first
    vision = VisionController()
    
    logger.info("Capturing screen (should use local stream if available)...")
    start_time = time.time()
    
    # Capture
    img = vision.capture_screen(save_path=OUTPUT_FILE)
    
    duration = time.time() - start_time
    logger.info(f"Capture took {duration:.4f} seconds")
    
    if img is not None:
        logger.info(f"SUCCESS: Captured image {img.shape}")
        logger.info(f"Saved to {OUTPUT_FILE}")
    else:
        logger.error("Failed to capture image")

if __name__ == "__main__":
    main()
