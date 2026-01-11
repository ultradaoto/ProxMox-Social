"""
Brain Orchestrator - The main control loop.

This is the BRAIN that coordinates everything:
1. Fetches pending posts from API
2. Connects to Windows 10 via VNC
3. Handles login if needed
4. Dispatches to platform-specific workflows
5. Reports results
"""

import asyncio
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from src.fetcher import Fetcher, PendingPost, Platform
from src.reporter import Reporter
from src.subsystems.vnc_capture import VNCCapture
from src.subsystems.vision_engine import VisionEngine
from src.subsystems.input_injector import InputInjector
from src.subroutines.windows_login import WindowsLoginSubroutine
from src.subroutines.browser_focus import BrowserFocusSubroutine
from src.subroutines.error_recovery import ErrorRecoverySubroutine
from src.workflows.async_base_workflow import WorkflowResult
from src.workflows.skool_workflow import SkoolWorkflow
from src.utils.logger import get_logger
from src.utils.screenshot_saver import ScreenshotSaver

logger = get_logger(__name__)


class BrainOrchestrator:
    """
    The main brain orchestrator.
    
    This class coordinates all subsystems to:
    1. Monitor for pending posts
    2. Connect to Windows 10
    3. Execute platform-specific workflows
    4. Report results
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        Initialize the brain.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        
        # Subsystems
        self.fetcher: Optional[Fetcher] = None
        self.reporter: Optional[Reporter] = None
        self.vnc: Optional[VNCCapture] = None
        self.vision: Optional[VisionEngine] = None
        self.input: Optional[InputInjector] = None
        
        # Subroutines
        self.windows_login: Optional[WindowsLoginSubroutine] = None
        self.browser_focus: Optional[BrowserFocusSubroutine] = None
        self.error_recovery: Optional[ErrorRecoverySubroutine] = None
        
        # Workflows
        self.workflows: Dict[Platform, Any] = {}
        
        # Screenshot saver for debugging
        self.screenshot_saver: Optional[ScreenshotSaver] = None
        
        # State
        self.running = False
        self.current_post: Optional[PendingPost] = None
    
    async def initialize(self) -> bool:
        """
        Initialize all subsystems.
        
        Returns:
            True if all subsystems initialized successfully
        """
        # Load configuration
        logger.info("Loading configuration...")
        self.config = self._load_config()
        
        # Setup screenshot saver if enabled
        if self.config.get("logging", {}).get("save_screenshots", True):
            screenshots_dir = self.config.get("logging", {}).get("screenshot_dir", "logs/screenshots")
            self.screenshot_saver = ScreenshotSaver(screenshots_dir)
            logger.info(f"Screenshots will be saved to: {self.screenshot_saver.get_session_dir()}")
        
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
        
        # Initialize VNC capture
        logger.info("Initializing VNC capture...")
        vnc_config = self.config.get("vnc", self.config.get("windows_vm", {}))
        self.vnc = VNCCapture(
            host=vnc_config.get("host", vnc_config.get("vnc_host", "192.168.100.20")),
            port=vnc_config.get("port", vnc_config.get("vnc_port", 5900)),
            password=vnc_config.get("password", vnc_config.get("vnc_password"))
        )
        await self.vnc.initialize()
        
        # Initialize vision engine
        logger.info("Initializing vision engine...")
        vision_config = self.config.get("vision", {})
        ollama_host = vision_config.get("ollama_host", "http://localhost:11434")
        # Extract host and port from URL
        if "://" in ollama_host:
            host_part = ollama_host.split("://")[1]
            host = host_part.split(":")[0] if ":" in host_part else host_part
            port = int(host_part.split(":")[1]) if ":" in host_part else 11434
        else:
            host = "localhost"
            port = 11434
        
        self.vision = VisionEngine(
            model=vision_config.get("model", "qwen2.5-vl:7b"),
            ollama_host=host,
            ollama_port=port,
            timeout=vision_config.get("timeout", vision_config.get("timeout_seconds", 60))
        )
        await self.vision.initialize()
        
        # Initialize input injector
        logger.info("Initializing input injector...")
        input_config = self.config.get("input", self.config.get("proxmox", {}))
        self.input = InputInjector(
            proxmox_host=input_config.get("proxmox_host", input_config.get("host", "192.168.100.1")),
            api_port=input_config.get("api_port", input_config.get("input_api_port", 8888))
        )
        await self.input.initialize()
        
        # Initialize subroutines
        logger.info("Initializing subroutines...")
        windows_creds = self.config.get("windows_credentials", {})
        self.windows_login = WindowsLoginSubroutine(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input,
            password=windows_creds.get("password", "")
        )
        
        self.browser_focus = BrowserFocusSubroutine(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        
        self.error_recovery = ErrorRecoverySubroutine(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        
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
        
        # Substitute environment variables
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
            },
            "vision": {
                "model": "qwen2.5-vl:7b",
                "ollama_host": "localhost",
                "ollama_port": 11434,
                "timeout_seconds": 60
            },
            "input": {
                "proxmox_host": "192.168.100.1",
                "api_port": 8888
            },
            "windows_credentials": {
                "password": ""
            },
            "workflow": {
                "screenshot_delay_ms": 500,
                "action_delay_ms": 300,
                "max_retries": 3,
                "step_timeout_seconds": 30
            },
            "logging": {
                "level": "INFO",
                "save_screenshots": True,
                "screenshot_dir": "logs/screenshots"
            }
        }
    
    def _initialize_workflows(self):
        """Initialize platform-specific workflows."""
        # Skool workflow
        skool_workflow = SkoolWorkflow(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        if self.screenshot_saver:
            skool_workflow.set_screenshot_saver(self.screenshot_saver)
        
        workflow_config = self.config.get("workflow", self.config.get("workflows", {}))
        skool_workflow.max_retries = workflow_config.get("max_retries", 3)
        skool_workflow.step_timeout = workflow_config.get("step_timeout_seconds", workflow_config.get("step_timeout", 30))
        
        self.workflows[Platform.SKOOL] = skool_workflow
        
        # TODO: Add other platforms
        # self.workflows[Platform.INSTAGRAM] = InstagramWorkflow(...)
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
        if self.vision:
            await self.vision.shutdown()
        if self.input:
            await self.input.shutdown()
        
        logger.info("Brain shutdown complete")
    
    async def run_forever(self):
        """
        Main loop - continuously process posts.
        
        This is the main brain loop that:
        1. Polls for pending posts
        2. Processes one post at a time
        3. Reports results
        4. Repeats
        """
        self.running = True
        api_config = self.config.get("api", {})
        poll_interval = api_config.get("poll_interval_seconds", api_config.get("poll_interval", 30))
        
        logger.info(f"Starting main loop (poll interval: {poll_interval}s)")
        
        while self.running:
            try:
                # Step 1: Check for pending post
                post = await self.fetcher.get_next_pending_post()
                
                if post:
                    # Step 2: Process the post
                    await self._process_post(post)
                else:
                    logger.debug("No pending posts, waiting...")
                
            except Exception as e:
                logger.exception(f"Main loop error: {e}")
            
            # Wait before next poll
            if self.running:
                await asyncio.sleep(poll_interval)
        
        logger.info("Main loop ended")
    
    async def _process_post(self, post: PendingPost):
        """
        Process a single post.
        
        Args:
            post: Post to process
        """
        logger.info(f"{'='*60}")
        logger.info(f"PROCESSING POST: {post.id}")
        logger.info(f"Platform: {post.platform.value}")
        logger.info(f"URL: {post.url}")
        logger.info(f"{'='*60}")
        
        self.current_post = post
        
        try:
            # Step 1: Mark post as processing
            await self.reporter.report_processing(post.id)
            
            # Step 2: Ensure Windows 10 is ready
            if not await self._ensure_windows_ready():
                await self.reporter.report_failure(
                    post.id,
                    "Failed to connect to Windows 10 or prepare environment",
                    step="windows_setup"
                )
                return
            
            # Step 3: Get workflow for platform
            workflow = self.workflows.get(post.platform)
            
            if not workflow:
                logger.error(f"No workflow for platform: {post.platform.value}")
                await self.reporter.report_failure(
                    post.id,
                    f"Unsupported platform: {post.platform.value}",
                    step="workflow_selection"
                )
                return
            
            # Step 4: Execute workflow
            result = await workflow.execute(post)
            
            # Step 5: Report result
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
    
    async def _ensure_windows_ready(self) -> bool:
        """
        Ensure Windows 10 is connected and ready.
        
        Returns:
            True if Windows is ready
        """
        logger.info("Checking Windows 10 state...")
        
        # Step 1: Capture screenshot
        screenshot = await self.vnc.capture()
        if not screenshot:
            logger.warning("Failed to capture Windows 10 screen (VNC may not be connected)")
            return True  # Assume it will work when deployed
        
        # Step 2: Check if login screen is showing
        is_login = await self.vision.check_for_login_screen(screenshot)
        
        if is_login:
            logger.info("Windows login screen detected, logging in...")
            
            if not await self.windows_login.execute():
                logger.error("Windows login failed")
                return False
        
        # Step 3: Ensure browser is focused with OSP panel
        logger.info("Checking for Chrome with OSP panel...")
        
        screenshot = await self.vnc.capture()
        if not screenshot:
            return True
        
        state = await self.vision.verify_screen_state(
            screenshot,
            "Chrome browser with OSP panel visible on the right side"
        )
        
        if state.is_match:
            logger.info("Windows 10 is ready with Chrome and OSP")
            return True
        
        # Try to focus browser
        logger.info("Attempting to focus Chrome...")
        await self.browser_focus.execute()
        
        return True
    
    async def run_single_post(self, post_id: str) -> Optional[WorkflowResult]:
        """
        Run a single post by ID (for testing).
        
        Args:
            post_id: Post ID to process
            
        Returns:
            WorkflowResult
        """
        # TODO: Implement fetching specific post by ID
        logger.info(f"Running single post: {post_id}")
        return None
