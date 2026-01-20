"""
JSON-Based Workflow Executor

Loads and executes workflows from JSON recording files created via the web UI.
This replaces the hardcoded Python workflow steps with the user's saved recordings.

Includes Visual Validation System integration for screenshot-based failure detection.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.workflows.async_base_workflow import AsyncBaseWorkflow, StepResult, StepStatus, WorkflowResult
from src.utils.logger import get_logger

# Visual Validation imports
try:
    from src.validation import (
        ValidationDatabase,
        ScreenshotCapture,
        WorkflowValidator,
        BaselineManager,
        WorkflowParser
    )
    VALIDATION_AVAILABLE = True
except ImportError:
    VALIDATION_AVAILABLE = False

logger = get_logger(__name__)

# Validation database path
VALIDATION_DB_PATH = "/home/ultra/proxmox-social/Ubu-Cont/workflow-validation/validation.db"


class JSONWorkflow(AsyncBaseWorkflow):
    """
    Workflow executor that loads actions from JSON recording files.
    
    This class executes the exact sequence of actions saved via the web UI,
    ensuring the workflow matches what the user tested and verified.
    """
    
    def __init__(self, vnc, vision, input_injector, recording_path: str, platform_name: str, enable_validation: bool = True):
        """
        Initialize JSON workflow.
        
        Args:
            vnc: VNC capture instance
            vision: Vision controller instance
            input_injector: Input controller instance
            recording_path: Path to the JSON recording file
            platform_name: Name of the platform (instagram, skool, etc.)
            enable_validation: Enable visual validation system
        """
        super().__init__(vnc, vision, input_injector)
        self.recording_path = Path(recording_path)
        self._platform_name = platform_name
        self.recording_data: Dict[str, Any] = {}
        self.actions: List[Dict[str, Any]] = []
        self._step_names: List[str] = []
        
        # Visual validation
        self.enable_validation = enable_validation and VALIDATION_AVAILABLE
        self.validator: Optional[WorkflowValidator] = None
        self.screenshot_capture: Optional[ScreenshotCapture] = None
        self._validation_run_id: Optional[int] = None
        self._click_index: int = 0  # Track click number separately from action index
        
        if self.enable_validation:
            self._init_validation()
        
        # Load the recording
        self._load_recording()
    
    def _init_validation(self):
        """Initialize visual validation system."""
        try:
            db = ValidationDatabase(VALIDATION_DB_PATH)
            self.screenshot_capture = ScreenshotCapture(self.vnc, box_size=100)
            self.validator = WorkflowValidator(db, self.screenshot_capture, logger=logger)
            logger.info("Visual validation system initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize validation: {e}")
            self.enable_validation = False
    
    def _load_recording(self):
        """Load the JSON recording file."""
        if not self.recording_path.exists():
            raise FileNotFoundError(f"Recording file not found: {self.recording_path}")
        
        with open(self.recording_path, 'r') as f:
            self.recording_data = json.load(f)
        
        self.actions = self.recording_data.get('actions', [])
        
        # Generate step names from action descriptions
        self._step_names = []
        for i, action in enumerate(self.actions):
            desc = action.get('description', f'action_{i}')
            # Create a sanitized step name
            step_name = f"step_{i:02d}_{action.get('type', 'unknown')}"
            self._step_names.append(step_name)
        
        logger.info(f"Loaded {len(self.actions)} actions from {self.recording_path}")
    
    @property
    def platform_name(self) -> str:
        return self._platform_name
    
    @property
    def steps(self) -> List[str]:
        return self._step_names
    
    async def execute(self, post) -> WorkflowResult:
        """
        Execute the entire workflow from JSON.
        
        Overrides base execute to run actions sequentially from JSON.
        Includes visual validation for click actions.
        """
        self.current_post = post
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info(f"Starting {self.platform_name} workflow (JSON-based)")
        logger.info(f"Recording: {self.recording_path.name}")
        logger.info(f"Post ID: {post.id}")
        logger.info(f"Total actions: {len(self.actions)}")
        logger.info(f"Visual Validation: {'ENABLED' if self.enable_validation else 'DISABLED'}")
        logger.info("=" * 60)
        
        # Start validation run
        workflow_name = self.recording_path.stem  # e.g., 'linkedin_default'
        self._click_index = 0  # Reset click counter for this run
        if self.enable_validation and self.validator:
            try:
                self._validation_run_id = self.validator.start_run(workflow_name, post.id)
                logger.info(f"Started validation run {self._validation_run_id}")
            except Exception as e:
                logger.warning(f"Failed to start validation run: {e}")
        
        try:
            for i, action in enumerate(self.actions):
                action_type = action.get('type', 'unknown')
                description = action.get('description', f'Action {i+1}')
                
                logger.info(f"Action {i+1}/{len(self.actions)}: [{action_type}] {description}")
                
                result = await self._execute_action(action, i)
                
                if result.status == StepStatus.FAILED:
                    elapsed = time.time() - start_time
                    logger.error(f"Workflow failed at action {i+1}: {result.message}")
                    
                    # Abort validation run on failure
                    if self.enable_validation and self.validator and self.validator.is_run_active:
                        self.validator.abort_run(f"Action {i+1} failed: {result.message}")
                    
                    return WorkflowResult(
                        success=False,
                        post_id=post.id,
                        platform=self._platform_name,
                        steps_completed=i,
                        total_steps=len(self.actions),
                        error_message=result.message,
                        error_step=f"action_{i+1}_{action_type}",
                        duration_seconds=elapsed
                    )
            
            # Validate all captured clicks before marking success
            validation_passed = True
            validation_failure_msg = None
            
            if self.enable_validation and self.validator and self.validator.is_run_active:
                try:
                    val_result = self.validator.validate_run()
                    validation_passed = val_result.success
                    if not validation_passed:
                        validation_failure_msg = val_result.failure_reason
                        logger.warning(f"Visual validation FAILED: {validation_failure_msg}")
                except Exception as e:
                    logger.error(f"Validation error: {e}")
                    # Don't fail workflow on validation error, just log it
            
            elapsed = time.time() - start_time
            
            if validation_passed:
                logger.info(f"Workflow completed successfully in {elapsed:.1f}s")
                return WorkflowResult(
                    success=True,
                    post_id=post.id,
                    platform=self._platform_name,
                    steps_completed=len(self.actions),
                    total_steps=len(self.actions),
                    duration_seconds=elapsed
                )
            else:
                logger.warning(f"Workflow actions completed but validation failed in {elapsed:.1f}s")
                return WorkflowResult(
                    success=False,
                    post_id=post.id,
                    platform=self._platform_name,
                    steps_completed=len(self.actions),
                    total_steps=len(self.actions),
                    error_message=f"Visual validation failed: {validation_failure_msg}",
                    error_step="validation",
                    duration_seconds=elapsed
                )
            
        except Exception as e:
            elapsed = time.time() - start_time
            logger.exception(f"Workflow error: {e}")
            
            # Abort validation on exception
            if self.enable_validation and self.validator and self.validator.is_run_active:
                self.validator.abort_run(str(e))
            
            return WorkflowResult(
                success=False,
                post_id=post.id if post else "unknown",
                platform=self._platform_name,
                steps_completed=0,
                total_steps=len(self.actions),
                error_message=str(e),
                error_step="unknown",
                duration_seconds=elapsed
            )
    
    async def _execute_action(self, action: Dict[str, Any], index: int) -> StepResult:
        """Execute a single action from the JSON recording."""
        action_type = action.get('type', 'unknown')
        description = action.get('description', '')
        
        # Handle delay_before_ms
        delay_before = action.get('delay_before_ms', 0) / 1000.0
        if delay_before > 0:
            logger.debug(f"Waiting {delay_before}s before action...")
            await asyncio.sleep(delay_before)
        
        try:
            if action_type == 'click':
                return await self._execute_click(action, index)
            
            elif action_type == 'double_click':
                return await self._execute_double_click(action, index)
            
            elif action_type == 'right_click':
                return await self._execute_right_click(action, index)
            
            elif action_type == 'wait':
                return await self._execute_wait(action)
            
            elif action_type == 'key':
                return await self._execute_key(action)
            
            elif action_type == 'type':
                return await self._execute_type(action)
            
            elif action_type == 'paste':
                return await self._execute_paste(action)
            
            elif action_type == 'scroll':
                return await self._execute_scroll(action)
            
            elif action_type == 'wait_for_change':
                return await self._execute_wait_for_change(action)
            
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return StepResult(StepStatus.SKIPPED, f"Unknown action type: {action_type}")
                
        except Exception as e:
            logger.error(f"Action failed: {e}")
            return StepResult(StepStatus.FAILED, str(e))
    
    async def _capture_for_validation(self, x: int, y: int):
        """Capture screenshot for validation before click. Uses click_index, not action_index."""
        if self.enable_validation and self.validator and self.validator.is_run_active:
            try:
                click_idx = self._click_index
                await asyncio.to_thread(
                    self.validator.capture_click,
                    click_idx, x, y
                )
                logger.debug(f"Captured validation screenshot for click {click_idx} at ({x}, {y})")
                self._click_index += 1  # Increment after capture
            except Exception as e:
                logger.warning(f"Failed to capture validation screenshot: {e}")
    
    async def _execute_click(self, action: Dict[str, Any], action_index: int = 0) -> StepResult:
        """Execute a click action."""
        x = action.get('x', 0)
        y = action.get('y', 0)
        button = action.get('button', 'left')
        description = action.get('description', '')
        
        logger.info(f"Clicking at ({x}, {y}) - {description}")
        
        # Capture screenshot BEFORE click for validation
        await self._capture_for_validation(x, y)
        
        await asyncio.to_thread(self.input.move_to, x, y)
        await asyncio.sleep(0.1)
        await asyncio.to_thread(self.input.click, button)
        await asyncio.sleep(0.2)
        
        return StepResult(StepStatus.SUCCESS, f"Clicked at ({x}, {y})")
    
    async def _execute_double_click(self, action: Dict[str, Any], action_index: int = 0) -> StepResult:
        """Execute a double-click action."""
        x = action.get('x', 0)
        y = action.get('y', 0)
        description = action.get('description', '')
        
        logger.info(f"Double-clicking at ({x}, {y}) - {description}")
        
        # Capture screenshot BEFORE click for validation
        await self._capture_for_validation(x, y)
        
        await asyncio.to_thread(self.input.move_to, x, y)
        await asyncio.sleep(0.1)
        await asyncio.to_thread(self.input.click, 'left')
        await asyncio.sleep(0.1)
        await asyncio.to_thread(self.input.click, 'left')
        await asyncio.sleep(0.2)
        
        return StepResult(StepStatus.SUCCESS, f"Double-clicked at ({x}, {y})")
    
    async def _execute_right_click(self, action: Dict[str, Any], action_index: int = 0) -> StepResult:
        """Execute a right-click action."""
        x = action.get('x', 0)
        y = action.get('y', 0)
        description = action.get('description', '')
        
        logger.info(f"Right-clicking at ({x}, {y}) - {description}")
        
        # Capture screenshot BEFORE click for validation
        await self._capture_for_validation(x, y)
        
        await asyncio.to_thread(self.input.move_to, x, y)
        await asyncio.sleep(0.1)
        await asyncio.to_thread(self.input.click, 'right')
        await asyncio.sleep(0.2)
        
        return StepResult(StepStatus.SUCCESS, f"Right-clicked at ({x}, {y})")
    
    async def _execute_wait(self, action: Dict[str, Any]) -> StepResult:
        """Execute a wait action."""
        delay_ms = action.get('delay_ms', 1000)
        description = action.get('description', '')
        
        delay_sec = delay_ms / 1000.0
        logger.info(f"Waiting {delay_sec}s - {description}")
        
        await asyncio.sleep(delay_sec)
        
        return StepResult(StepStatus.SUCCESS, f"Waited {delay_sec}s")
    
    async def _execute_key(self, action: Dict[str, Any]) -> StepResult:
        """Execute a key press action."""
        key = action.get('key', '')
        ctrl = action.get('ctrl', False)
        shift = action.get('shift', False)
        description = action.get('description', '')
        
        key_desc = f"{'Ctrl+' if ctrl else ''}{'Shift+' if shift else ''}{key}"
        logger.info(f"Pressing key: {key_desc} - {description}")
        
        if ctrl and shift:
            await asyncio.to_thread(self.input.hotkey, 'ctrl', 'shift', key)
        elif ctrl:
            await asyncio.to_thread(self.input.hotkey, 'ctrl', key)
        elif shift:
            await asyncio.to_thread(self.input.hotkey, 'shift', key)
        else:
            await asyncio.to_thread(self.input.keyboard._send_key, key, 'press')
        
        await asyncio.sleep(0.1)
        
        return StepResult(StepStatus.SUCCESS, f"Pressed {key_desc}")
    
    async def _execute_type(self, action: Dict[str, Any]) -> StepResult:
        """Execute a type text action."""
        text = action.get('text', '')
        description = action.get('description', '')
        
        logger.info(f"Typing text: {text[:30]}... - {description}")
        
        for char in text:
            await asyncio.to_thread(self.input.keyboard._send_key, char, 'press')
            await asyncio.sleep(0.05)
        
        return StepResult(StepStatus.SUCCESS, f"Typed {len(text)} characters")
    
    async def _execute_paste(self, action: Dict[str, Any]) -> StepResult:
        """Execute a paste action (Ctrl+V)."""
        description = action.get('description', '')
        
        logger.info(f"Pasting from clipboard - {description}")
        
        await asyncio.to_thread(self.input.hotkey, 'ctrl', 'v')
        await asyncio.sleep(0.2)
        
        return StepResult(StepStatus.SUCCESS, "Pasted from clipboard")
    
    async def _execute_scroll(self, action: Dict[str, Any]) -> StepResult:
        """Execute a scroll action."""
        delta = action.get('delta', 0)
        description = action.get('description', '')
        
        logger.info(f"Scrolling delta={delta} - {description}")
        
        await asyncio.to_thread(self.input.scroll_raw, delta)
        await asyncio.sleep(0.2)
        
        return StepResult(StepStatus.SUCCESS, f"Scrolled {delta}")
    
    async def _execute_wait_for_change(self, action: Dict[str, Any]) -> StepResult:
        """Execute a wait-for-screen-change action."""
        import numpy as np
        from PIL import Image
        
        timeout_ms = action.get('timeout_ms', 5000)
        threshold = action.get('threshold', 10)
        description = action.get('description', '')
        
        logger.info(f"Waiting for screen change (timeout={timeout_ms}ms) - {description}")
        
        # Capture initial frame
        initial_frame = await asyncio.to_thread(self.vnc.capture_frame)
        if initial_frame is None:
            return StepResult(StepStatus.FAILED, "Could not capture initial frame")
        
        initial_np = np.array(initial_frame)
        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0
        
        while (time.time() - start_time) < timeout_sec:
            await asyncio.sleep(0.2)
            
            current_frame = await asyncio.to_thread(self.vnc.capture_frame)
            if current_frame is None:
                continue
            
            current_np = np.array(current_frame)
            
            if current_np.shape != initial_np.shape:
                return StepResult(StepStatus.SUCCESS, "Screen changed (resolution)")
            
            diff = np.abs(current_np.astype(np.int16) - initial_np.astype(np.int16))
            if diff.mean() > threshold:
                return StepResult(StepStatus.SUCCESS, f"Screen changed (diff={diff.mean():.1f})")
        
        return StepResult(StepStatus.SUCCESS, "Wait timeout (continuing)")
    
    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a step by name - not used in JSON workflow, but required by base class."""
        # Find the action by step name
        for i, name in enumerate(self._step_names):
            if name == step_name:
                return await self._execute_action(self.actions[i], i)
        
        return StepResult(StepStatus.FAILED, f"Step not found: {step_name}")


