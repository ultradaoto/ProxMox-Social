"""
Brain Orchestrator - The main control loop.

Uses the WORKING VisionController and InputController from test_osp_click.py.
These are SYNC controllers that handle their own VNC capture internally.
"""

import asyncio
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from src.fetcher import Fetcher, PendingPost, Platform
from src.reporter import Reporter
from src.subsystems.vnc_capture import VNCCapture
from src.vision_controller import VisionController
from src.input_controller import InputController
from src.workflows.async_base_workflow import WorkflowResult
from src.workflows.skool_workflow import SkoolWorkflow
from src.workflows.instagram_workflow import InstagramWorkflow
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrainOrchestrator:
    """
    The main brain orchestrator.
    
    Uses WORKING sync controllers (VisionController, InputController)
    that handle VNC capture and vision processing internally.
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        
        # Core components
        self.fetcher: Optional[Fetcher] = None
        self.reporter: Optional[Reporter] = None
        self.vnc: Optional[VNCCapture] = None
        
        # WORKING sync controllers
        self.vision: Optional[VisionController] = None
        self.input: Optional[InputController] = None
        
        # Workflows
        self.workflows: Dict[Platform, Any] = {}
        
        # State
        self.running = False
        self.current_post: Optional[PendingPost] = None
    
    async def initialize(self) -> bool:
        """Initialize all subsystems."""
        logger.info("Loading configuration...")
        self.config = self._load_config()
        
        # Initialize fetcher
        logger.info("Initializing fetcher...")
        api_config = self.config.get("api", {})
        self.fetcher = Fetcher(
            api_base_url=api_config.get("base_url", "https://social.sterlingcooley.com/api"),
            timeout=api_config.get("timeout_seconds", 10),
            api_key=api_config.get("api_key", "")
        )
        await self.fetcher.initialize()
        
        # Initialize reporter
        logger.info("Initializing reporter...")
        self.reporter = Reporter(
            api_base_url=api_config.get("base_url", "https://social.sterlingcooley.com/api"),
            timeout=api_config.get("timeout_seconds", 10),
            api_key=api_config.get("api_key", "")
        )
        await self.reporter.initialize()
        
        # Initialize VNC capture (for backup/direct access if needed)
        logger.info("Initializing VNC capture...")
        vnc_config = self.config.get("vnc", self.config.get("windows_vm", {}))
        self.vnc = VNCCapture(
            host=vnc_config.get("host", vnc_config.get("vnc_host", "192.168.100.20")),
            port=vnc_config.get("port", vnc_config.get("vnc_port", 5900)),
            password=vnc_config.get("password", vnc_config.get("vnc_password"))
        )
        await self.vnc.initialize()
        
        # Initialize WORKING VisionController (uses config.json)
        logger.info("Initializing VisionController...")
        self.vision = VisionController()
        logger.info(f"VisionController ready - Model: {self.vision.model_name}")
        
        # Initialize WORKING InputController (uses config.json)
        logger.info("Initializing InputController...")
        self.input = InputController()
        self.input.connect()
        logger.info("InputController connected")
        
        # Initialize workflows
        logger.info("Initializing workflows...")
        self._initialize_workflows()
        
        logger.info("Brain initialization complete!")
        return True
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_path = Path(self.config_path)
        
        if not config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return self._default_config()
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        config = self._substitute_env(config)
        return config
    
    def _substitute_env(self, obj: Any) -> Any:
        """Recursively substitute environment variables in config."""
        if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            return os.environ.get(var_name, obj)
        elif isinstance(obj, dict):
            return {k: self._substitute_env(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_env(item) for item in obj]
        return obj
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "api": {
                "base_url": "https://social.sterlingcooley.com/api",
                "poll_interval_seconds": 30,
                "timeout_seconds": 10
            },
            "vnc": {
                "host": "192.168.100.20",
                "port": 5900
            }
        }
    
    def _initialize_workflows(self):
        """Initialize platform-specific workflows."""
        workflow_config = self.config.get("workflow", self.config.get("workflows", {}))

        # Skool workflow
        skool_workflow = SkoolWorkflow(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        if self.screenshot_saver:
            skool_workflow.set_screenshot_saver(self.screenshot_saver)

        skool_workflow.max_retries = workflow_config.get("max_retries", 3)
        skool_workflow.step_timeout = workflow_config.get("step_timeout_seconds", workflow_config.get("step_timeout", 30))

        self.workflows[Platform.SKOOL] = skool_workflow

        # Instagram workflow
        instagram_workflow = InstagramWorkflow(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        if self.screenshot_saver:
            instagram_workflow.set_screenshot_saver(self.screenshot_saver)

        instagram_workflow.max_retries = workflow_config.get("max_retries", 3)
        instagram_workflow.step_timeout = workflow_config.get("step_timeout_seconds", workflow_config.get("step_timeout", 30))

        self.workflows[Platform.INSTAGRAM] = instagram_workflow

        # TODO: Add other platforms
        # self.workflows[Platform.FACEBOOK] = FacebookWorkflow(...)
        # self.workflows[Platform.TIKTOK] = TikTokWorkflow(...)
        logger.info(f"Initialized workflows for: {[p.value for p in self.workflows.keys()]}")
    
    async def shutdown(self):
        """Shutdown all subsystems gracefully."""
        logger.info("Shutting down brain...")
        self.running = False
        
        if self.fetcher:
            await self.fetcher.shutdown()
        if self.reporter:
            await self.reporter.shutdown()
        
        logger.info("Brain shutdown complete")
    
    async def run_forever(self):
        """Main loop - continuously process posts."""
        self.running = True
        api_config = self.config.get("api", {})
        poll_interval = api_config.get("poll_interval_seconds", api_config.get("poll_interval", 30))
        
        logger.info(f"Starting main loop (poll interval: {poll_interval}s)")
        
        while self.running:
            try:
                post = await self.fetcher.get_next_pending_post()
                
                if post:
                    await self._process_post(post)
                else:
                    logger.debug("No pending posts, waiting...")
                
            except Exception as e:
                logger.exception(f"Main loop error: {e}")
            
            if self.running:
                await asyncio.sleep(poll_interval)
        
        logger.info("Main loop ended")
    
    async def _process_post(self, post: PendingPost):
        """Process a single post."""
        logger.info("=" * 60)
        logger.info(f"PROCESSING POST: {post.id}")
        logger.info(f"Platform: {post.platform.value}")
        logger.info(f"URL: {post.url}")
        logger.info("=" * 60)
        
        # Wait for Windows 10 OSP GUI to download and display the post
        # This prevents a race condition where we click before content is ready
        osp_load_delay = 15  # seconds
        logger.info(f"Waiting {osp_load_delay}s for Windows 10 OSP to load post content...")
        await asyncio.sleep(osp_load_delay)
        logger.info("OSP load delay complete, starting workflow...")
        
        self.current_post = post
        
        try:
            # Mark as processing
            await self.reporter.report_processing(post.id)
            
            # Get workflow
            workflow = self.workflows.get(post.platform)
            
            if not workflow:
                logger.error(f"No workflow for platform: {post.platform.value}")
                await self.reporter.report_failure(
                    post.id,
                    f"Unsupported platform: {post.platform.value}",
                    step="workflow_selection"
                )
                return
            
            # Execute workflow
            result = await workflow.execute(post)
            
            # Report result
            if result.success:
                await self.reporter.report_success(
                    post.id,
                    email_sent=post.send_email
                )
                logger.info(f"Post {post.id} completed successfully!")
            else:
                await self.reporter.report_failure(
                    post.id,
                    result.error_message or "Unknown error",
                    step=result.error_step
                )
                logger.warning(f"Post {post.id} failed: {result.error_message}")
            
        except Exception as e:
            logger.exception(f"Error processing post {post.id}: {e}")
            await self.reporter.report_failure(
                post.id,
                str(e),
                step="unknown"
            )
        finally:
            self.current_post = None
    
    async def run_single_post(self, post_id: str) -> Optional[WorkflowResult]:
        """Run a single post by ID (for testing)."""
        logger.info(f"Running single post: {post_id}")
        return None
