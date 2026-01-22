"""
Self-Healing Workflow System

Automatically detects and fixes UI changes that break automation workflows.
When similarity drops below threshold, uses vision AI to find new element locations.
"""

from .config import (
    SIMILARITY_FAILURE_THRESHOLD,
    MAX_HEALING_ATTEMPTS,
    CONFIDENCE_THRESHOLD,
)
from .vision_locator import VisionLocator, LocatorResult
from .workflow_updater import WorkflowUpdater
from .healer import WorkflowHealer, HealingResult
from .events import HealingEventStore, get_healing_store

__all__ = [
    'WorkflowHealer',
    'HealingResult',
    'VisionLocator',
    'LocatorResult',
    'WorkflowUpdater',
    'HealingEventStore',
    'get_healing_store',
    'SIMILARITY_FAILURE_THRESHOLD',
    'MAX_HEALING_ATTEMPTS',
    'CONFIDENCE_THRESHOLD',
]