def create_instagram_workflow(vnc, vision, input_injector) -> JSONWorkflow:
    """Factory function to create Instagram workflow from JSON."""
    recording_path = Path(__file__).parent.parent.parent / "recordings" / "instagram_default.json"
    return JSONWorkflow(vnc, vision, input_injector, str(recording_path), "Instagram")


def create_skool_workflow(vnc, vision, input_injector) -> JSONWorkflow:
    """Factory function to create Skool workflow from JSON."""
    recording_path = Path(__file__).parent.parent.parent / "recordings" / "skool_default.json"
    return JSONWorkflow(vnc, vision, input_injector, str(recording_path), "Skool")


def create_facebook_workflow(vnc, vision, input_injector) -> JSONWorkflow:
    """Factory function to create Facebook workflow from JSON."""
    recording_path = Path(__file__).parent.parent.parent / "recordings" / "facebook_default.json"
    return JSONWorkflow(vnc, vision, input_injector, str(recording_path), "Facebook")


def create_linkedin_workflow(vnc, vision, input_injector) -> JSONWorkflow:
    """Factory function to create LinkedIn workflow from JSON."""
    recording_path = Path(__file__).parent.parent.parent / "recordings" / "linkedin_default.json"
    return JSONWorkflow(vnc, vision, input_injector, str(recording_path), "LinkedIn")
