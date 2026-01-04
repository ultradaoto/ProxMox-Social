import sys
import os
import logging
import time

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from playbook_executor import PlaybookExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestWorkflow")

def main():
    logger.info("Starting Offline Skool Workflow Test...")
    
    pe = PlaybookExecutor()
    
    # Mock Post Data
    mock_post = {
        "id": "HELLO_WORLD_TEST",
        "platform": "skool_desci",
        "caption": "Hello World!\nHello World!", # Title \n Body
        "media": [] # No media for this simple test
    }
    
    logger.info(f"Executing with mock post: {mock_post['id']}")
    
    try:
        # We call the method directly to bypass platform check logic, or use execute_post
        result = pe.run_skool_playbook(mock_post)
        
        if result:
            logger.info("Test PASSED: Workflow returned True")
        else:
            logger.error("Test FAILED: Workflow returned False")
            
    except Exception as e:
        logger.error(f"Test CRASHED: {e}")

if __name__ == "__main__":
    main()
