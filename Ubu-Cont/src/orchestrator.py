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
from src.workflows.json_workflow import create_instagram_workflow, create_skool_workflow, create_facebook_workflow, create_linkedin_workflow
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Pause flag path - shared with vnc_stream_server.py
PAUSE_FLAG_PATH = "/tmp/brain_pause_flag"

def is_main_paused():
    """Check if main automation is paused via web UI."""
    import os
    return os.path.exists(PAUSE_FLAG_PATH)


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
        
        # Screenshot saver (optional)
        self.screenshot_saver = None
        
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
        # Get API key from config or environment variable
        api_key = api_config.get("api_key") or os.getenv("API_KEY", "")
        api_base_url = api_config.get("base_url") or os.getenv("API_BASE_URL", "https://social.sterlingcooley.com/api")
        
        logger.info(f"API Base URL: {api_base_url}")
        logger.info(f"API Key configured: {'Yes' if api_key else 'No'}")
        
        self.fetcher = Fetcher(
            api_base_url=api_base_url,
            timeout=api_config.get("timeout_seconds", 30),
            api_key=api_key
        )
        await self.fetcher.initialize()
        
        # Initialize reporter
        logger.info("Initializing reporter...")
        self.reporter = Reporter(
            api_base_url=api_base_url,
            timeout=api_config.get("timeout_seconds", 30),
            api_key=api_key
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
        """Initialize platform-specific workflows from JSON recordings."""
        logger.info("Loading workflows from JSON recordings...")

        # Skool workflow - loads from recordings/skool_default.json
        try:
            skool_workflow = create_skool_workflow(
                vnc=self.vnc,
                vision=self.vision,
                input_injector=self.input
            )
            self.workflows[Platform.SKOOL] = skool_workflow
            logger.info(f"Loaded Skool workflow: {len(skool_workflow.actions)} actions")
        except Exception as e:
            logger.error(f"Failed to load Skool workflow: {e}")

        # Instagram workflow - loads from recordings/instagram_default.json
        try:
            instagram_workflow = create_instagram_workflow(
                vnc=self.vnc,
                vision=self.vision,
                input_injector=self.input
            )
            self.workflows[Platform.INSTAGRAM] = instagram_workflow
            logger.info(f"Loaded Instagram workflow: {len(instagram_workflow.actions)} actions")
        except Exception as e:
            logger.error(f"Failed to load Instagram workflow: {e}")

        # Facebook workflow - loads from recordings/facebook_default.json
        try:
            facebook_workflow = create_facebook_workflow(
                vnc=self.vnc,
                vision=self.vision,
                input_injector=self.input
            )
            self.workflows[Platform.FACEBOOK] = facebook_workflow
            logger.info(f"Loaded Facebook workflow: {len(facebook_workflow.actions)} actions")
        except Exception as e:
            logger.error(f"Failed to load Facebook workflow: {e}")

        # LinkedIn workflow - loads from recordings/linkedin_default.json
        try:
            linkedin_workflow = create_linkedin_workflow(
                vnc=self.vnc,
                vision=self.vision,
                input_injector=self.input
            )
            self.workflows[Platform.LINKEDIN] = linkedin_workflow
            logger.info(f"Loaded LinkedIn workflow: {len(linkedin_workflow.actions)} actions")
        except Exception as e:
            logger.error(f"Failed to load LinkedIn workflow: {e}")

        logger.info(f"Initialized JSON-based workflows for: {[p.value for p in self.workflows.keys()]}")
    
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
                # Check if paused via web UI
                if is_main_paused():
                    logger.debug("Main automation PAUSED via web UI - waiting...")
                    await asyncio.sleep(2)
                    continue
                
                post = await self.fetcher.get_next_pending_post()
                
                if post:
                    # Double-check pause before starting workflow
                    if is_main_paused():
                        logger.info("Pause detected before workflow - skipping this cycle")
                        continue
                    await self._process_post(post)
                else:
                    logger.debug("No pending posts, waiting...")
                
            except Exception as e:
                logger.exception(f"Main loop error: {e}")
            
            if self.running:
                await asyncio.sleep(poll_interval)
        
        logger.info("Main loop ended")
    
    async def _process_post(self, post: PendingPost):
        """Process a single post by detecting platform from OSP."""
        logger.info("=" * 60)
        logger.info(f"API DETECTED POST: {post.id}")
        logger.info(f"API says platform: {post.platform.value}")
        logger.info("Will detect actual platform from OSP screen...")
        logger.info("=" * 60)
        
        self.current_post = post
        
        try:
            # Mark as processing
            await self.reporter.report_processing(post.id)
            
            # STEP 1: Wait for OSP to be ready and detect platform from screen
            detected_platform = await self._wait_for_osp_and_detect_platform()
            
            if not detected_platform:
                logger.error("Could not detect platform from OSP after timeout")
                await self.reporter.report_failure(
                    post.id,
                    "OSP not ready or platform not detected",
                    step="osp_detection"
                )
                return
            
            logger.info(f"OSP shows platform: {detected_platform}")
            
            # STEP 2: Get the workflow for the DETECTED platform (not API platform)
            workflow = None
            if detected_platform == "SKOOL":
                workflow = self.workflows.get(Platform.SKOOL)
            elif detected_platform == "INSTAGRAM":
                workflow = self.workflows.get(Platform.INSTAGRAM)
            elif detected_platform == "FACEBOOK":
                workflow = self.workflows.get(Platform.FACEBOOK)
            elif detected_platform == "LINKEDIN":
                workflow = self.workflows.get(Platform.LINKEDIN)
            
            if not workflow:
                logger.error(f"No workflow for detected platform: {detected_platform}")
                await self.reporter.report_failure(
                    post.id,
                    f"No workflow for platform: {detected_platform}",
                    step="workflow_selection"
                )
                return
            
            logger.info(f"Running {detected_platform} workflow...")
            
            # STEP 3: Execute workflow (skip the wait_for_osp_ready step since we already did it)
            # We'll set a flag so the workflow knows OSP is already confirmed ready
            workflow.set_step_data("osp_already_ready", True)
            workflow.set_step_data("detected_platform", detected_platform)
            
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
    
    async def _wait_for_osp_and_detect_platform(self) -> Optional[str]:
        """
        Wait for OSP to be ready and detect which platform is loaded.
        Returns: 'SKOOL', 'INSTAGRAM', 'FACEBOOK', 'LINKEDIN', or None if timeout
        """
        import asyncio
        
        max_attempts = 15  # Up to ~10 minutes
        
        for attempt in range(1, max_attempts + 1):
            # Check pause during detection loop
            if is_main_paused():
                logger.info("Paused during OSP detection - waiting...")
                await asyncio.sleep(2)
                continue
            
            logger.info(f"Checking OSP for platform (attempt {attempt}/{max_attempts})...")
            
            await asyncio.sleep(3.0)  # Let screen settle
            
            try:
                # Use vision controller to analyze the screen
                result = await asyncio.to_thread(
                    self.vision.analyze_screen,
                    "Look at the OSP panel on the right side of the screen. "
                    "Do you see RED text that says 'NO POSTS'? "
                    "Or do you see a platform name in the upper right like 'SKOOL', 'INSTAGRAM', 'FACEBOOK', or 'LINKEDIN'? "
                    "Answer 'NO_POSTS' if you see red 'NO POSTS' text. "
                    "Answer 'SKOOL' if you see Skool. "
                    "Answer 'INSTAGRAM' if you see Instagram. "
                    "Answer 'FACEBOOK' if you see Facebook. "
                    "Answer 'LINKEDIN' if you see LinkedIn."
                )
                
                result_upper = result.upper()
                logger.info(f"OSP detection result: {result[:100]}...")
                
                # Check for platform indicators
                if "SKOOL" in result_upper and "NO" not in result_upper:
                    logger.info("Detected SKOOL on OSP!")
                    return "SKOOL"
                
                if "INSTAGRAM" in result_upper and "NO" not in result_upper:
                    logger.info("Detected INSTAGRAM on OSP!")
                    return "INSTAGRAM"
                
                if "FACEBOOK" in result_upper and "NO" not in result_upper:
                    logger.info("Detected FACEBOOK on OSP!")
                    return "FACEBOOK"
                
                if "LINKEDIN" in result_upper and "NO" not in result_upper:
                    logger.info("Detected LINKEDIN on OSP!")
                    return "LINKEDIN"
                
                # If we see "NO POSTS", wait longer
                if "NO_POSTS" in result_upper or "NO POSTS" in result_upper:
                    logger.info(f"OSP shows 'NO POSTS' - waiting 45 seconds...")
                    await asyncio.sleep(45)
                    continue
                
                # Ambiguous - wait and try again
                logger.info(f"OSP status unclear, waiting 30 seconds...")
                await asyncio.sleep(30)
                
            except Exception as e:
                logger.error(f"Error checking OSP: {e}")
                await asyncio.sleep(10)
        
        logger.error(f"OSP detection timed out after {max_attempts} attempts")
        return None
    
    async def run_single_post(self, post_id: str) -> Optional[WorkflowResult]:
        """Run a single post by ID (for testing)."""
        logger.info(f"Running single post: {post_id}")
        return None
