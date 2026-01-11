"""
Base Workflow Class

Shared functionality for all social media posting workflows.
"""
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class PostContent:
    """Content to be posted."""
    post_id: str                    # Unique post ID from API
    media_path: str                 # Full path to media file on Windows
    caption: str                    # Post caption/body text
    hashtags: list                  # List of hashtags (without #)
    platform: str                   # Platform name (instagram, facebook, etc.)
    metadata: Dict[str, Any] = None # Additional platform-specific data
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class WorkflowStep(Enum):
    """Generic workflow steps - subclass and override."""
    INIT = "init"
    DONE = "done"
    FAILED = "failed"


class BaseWorkflow(ABC):
    """
    Base class for all platform workflows.
    
    Provides:
    - Step execution with retries
    - State management
    - Error handling
    - Logging
    """
    
    def __init__(
        self,
        capture,      # VNCCapture instance
        vision,       # VisionFinder instance
        input,        # InputInjector instance
        max_retries: int = 3,
        step_timeout: int = 30
    ):
        """
        Initialize workflow.
        
        Args:
            capture: Screen capture instance
            vision: Vision finder instance
            input: Input injector instance
            max_retries: Max retries per step
            step_timeout: Timeout per step in seconds
        """
        self.capture = capture
        self.vision = vision
        self.input = input
        self.max_retries = max_retries
        self.step_timeout = step_timeout
        
        self.current_step = None
        self.start_time = None
        self.error_message = None
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return platform name (instagram, facebook, etc.)."""
        pass
    
    @abstractmethod
    def get_initial_step(self):
        """Return the first step of the workflow."""
        pass
    
    @abstractmethod
    def execute_step(self, step, content: PostContent) -> bool:
        """
        Execute a single workflow step.
        
        Args:
            step: The step to execute
            content: Post content
        
        Returns:
            True if step succeeded
        """
        pass
    
    @abstractmethod
    def get_next_step(self, current_step):
        """
        Get the next step after current step.
        
        Args:
            current_step: Current workflow step
        
        Returns:
            Next step, or None if workflow complete
        """
        pass
    
    def execute(self, content: PostContent) -> bool:
        """
        Execute full workflow.
        
        Args:
            content: Post content to publish
        
        Returns:
            True if post succeeded, False otherwise
        """
        self.start_time = time.time()
        self.current_step = self.get_initial_step()
        self.error_message = None
        
        platform = self.get_platform_name()
        
        logger.info(f"=" * 60)
        logger.info(f"Starting {platform} workflow")
        logger.info(f"Post ID: {content.post_id}")
        logger.info(f"Media: {content.media_path}")
        logger.info(f"Caption: {content.caption[:50]}...")
        logger.info(f"=" * 60)
        
        try:
            while self.current_step and self.current_step != WorkflowStep.DONE:
                # Check for FAILED state
                if self.current_step == WorkflowStep.FAILED:
                    logger.error(f"{platform} workflow failed at step")
                    return False
                
                # Execute current step with retries
                success = self._execute_step_with_retries(content)
                
                if not success:
                    logger.error(f"Step {self.current_step} failed after {self.max_retries} attempts")
                    return False
                
                # Move to next step
                self.current_step = self.get_next_step(self.current_step)
                
                # Brief pause between steps
                time.sleep(1)
            
            # Workflow completed
            elapsed = time.time() - self.start_time
            logger.info(f"✓ {platform} post completed successfully in {elapsed:.1f}s")
            return True
            
        except Exception as e:
            logger.exception(f"{platform} workflow error: {e}")
            self.error_message = str(e)
            return False
    
    def _execute_step_with_retries(self, content: PostContent) -> bool:
        """Execute step with retries on failure."""
        step_name = self.current_step.value if hasattr(self.current_step, 'value') else str(self.current_step)
        logger.info(f"→ Executing step: {step_name}")
        
        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    logger.warning(f"Retry attempt {attempt + 1}/{self.max_retries}")
                    time.sleep(2 * attempt)  # Increasing backoff
                
                success = self.execute_step(self.current_step, content)
                
                if success:
                    logger.info(f"✓ Step completed: {step_name}")
                    return True
                else:
                    logger.warning(f"✗ Step failed: {step_name}")
                    
            except Exception as e:
                logger.error(f"Step exception (attempt {attempt + 1}): {e}")
        
        return False
    
    def wait_for_element(
        self,
        description: str,
        timeout: Optional[int] = None
    ):
        """
        Wait for an element to appear on screen.
        
        Args:
            description: Element description for vision finder
            timeout: Max seconds to wait (uses step_timeout if None)
        
        Returns:
            UIElement if found, None otherwise
        """
        timeout = timeout or self.step_timeout
        start = time.time()
        
        while time.time() - start < timeout:
            screenshot = self.capture.capture()
            if not screenshot:
                time.sleep(1)
                continue
            
            element = self.vision.find_element(screenshot, description)
            if element:
                return element
            
            time.sleep(1)
        
        return None
    
    def wait_for_state(
        self,
        expected_state: str,
        timeout: Optional[int] = None
    ) -> bool:
        """
        Wait for screen to show expected state.
        
        Args:
            expected_state: State description
            timeout: Max seconds to wait
        
        Returns:
            True if state achieved
        """
        timeout = timeout or self.step_timeout
        start = time.time()
        
        while time.time() - start < timeout:
            screenshot = self.capture.capture()
            if not screenshot:
                time.sleep(1)
                continue
            
            matches, explanation = self.vision.verify_state(screenshot, expected_state)
            if matches:
                logger.info(f"State verified: {explanation}")
                return True
            
            time.sleep(1)
        
        return False
    
    def click_element(
        self,
        description: str,
        timeout: Optional[int] = None,
        double_click: bool = False
    ) -> bool:
        """
        Find and click an element.
        
        Args:
            description: Element description
            timeout: Max seconds to wait for element
            double_click: Use double click instead of single
        
        Returns:
            True if clicked successfully
        """
        element = self.wait_for_element(description, timeout)
        if not element:
            logger.error(f"Element not found: {description}")
            return False
        
        logger.info(f"Clicking element at ({element.x}, {element.y})")
        
        if double_click:
            return self.input.double_click(element.x, element.y)
        else:
            return self.input.click(element.x, element.y)
    
    def type_in_field(
        self,
        field_description: str,
        text: str,
        clear_first: bool = True
    ) -> bool:
        """
        Click a field and type text.
        
        Args:
            field_description: Field description for vision
            text: Text to type
            clear_first: Clear field before typing
        
        Returns:
            True if successful
        """
        # Find and click the field
        if not self.click_element(field_description):
            return False
        
        time.sleep(0.3)
        
        # Clear if requested
        if clear_first:
            self.input.select_all()
            time.sleep(0.1)
        
        # Type the text
        return self.input.type_text(text)
    
    def get_error_message(self) -> Optional[str]:
        """Get error message from failed workflow."""
        return self.error_message
