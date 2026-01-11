"""
Async Base Workflow - Abstract base class for async platform workflows.

All platform-specific workflows inherit from this class.
It provides the common structure and helper methods for async operations.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from PIL import Image

from src.fetcher import PendingPost
from src.subsystems.vnc_capture import VNCCapture
from src.subsystems.vision_engine import VisionEngine, FoundElement
from src.subsystems.input_injector import InputInjector
from src.utils.logger import get_logger
from src.utils.screenshot_saver import ScreenshotSaver

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = auto()
    IN_PROGRESS = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class StepResult:
    """Result of executing a workflow step."""
    status: StepStatus
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None


@dataclass
class WorkflowResult:
    """Final result of workflow execution."""
    success: bool
    post_id: str
    platform: str
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    duration_seconds: float = 0.0


class AsyncBaseWorkflow(ABC):
    """
    Base class for platform-specific async workflows.
    
    Each workflow is a sequence of steps that:
    1. Take a screenshot
    2. Ask vision where to click
    3. Send the click command
    4. Verify the result
    """
    
    def __init__(
        self,
        vnc: VNCCapture,
        vision: VisionEngine,
        input_injector: InputInjector
    ):
        """
        Initialize workflow.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        
        # Configuration
        self.screenshot_delay = 0.5      # Seconds to wait after action before screenshot
        self.action_delay = 0.3          # Seconds between actions
        self.max_retries = 3             # Retries per step
        self.step_timeout = 30           # Seconds timeout per step
        
        # State
        self.current_post: Optional[PendingPost] = None
        self.current_step: int = 0
        self.screenshot_saver: Optional[ScreenshotSaver] = None
        
        # Step data that persists across steps
        self._step_data: Dict[str, Any] = {}
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name."""
        pass
    
    @property
    @abstractmethod
    def steps(self) -> List[str]:
        """Return list of step names in order."""
        pass
    
    def set_screenshot_saver(self, saver: ScreenshotSaver):
        """Set the screenshot saver for debugging."""
        self.screenshot_saver = saver
    
    # ==================== CORE EXECUTION ====================
    
    async def execute(self, post: PendingPost) -> WorkflowResult:
        """
        Execute the full workflow for a post.
        
        Args:
            post: Post data to process
            
        Returns:
            WorkflowResult with success/failure details
        """
        self.current_post = post
        self.current_step = 0
        self._step_data = {}
        start_time = datetime.now()
        
        logger.info(f"{'='*60}")
        logger.info(f"Starting {self.platform_name} workflow for post {post.id}")
        logger.info(f"URL: {post.url}")
        logger.info(f"Title: {post.title[:50]}..." if len(post.title) > 50 else f"Title: {post.title}")
        logger.info(f"{'='*60}")
        
        try:
            # Execute each step
            for i, step_name in enumerate(self.steps):
                self.current_step = i
                logger.info(f"Step {i+1}/{len(self.steps)}: {step_name}")
                
                result = await self._execute_step_with_retry(step_name)
                
                if result.status == StepStatus.FAILED:
                    duration = (datetime.now() - start_time).total_seconds()
                    logger.error(f"Step failed: {result.message}")
                    return WorkflowResult(
                        success=False,
                        post_id=post.id,
                        platform=self.platform_name,
                        steps_completed=i,
                        total_steps=len(self.steps),
                        error_message=result.message,
                        error_step=step_name,
                        duration_seconds=duration
                    )
                
                # Store step data for use in later steps
                if result.data:
                    self._step_data.update(result.data)
                
                # Brief pause between steps
                await asyncio.sleep(self.action_delay)
            
            # All steps completed
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Workflow completed successfully in {duration:.1f}s")
            
            return WorkflowResult(
                success=True,
                post_id=post.id,
                platform=self.platform_name,
                steps_completed=len(self.steps),
                total_steps=len(self.steps),
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.exception(f"Workflow error: {e}")
            
            return WorkflowResult(
                success=False,
                post_id=post.id,
                platform=self.platform_name,
                steps_completed=self.current_step,
                total_steps=len(self.steps),
                error_message=str(e),
                error_step=self.steps[self.current_step] if self.current_step < len(self.steps) else None,
                duration_seconds=duration
            )
    
    async def _execute_step_with_retry(self, step_name: str) -> StepResult:
        """Execute a step with retries."""
        for attempt in range(self.max_retries):
            try:
                result = await asyncio.wait_for(
                    self._execute_step(step_name),
                    timeout=self.step_timeout
                )
                
                if result.status == StepStatus.SUCCESS:
                    return result
                elif result.status == StepStatus.SKIPPED:
                    return result
                    
                logger.warning(f"Step failed (attempt {attempt+1}): {result.message}")
                
            except asyncio.TimeoutError:
                logger.warning(f"Step timed out (attempt {attempt+1})")
            except Exception as e:
                logger.exception(f"Step error (attempt {attempt+1}): {e}")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)
        
        return StepResult(
            status=StepStatus.FAILED,
            message=f"Step '{step_name}' failed after {self.max_retries} attempts"
        )
    
    @abstractmethod
    async def _execute_step(self, step_name: str) -> StepResult:
        """
        Execute a single step. Must be implemented by subclass.
        
        Args:
            step_name: Name of the step to execute
            
        Returns:
            StepResult
        """
        pass
    
    # ==================== HELPER METHODS ====================
    
    async def take_screenshot(self, save_name: Optional[str] = None) -> Optional[Image.Image]:
        """Take a screenshot and optionally save it."""
        await asyncio.sleep(self.screenshot_delay)
        
        screenshot = await self.vnc.capture()
        
        if screenshot and self.screenshot_saver and save_name:
            post_id = self.current_post.id if self.current_post else None
            self.screenshot_saver.save(screenshot, save_name, post_id)
        
        return screenshot
    
    async def find_and_click(
        self,
        element_description: str,
        click_after_find: bool = True,
        save_screenshot: bool = True
    ) -> Optional[FoundElement]:
        """
        Take screenshot, find element, and optionally click it.
        
        Args:
            element_description: What to find
            click_after_find: Whether to click the element
            save_screenshot: Whether to save screenshot for debugging
            
        Returns:
            FoundElement if found
        """
        step_name = self.steps[self.current_step] if self.current_step < len(self.steps) else "unknown"
        screenshot = await self.take_screenshot(step_name if save_screenshot else None)
        
        if not screenshot:
            logger.error("Failed to capture screenshot")
            return None
        
        element = await self.vision.find_element(screenshot, element_description)
        
        if not element:
            logger.warning(f"Element not found: {element_description}")
            return None
        
        if click_after_find:
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked at ({element.x}, {element.y})")
        
        return element
    
    async def find_osp_button_and_click(self, button_name: str) -> bool:
        """
        Find and click an OSP button.
        
        Args:
            button_name: Button text (e.g., "OPEN URL", "COPY TITLE")
            
        Returns:
            True if successful
        """
        element = await self.find_and_click(
            f"button labeled '{button_name}' on the right side panel (OSP)"
        )
        return element is not None
    
    async def find_paste_target_and_paste(
        self,
        target_description: str
    ) -> bool:
        """
        Find paste target, click it, and paste.
        
        Args:
            target_description: Description of where to paste
            
        Returns:
            True if successful
        """
        element = await self.find_and_click(target_description)
        if not element:
            return False
        
        await asyncio.sleep(0.3)
        await self.input.paste()
        return True
    
    async def verify_screen_state(self, expected_state: str) -> bool:
        """
        Verify the screen shows expected state.
        
        Args:
            expected_state: Description of expected state
            
        Returns:
            True if screen matches
        """
        screenshot = await self.take_screenshot()
        if not screenshot:
            return False
        
        state = await self.vision.verify_screen_state(screenshot, expected_state)
        return state.is_match
    
    async def wait_for_state(
        self,
        expected_state: str,
        timeout: int = 10,
        check_interval: float = 1.0
    ) -> bool:
        """
        Wait for screen to show expected state.
        
        Args:
            expected_state: Description of expected state
            timeout: Maximum seconds to wait
            check_interval: Seconds between checks
            
        Returns:
            True if state achieved within timeout
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if await self.verify_screen_state(expected_state):
                return True
            await asyncio.sleep(check_interval)
        
        return False
    
    def get_step_data(self, key: str, default: Any = None) -> Any:
        """Get data stored from a previous step."""
        return self._step_data.get(key, default)
    
    def set_step_data(self, key: str, value: Any):
        """Store data for use in later steps."""
        self._step_data[key] = value
