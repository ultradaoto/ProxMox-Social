"""
Main self-healing orchestrator.
Detects failures, uses AI to find new locations, updates workflows.
"""
import os
import logging
import time
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from PIL import Image
import io

from .config import (
    MAX_HEALING_ATTEMPTS,
    SIMILARITY_FAILURE_THRESHOLD,
    WORKFLOW_ACTION_DESCRIPTIONS,
    DEFAULT_ACTION_DESCRIPTION,
    DATABASE_PATH,
)
from .vision_locator import VisionLocator
from .workflow_updater import WorkflowUpdater
from .events import get_healing_store

logger = logging.getLogger(__name__)


@dataclass
class HealingResult:
    """Result of a self-healing attempt."""
    success: bool
    workflow_name: str
    click_index: int
    old_coordinates: Tuple[int, int]
    new_coordinates: Optional[Tuple[int, int]]
    attempts: int
    error_message: Optional[str] = None
    ai_reasoning: Optional[str] = None


class WorkflowHealer:
    """
    Self-healing system for automation workflows.
    
    When a click fails (similarity < threshold), this system:
    1. Takes a full screenshot
    2. Asks vision AI to find where the button moved
    3. Updates the workflow JSON with new coordinates
    4. Optionally re-runs to verify
    """
    
    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: OpenRouter API key (uses env var if not provided)
        """
        self.locator = VisionLocator(api_key=api_key)
        self.healing_history = []
    
    def get_action_description(self, workflow_name: str, click_index: int) -> str:
        """Get human-readable description of what an action does."""
        workflow_desc = WORKFLOW_ACTION_DESCRIPTIONS.get(workflow_name, {})
        return workflow_desc.get(click_index, DEFAULT_ACTION_DESCRIPTION)
    
    def should_heal(self, similarity_score: float) -> bool:
        """Check if similarity is low enough to trigger healing."""
        return similarity_score < SIMILARITY_FAILURE_THRESHOLD
    
    def heal(
        self,
        workflow_name: str,
        click_index: int,
        similarity_score: float,
        failed_screenshot: bytes,
        baseline_screenshot: bytes,
        full_screenshot_func: Callable[[], bytes]
    ) -> HealingResult:
        """
        Attempt to heal a failed click action.
        
        Args:
            workflow_name: e.g., 'instagram_default'
            click_index: Which click failed (0-indexed, clicks only)
            similarity_score: How similar to baseline (0.0-1.0)
            failed_screenshot: 100x100 PNG of failed click area
            baseline_screenshot: 100x100 PNG of expected baseline
            full_screenshot_func: Function to capture full screen
        
        Returns:
            HealingResult with outcome
        """
        start_time = time.time()
        store = get_healing_store()
        
        # Check if healing is enabled
        if not store.enabled:
            logger.info("Self-healing is disabled")
            return HealingResult(
                success=False,
                workflow_name=workflow_name,
                click_index=click_index,
                old_coordinates=(0, 0),
                new_coordinates=None,
                attempts=0,
                error_message="Self-healing disabled"
            )
        
        logger.info("=" * 60)
        logger.info("SELF-HEALING TRIGGERED")
        logger.info(f"Workflow: {workflow_name}")
        logger.info(f"Click index: {click_index}")
        logger.info(f"Similarity: {similarity_score:.1%}")
        logger.info("=" * 60)
        
        updater = WorkflowUpdater(workflow_name)
        
        # Get current coordinates
        old_coords = updater.get_coordinates_by_click_index(click_index)
        if old_coords is None:
            return HealingResult(
                success=False,
                workflow_name=workflow_name,
                click_index=click_index,
                old_coordinates=(0, 0),
                new_coordinates=None,
                attempts=0,
                error_message="Could not get coordinates for click index"
            )
        
        old_x, old_y = old_coords
        action_description = self.get_action_description(workflow_name, click_index)
        
        # Track event
        event_id = store.start_healing(workflow_name, click_index, similarity_score, old_coords)
        
        for attempt in range(1, MAX_HEALING_ATTEMPTS + 1):
            logger.info(f"Healing attempt {attempt}/{MAX_HEALING_ATTEMPTS}")
            
            # Get fresh full screenshot
            full_screenshot = full_screenshot_func()
            
            # Track AI request
            store.update_ai_request(event_id)
            
            # Ask AI to find the element
            result = self.locator.locate_element(
                full_screenshot=full_screenshot,
                action_description=action_description,
                old_x=old_x,
                old_y=old_y,
                baseline_image=baseline_screenshot,
                failed_image=failed_screenshot
            )
            
            if not result.success:
                logger.warning(f"AI could not locate: {result.reasoning}")
                continue
            
            new_x, new_y = result.new_x, result.new_y
            logger.info(f"AI found element at ({new_x}, {new_y}) - {result.confidence:.1%} confidence")
            
            # Track AI response
            store.update_ai_response(event_id, (new_x, new_y), result.confidence, result.reasoning)
            
            # Update workflow
            try:
                updater.update_coordinates_by_click_index(click_index, new_x, new_y)
            except Exception as e:
                logger.error(f"Failed to update workflow: {e}")
                continue
            
            # Success!
            duration_ms = int((time.time() - start_time) * 1000)
            store.complete_success(event_id, duration_ms)
            
            healing_result = HealingResult(
                success=True,
                workflow_name=workflow_name,
                click_index=click_index,
                old_coordinates=old_coords,
                new_coordinates=(new_x, new_y),
                attempts=attempt,
                ai_reasoning=result.reasoning
            )
            
            self.healing_history.append(healing_result)
            
            logger.info("=" * 60)
            logger.info("SELF-HEALING SUCCESSFUL!")
            logger.info(f"Old: ({old_x}, {old_y}) -> New: ({new_x}, {new_y})")
            logger.info("=" * 60)
            
            return healing_result
        
        # All attempts failed
        duration_ms = int((time.time() - start_time) * 1000)
        store.complete_failed(event_id, "Max healing attempts exceeded", duration_ms)
        
        logger.error(f"Self-healing FAILED after {MAX_HEALING_ATTEMPTS} attempts")
        
        return HealingResult(
            success=False,
            workflow_name=workflow_name,
            click_index=click_index,
            old_coordinates=old_coords,
            new_coordinates=None,
            attempts=MAX_HEALING_ATTEMPTS,
            error_message="Max healing attempts exceeded"
        )
    
    def close(self):
        self.locator.close()


def get_full_screenshot() -> bytes:
    """Get full VNC screenshot from shared frame file."""
    shared_path = "/dev/shm/vnc_latest.png" if os.path.exists("/dev/shm") else "/tmp/vnc_latest.png"
    
    if os.path.exists(shared_path):
        with open(shared_path, 'rb') as f:
            return f.read()
    
    return None
