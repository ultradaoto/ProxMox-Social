"""
Async Base Workflow - Abstract base class for platform workflows.

Uses the WORKING sync VisionController and InputController.
These controllers handle their own screenshot capture internally.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime

from src.fetcher import PendingPost
from src.subsystems.vnc_capture import VNCCapture
from src.vision_controller import VisionController
from src.input_controller import InputController
from src.utils.logger import get_logger

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
    Base class for platform-specific workflows.
    
    Uses WORKING sync controllers (VisionController, InputController)
    that are wrapped with asyncio.to_thread() for async compatibility.
    """
    
    def __init__(
        self,
        vnc: VNCCapture,
        vision: VisionController,
        input_injector: InputController
    ):
        """
        Initialize workflow.
        
        Args:
            vnc: VNC capture instance (for direct capture if needed)
            vision: VisionController instance (WORKING sync controller)
            input_injector: InputController instance (WORKING sync controller)
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        
        # Configuration
        self.action_delay = 0.3
        self.max_retries = 3
        self.step_timeout = 60
        
        # State
        self.current_post: Optional[PendingPost] = None
        self.current_step: int = 0
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
    
    async def execute(self, post: PendingPost) -> WorkflowResult:
        """Execute the full workflow for a post."""
        self.current_post = post
        self.current_step = 0
        self._step_data = {}
        start_time = datetime.now()
        
        logger.info("=" * 60)
        logger.info(f"Starting {self.platform_name} workflow for post {post.id}")
        logger.info(f"URL: {post.url}")
        title = post.title or "(no title)"
        logger.info(f"Title: {title[:50]}..." if len(title) > 50 else f"Title: {title}")
        logger.info("=" * 60)
        
        try:
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
                
                if result.data:
                    self._step_data.update(result.data)
                
                await asyncio.sleep(self.action_delay)
            
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
                
                if result.status in (StepStatus.SUCCESS, StepStatus.SKIPPED):
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
        """Execute a single step. Must be implemented by subclass."""
        pass
    
    def get_step_data(self, key: str, default: Any = None) -> Any:
        """Get data stored from a previous step."""
        return self._step_data.get(key, default)
    
    def set_step_data(self, key: str, value: Any):
        """Store data for use in later steps."""
        self._step_data[key] = value
