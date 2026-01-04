import time
import sys
import os
import logging

# Ensure src directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from input_controller import InputController

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("KeyboardTest")

def main():
    logger.info("Starting Keyboard Stability Test...")
    
    try:
        ic = InputController()
        logger.info("Connecting to Input Controller...")
        ic.connect()
        logger.info("Connected.")
        
        duration = 60
        start_time = time.time()
        
        count = 0
        while time.time() - start_time < duration:
            count += 1
            logger.info(f"[{count}] Typing 'Hello World!'...")
            try:
                ic.type_text("Hello World!")
                time.sleep(0.2)
                ic.hotkey('enter')
                logger.info(f"[{count}] Sent successfully.")
            except Exception as e:
                logger.error(f"[{count}] Failed to send: {e}")
                # Optional: try to reconnect? 
                # ic.connect() 
            
            time.sleep(1)
            
        logger.info("Test Complete.")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()
