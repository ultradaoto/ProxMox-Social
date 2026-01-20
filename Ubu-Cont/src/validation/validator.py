"""
Main validation logic - the core of the system.
"""
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

from .database import ValidationDatabase
from .screenshot_capture import ScreenshotCapture
from .image_comparator import quick_compare


@dataclass
class ValidationResult:
    """Result of validating a single click."""
    action_index: int
    click_x: int
    click_y: int
    is_valid: bool
    similarity_score: float
    baseline_exists: bool
    

@dataclass
class WorkflowValidationResult:
    """Result of validating entire workflow run."""
    run_id: int
    workflow_name: str
    success: bool
    click_results: List[ValidationResult]
    failure_index: Optional[int]
    failure_reason: Optional[str]


class WorkflowValidator:
    """
    Validates workflow runs against stored baselines.
    
    Usage:
        validator = WorkflowValidator(db, screenshot_capture)
        
        # Start a run
        run_id = validator.start_run('facebook_default', post_id='123')
        
        # During workflow execution, before each click:
        validator.capture_click(action_index, x, y)
        
        # Before marking success:
        result = validator.validate_run()
        if result.success:
            # Click success button
        else:
            # Click failed button
    """
    
    def __init__(
        self,
        database: ValidationDatabase,
        screenshot: ScreenshotCapture,
        default_threshold: float = 0.95,
        logger: logging.Logger = None
    ):
        """
        Initialize validator.
        
        Args:
            database: ValidationDatabase instance
            screenshot: ScreenshotCapture instance
            default_threshold: Default similarity threshold
            logger: Optional logger
        """
        self.db = database
        self.screenshot = screenshot
        self.default_threshold = default_threshold
        self.logger = logger or logging.getLogger(__name__)
        
        self._current_run_id: Optional[int] = None
        self._current_workflow_id: Optional[int] = None
        self._current_workflow_name: Optional[str] = None
        self._captured_screenshots: Dict[int, bytes] = {}
    
    @property
    def is_run_active(self) -> bool:
        """Check if there's an active validation run."""
        return self._current_run_id is not None
    
    def start_run(
        self,
        workflow_name: str,
        post_id: str = None
    ) -> int:
        """
        Start tracking a new workflow run.
        
        Args:
            workflow_name: Name of workflow (e.g., 'facebook_default')
            post_id: Optional post identifier
            
        Returns:
            Run ID
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            self.logger.warning(f"Unknown workflow: {workflow_name}, creating placeholder")
            workflow_id = self.db.register_workflow(
                name=workflow_name,
                json_path=f"recordings/{workflow_name}.json",
                platform=workflow_name.split('_')[0],
                total_actions=0,
                click_count=0
            )
            self._current_workflow_id = workflow_id
        else:
            self._current_workflow_id = workflow['id']
        
        self._current_workflow_name = workflow_name
        self._current_run_id = self.db.start_run(self._current_workflow_id, post_id)
        self._captured_screenshots = {}
        
        self.logger.info(f"Started validation run {self._current_run_id} for workflow {workflow_name}")
        return self._current_run_id
    
    def capture_click(
        self,
        action_index: int,
        click_x: int,
        click_y: int
    ) -> Optional[bytes]:
        """
        Capture screenshot before performing a click.
        Call this BEFORE the click is executed.
        
        Args:
            action_index: Index of action in workflow
            click_x: X coordinate of click
            click_y: Y coordinate of click
            
        Returns:
            Captured image bytes, or None if capture failed
        """
        if self._current_run_id is None:
            self.logger.warning("No active run. Call start_run() first.")
            return None
        
        image_data, _ = self.screenshot.capture_before_click(click_x, click_y)
        
        if image_data is None:
            self.logger.warning(f"Failed to capture screenshot for action {action_index}")
            return None
        
        self._captured_screenshots[action_index] = image_data
        
        self.db.save_run_screenshot(
            run_id=self._current_run_id,
            action_index=action_index,
            click_x=click_x,
            click_y=click_y,
            image_data=image_data
        )
        
        self.logger.debug(f"Captured click {action_index} at ({click_x}, {click_y})")
        return image_data
    
    def validate_run(self) -> WorkflowValidationResult:
        """
        Validate all captured clicks against baselines.
        Call this BEFORE clicking the success button.
        
        Returns:
            WorkflowValidationResult with success/failure info
        """
        if self._current_run_id is None:
            self.logger.error("No active run to validate")
            return WorkflowValidationResult(
                run_id=0,
                workflow_name="unknown",
                success=False,
                click_results=[],
                failure_index=None,
                failure_reason="No active run"
            )
        
        results = []
        failure_index = None
        failure_reason = None
        
        baselines = {b['action_index']: b for b in self.db.get_baselines(self._current_workflow_id)}
        
        for action_index, captured_image in sorted(self._captured_screenshots.items()):
            baseline = baselines.get(action_index)
            
            if baseline is None:
                results.append(ValidationResult(
                    action_index=action_index,
                    click_x=0,
                    click_y=0,
                    is_valid=True,
                    similarity_score=0.0,
                    baseline_exists=False
                ))
                self.logger.debug(f"No baseline for action {action_index}, skipping validation")
                continue
            
            threshold = baseline.get('confidence_threshold', self.default_threshold)
            is_match, score = quick_compare(
                baseline['baseline_image'],
                captured_image,
                threshold
            )
            
            self.db.update_run_screenshot(
                run_id=self._current_run_id,
                action_index=action_index,
                match_score=score,
                is_match=is_match
            )
            
            results.append(ValidationResult(
                action_index=action_index,
                click_x=baseline['click_x'],
                click_y=baseline['click_y'],
                is_valid=is_match,
                similarity_score=score,
                baseline_exists=True
            ))
            
            if not is_match and failure_index is None:
                failure_index = action_index
                failure_reason = f"Click {action_index} mismatch: {score:.2%} similarity (need {threshold:.2%})"
                self.logger.warning(failure_reason)
        
        validated_with_baselines = [r for r in results if r.baseline_exists]
        success = all(r.is_valid for r in validated_with_baselines) if validated_with_baselines else True
        
        status = 'success' if success else 'validation_failed'
        self.db.complete_run(
            run_id=self._current_run_id,
            status=status,
            failure_index=failure_index,
            failure_reason=failure_reason
        )
        
        result = WorkflowValidationResult(
            run_id=self._current_run_id,
            workflow_name=self._current_workflow_name or "unknown",
            success=success,
            click_results=results,
            failure_index=failure_index,
            failure_reason=failure_reason
        )
        
        self.logger.info(f"Validation complete: {'SUCCESS' if success else 'FAILED'} - {len(results)} clicks checked")
        
        self._current_run_id = None
        self._current_workflow_id = None
        self._current_workflow_name = None
        self._captured_screenshots = {}
        
        return result
    
    def abort_run(self, reason: str = "aborted") -> None:
        """Abort the current run without validation."""
        if self._current_run_id:
            self.db.complete_run(
                run_id=self._current_run_id,
                status='aborted',
                failure_reason=reason
            )
            self.logger.info(f"Run {self._current_run_id} aborted: {reason}")
        
        self._current_run_id = None
        self._current_workflow_id = None
        self._current_workflow_name = None
        self._captured_screenshots = {}
    
    def validate_single_click(
        self,
        workflow_name: str,
        action_index: int,
        captured_image: bytes
    ) -> Tuple[bool, float]:
        """
        Validate a single click against its baseline.
        Useful for real-time validation.
        
        Returns:
            Tuple of (is_valid, similarity_score)
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return True, 0.0
        
        baseline = self.db.get_baseline(workflow['id'], action_index)
        if not baseline:
            return True, 0.0
        
        threshold = baseline.get('confidence_threshold', self.default_threshold)
        return quick_compare(baseline['baseline_image'], captured_image, threshold)
    
    def should_trigger_self_healing(
        self,
        workflow_name: str,
        action_index: int,
        max_failures: int = 3
    ) -> bool:
        """
        Check if self-healing should be triggered for an action.
        
        Returns:
            True if consecutive failures exceed threshold
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return False
        
        count = self.db.count_consecutive_failures(workflow['id'], action_index)
        return count >= max_failures
    
    @property
    def is_run_active(self) -> bool:
        """Check if there's an active run."""
        return self._current_run_id is not None
