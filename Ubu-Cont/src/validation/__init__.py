"""
Visual Validation System for Workflow Automation.

Captures, stores, and compares screenshots around click points
to detect failures before they propagate.
"""

from .database import ValidationDatabase
from .screenshot_capture import ScreenshotCapture
from .image_comparator import ImageComparator, quick_compare
from .workflow_parser import WorkflowParser, WorkflowInfo, ClickAction
from .validator import WorkflowValidator, ValidationResult, WorkflowValidationResult
from .baseline_manager import BaselineManager

__all__ = [
    'ValidationDatabase',
    'ScreenshotCapture',
    'ImageComparator',
    'quick_compare',
    'WorkflowParser',
    'WorkflowInfo',
    'ClickAction',
    'WorkflowValidator',
    'ValidationResult',
    'WorkflowValidationResult',
    'BaselineManager',
]
