import time
import logging
import signal
import sys
import os

# Ensure src directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input'))

from playbook_executor import PlaybookExecutor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("MainPoster")

class SocialPosterAgent:
    def __init__(self):
        self.running = True
        self.executor = PlaybookExecutor()
        self.poll_interval = 300 # 5 minutes
        
        # Determine if we should poll recursively or just once/fast for testing
        # For this deployment, we default to 5 minutes, but check env
        if os.getenv('FAST_POLL'):
            self.poll_interval = 60
            
    def start(self):
        logger.info("Social Poster Agent Starting...")
        logger.info(f"Poll Interval: {self.poll_interval}s")
        
        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"Cycle failed: {e}")
            
            # Wait for next cycle
            logger.info(f"Sleeping for {self.poll_interval}s...")
            try:
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                self.stop()
                
    def run_cycle(self):
        logger.info("Checking for pending posts...")
        posts = self.executor.api.get_pending_posts()
        
        if not posts:
            logger.info("No pending posts.")
            return

        logger.info(f"Found {len(posts)} pending posts.")
        
        for post in posts:
            if not self.running: 
                break
                
            success = self.executor.execute_post(post)
            if success:
                logger.info(f"Post {post['id']} completed successfully.")
            else:
                logger.error(f"Post {post['id']} failed.")
            
            # Small delay between posts
            time.sleep(5)

    def stop(self, signum=None, frame=None):
        logger.info("Stopping agent...")
        self.running = False
        sys.exit(0)

if __name__ == "__main__":
    agent = SocialPosterAgent()
    signal.signal(signal.SIGINT, agent.stop)
    signal.signal(signal.SIGTERM, agent.stop)
    agent.start()
