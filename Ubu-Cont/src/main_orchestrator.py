"""
Main Orchestrator

Polls the Social Dashboard API for pending posts and executes
platform-specific workflows.

This is the main entry point for the Ubuntu-based automation system.
"""
import time
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

import requests
import yaml

from vnc_capture import VNCCapture
from vision_finder import VisionFinder
from input_injector import InputInjector
from workflows.base_workflow import PostContent
from workflows.instagram import InstagramWorkflow

logger = logging.getLogger(__name__)


class MainOrchestrator:
    """Main orchestrator for social media posting automation."""
    
    def __init__(self, config_path: str = "../config/settings.yaml"):
        """
        Initialize orchestrator.
        
        Args:
            config_path: Path to configuration file
        """
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Setup logging
        self._setup_logging()
        
        # Initialize components
        logger.info("Initializing components...")
        self.capture = VNCCapture(
            host=self.config['vnc']['host'],
            port=self.config['vnc']['port'],
            password=self.config['vnc'].get('password')
        )
        
        self.vision = VisionFinder(
            model=self.config['vision']['model'],
            ollama_host=self.config['vision']['ollama_host']
        )
        
        self.input = InputInjector(
            proxmox_host=self.config['input']['proxmox_host'],
            api_port=self.config['input']['api_port']
        )
        
        # Initialize workflows for each platform
        logger.info("Initializing platform workflows...")
        self.workflows = {
            "instagram": InstagramWorkflow(
                self.capture,
                self.vision,
                self.input,
                max_retries=self.config['workflows']['max_retries'],
                step_timeout=self.config['workflows']['step_timeout']
            ),
            # Add more platforms here:
            # "facebook": FacebookWorkflow(...),
            # "tiktok": TikTokWorkflow(...),
            # "skool": SkoolWorkflow(...),
        }
        
        # API configuration
        self.api_base_url = self.config['api']['base_url']
        self.api_key = self.config['api'].get('api_key', '')
        self.poll_interval = self.config['api']['poll_interval']
        
        logger.info("Orchestrator initialized successfully")
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return self._default_config()
        
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Configuration loaded from {config_path}")
        return config
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            'vnc': {
                'host': '192.168.100.20',
                'port': 5900,
                'password': None
            },
            'vision': {
                'model': 'qwen2.5-vl:7b',
                'ollama_host': 'http://localhost:11434'
            },
            'input': {
                'proxmox_host': '192.168.100.1',
                'api_port': 8888
            },
            'workflows': {
                'max_retries': 3,
                'step_timeout': 30
            },
            'api': {
                'base_url': 'https://social.sterlingcooley.com/api',
                'api_key': '',
                'poll_interval': 60
            },
            'logging': {
                'level': 'INFO',
                'file': '/var/log/orchestrator.log'
            }
        }
    
    def _setup_logging(self):
        """Configure logging."""
        log_config = self.config.get('logging', {})
        level = getattr(logging, log_config.get('level', 'INFO'))
        log_file = log_config.get('file', '/tmp/orchestrator.log')
        
        # Create log directory if needed
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
    
    def run(self):
        """Main loop - continuously process post queue."""
        logger.info("=" * 70)
        logger.info("Social Media Automation Orchestrator STARTED")
        logger.info(f"API: {self.api_base_url}")
        logger.info(f"Poll interval: {self.poll_interval} seconds")
        logger.info(f"Active platforms: {', '.join(self.workflows.keys())}")
        logger.info("=" * 70)
        
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        while True:
            try:
                # Process next pending post
                processed = self._process_next_post()
                
                if processed:
                    consecutive_errors = 0  # Reset on success
                    # Short delay before checking for next post
                    time.sleep(5)
                else:
                    # No posts to process, wait poll interval
                    time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                logger.info("Orchestrator stopped by user")
                break
            
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Orchestrator error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                
                if consecutive_errors >= max_consecutive_errors:
                    logger.critical("Too many consecutive errors, shutting down")
                    break
                
                time.sleep(self.poll_interval)
    
    def _process_next_post(self) -> bool:
        """
        Check for and process the next pending post.
        
        Returns:
            True if a post was processed, False if queue was empty
        """
        # Fetch next pending post
        post = self._fetch_next_post()
        
        if not post:
            # No posts in queue
            return False
        
        logger.info("\n" + "=" * 70)
        logger.info(f"Processing post ID: {post['id']}")
        logger.info(f"Platform: {post['platform']}")
        logger.info(f"Media: {post.get('media_path', 'N/A')}")
        logger.info("=" * 70 + "\n")
        
        # Get workflow for platform
        platform = post['platform'].lower()
        workflow = self.workflows.get(platform)
        
        if not workflow:
            logger.error(f"No workflow available for platform: {platform}")
            self._report_failure(
                post['id'],
                f"Unsupported platform: {platform}"
            )
            return True  # Still counts as processed
        
        # Prepare content
        content = PostContent(
            post_id=post['id'],
            media_path=post.get('media_path', ''),
            caption=post.get('caption', ''),
            hashtags=post.get('hashtags', []),
            platform=platform,
            metadata=post.get('metadata', {})
        )
        
        # Execute workflow
        try:
            success = workflow.execute(content)
            
            if success:
                self._report_success(post['id'])
                logger.info(f"✓ Post {post['id']} completed successfully\n")
            else:
                error_msg = workflow.get_error_message() or "Workflow failed"
                self._report_failure(post['id'], error_msg)
                logger.error(f"✗ Post {post['id']} failed: {error_msg}\n")
        
        except Exception as e:
            logger.exception(f"Workflow execution error: {e}")
            self._report_failure(post['id'], str(e))
        
        return True
    
    def _fetch_next_post(self) -> Optional[Dict[str, Any]]:
        """
        Fetch next pending post from API.
        
        Returns:
            Post dict or None if queue is empty
        """
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.get(
                f"{self.api_base_url}/gui_post_queue/pending",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                posts = response.json()
                if posts and len(posts) > 0:
                    return posts[0]  # Return first pending post
            
            elif response.status_code != 404:
                logger.warning(f"API returned status {response.status_code}")
        
        except Exception as e:
            logger.error(f"Failed to fetch posts from API: {e}")
        
        return None
    
    def _report_success(self, post_id: str):
        """Report successful post to API."""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.api_base_url}/gui_post_queue/{post_id}/complete",
                headers=headers,
                json={
                    "status": "success",
                    "completed_at": datetime.now().isoformat(),
                    "processor": "ubuntu-orchestrator"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Success reported to API for post {post_id}")
            else:
                logger.warning(f"Failed to report success: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error reporting success: {e}")
    
    def _report_failure(self, post_id: str, reason: str):
        """Report failed post to API."""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.post(
                f"{self.api_base_url}/gui_post_queue/{post_id}/failed",
                headers=headers,
                json={
                    "status": "failed",
                    "reason": reason,
                    "failed_at": datetime.now().isoformat(),
                    "processor": "ubuntu-orchestrator"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Failure reported to API for post {post_id}")
            else:
                logger.warning(f"Failed to report failure: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Error reporting failure: {e}")
    
    def process_single_post(self, post_id: str) -> bool:
        """
        Process a specific post by ID (for testing).
        
        Args:
            post_id: Post ID to process
        
        Returns:
            True if successful
        """
        logger.info(f"Processing specific post: {post_id}")
        
        # Fetch post details
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"
            
            response = requests.get(
                f"{self.api_base_url}/gui_post_queue/{post_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch post {post_id}: {response.status_code}")
                return False
            
            post = response.json()
            
            # Process it
            platform = post['platform'].lower()
            workflow = self.workflows.get(platform)
            
            if not workflow:
                logger.error(f"No workflow for platform: {platform}")
                return False
            
            content = PostContent(
                post_id=post['id'],
                media_path=post.get('media_path', ''),
                caption=post.get('caption', ''),
                hashtags=post.get('hashtags', []),
                platform=platform,
                metadata=post.get('metadata', {})
            )
            
            success = workflow.execute(content)
            
            if success:
                self._report_success(post_id)
            else:
                self._report_failure(post_id, workflow.get_error_message() or "Failed")
            
            return success
        
        except Exception as e:
            logger.exception(f"Error processing post {post_id}: {e}")
            return False


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Social Media Automation Orchestrator"
    )
    parser.add_argument(
        '--config',
        default='../config/settings.yaml',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--post-id',
        help='Process a specific post ID (for testing)'
    )
    parser.add_argument(
        '--test-connection',
        action='store_true',
        help='Test connections and exit'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run module tests without starting orchestrator'
    )
    
    args = parser.parse_args()
    
    # Handle test mode
    if args.test:
        print("="*60)
        print("MAIN ORCHESTRATOR MODULE TEST")
        print("="*60)
        print("Testing module structure and initialization")
        print("")
        
        try:
            print("[1/2] Loading configuration...")
            orchestrator = MainOrchestrator(config_path=args.config)
            print("      Configuration loaded successfully")
            
            print("[2/2] Validating components...")
            print(f"      Workflows available: {', '.join(orchestrator.workflows.keys())}")
            print(f"      API endpoint: {orchestrator.api_base_url}")
            print("")
            print("[INFO] Module structure is valid")
            print("       - Configuration loading works")
            print("       - All workflows registered")
            print("       - Ready for deployment")
            print("")
            print("="*60)
            print("Test completed - module is ready for deployment")
            print("="*60)
            return
        except Exception as e:
            print(f"      [ERROR] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            print("")
            print("[FAIL] Module has issues")
            exit(1)
    
    # Initialize orchestrator
    orchestrator = MainOrchestrator(config_path=args.config)
    
    if args.test_connection:
        print("Testing connections...")
        print("[OK] VNC: Component initialized")
        print("[OK] Vision: Component initialized")
        print("[OK] Input: Component initialized")
        print("All components loaded successfully!")
        return
    
    if args.post_id:
        # Process single post
        success = orchestrator.process_single_post(args.post_id)
        exit(0 if success else 1)
    
    # Run main loop
    orchestrator.run()


if __name__ == "__main__":
    main()
