"""
Element Tracker

Tracks UI elements across frames for stability and identification.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple, Set
from collections import defaultdict

import numpy as np

from .omniparser import UIElement

logger = logging.getLogger(__name__)


@dataclass
class TrackedElement:
    """An element being tracked across frames."""
    id: str
    element: UIElement
    first_seen: float
    last_seen: float
    frame_count: int = 1
    stable: bool = False
    history: List[Tuple[float, UIElement]] = field(default_factory=list)

    @property
    def age(self) -> float:
        """Seconds since first seen."""
        return time.time() - self.first_seen

    @property
    def time_since_update(self) -> float:
        """Seconds since last update."""
        return time.time() - self.last_seen

    def update(self, element: UIElement):
        """Update with new detection."""
        self.element = element
        self.last_seen = time.time()
        self.frame_count += 1
        self.history.append((self.last_seen, element))

        # Keep history limited
        if len(self.history) > 30:
            self.history = self.history[-30:]


class ElementTracker:
    """
    Tracks UI elements across multiple frames.

    Provides stable element identification and change detection.
    """

    def __init__(
        self,
        iou_threshold: float = 0.5,
        stable_frames: int = 3,
        max_age: float = 2.0
    ):
        """
        Initialize element tracker.

        Args:
            iou_threshold: IoU threshold for matching elements
            stable_frames: Frames needed to consider element stable
            max_age: Maximum seconds before removing untracked element
        """
        self.iou_threshold = iou_threshold
        self.stable_frames = stable_frames
        self.max_age = max_age

        self._tracked: Dict[str, TrackedElement] = {}
        self._next_id = 0
        self._frame_count = 0

    def update(self, elements: List[UIElement]) -> List[TrackedElement]:
        """
        Update tracker with new frame's elements.

        Args:
            elements: Detected elements in current frame

        Returns:
            List of tracked elements (includes stability info)
        """
        current_time = time.time()
        self._frame_count += 1

        # Match new elements to tracked elements
        matched_ids: Set[str] = set()
        unmatched_elements: List[UIElement] = []

        for element in elements:
            best_match_id = None
            best_iou = 0.0

            for track_id, tracked in self._tracked.items():
                if track_id in matched_ids:
                    continue

                iou = self._calculate_iou(element.bbox, tracked.element.bbox)
                if iou > self.iou_threshold and iou > best_iou:
                    best_iou = iou
                    best_match_id = track_id

            if best_match_id:
                # Update existing track
                self._tracked[best_match_id].update(element)
                matched_ids.add(best_match_id)
            else:
                # New element
                unmatched_elements.append(element)

        # Create new tracks for unmatched elements
        for element in unmatched_elements:
            track_id = f"elem_{self._next_id}"
            self._next_id += 1

            self._tracked[track_id] = TrackedElement(
                id=track_id,
                element=element,
                first_seen=current_time,
                last_seen=current_time,
            )

        # Update stability and remove stale tracks
        stale_ids = []
        for track_id, tracked in self._tracked.items():
            # Update stability
            tracked.stable = tracked.frame_count >= self.stable_frames

            # Mark stale tracks
            if tracked.time_since_update > self.max_age:
                stale_ids.append(track_id)

        for track_id in stale_ids:
            del self._tracked[track_id]

        return list(self._tracked.values())

    def _calculate_iou(
        self,
        bbox1: Tuple[int, int, int, int],
        bbox2: Tuple[int, int, int, int]
    ) -> float:
        """
        Calculate Intersection over Union of two bounding boxes.

        Args:
            bbox1: First box (x, y, w, h)
            bbox2: Second box (x, y, w, h)

        Returns:
            IoU value (0-1)
        """
        x1, y1, w1, h1 = bbox1
        x2, y2, w2, h2 = bbox2

        # Calculate intersection
        xi1 = max(x1, x2)
        yi1 = max(y1, y2)
        xi2 = min(x1 + w1, x2 + w2)
        yi2 = min(y1 + h1, y2 + h2)

        if xi2 <= xi1 or yi2 <= yi1:
            return 0.0

        intersection = (xi2 - xi1) * (yi2 - yi1)

        # Calculate union
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def get_stable_elements(self) -> List[TrackedElement]:
        """Get all stable (reliably tracked) elements."""
        return [t for t in self._tracked.values() if t.stable]

    def get_element_by_id(self, element_id: str) -> Optional[TrackedElement]:
        """Get tracked element by ID."""
        return self._tracked.get(element_id)

    def find_by_label(self, label: str, partial: bool = True) -> Optional[TrackedElement]:
        """
        Find tracked element by label.

        Args:
            label: Label to search for
            partial: Allow partial matching

        Returns:
            Matching TrackedElement or None
        """
        label_lower = label.lower()
        for tracked in self._tracked.values():
            elem_label = tracked.element.label.lower()
            if partial:
                if label_lower in elem_label:
                    return tracked
            else:
                if label_lower == elem_label:
                    return tracked
        return None

    def find_by_type(self, element_type: str) -> List[TrackedElement]:
        """Find all tracked elements of a type."""
        return [
            t for t in self._tracked.values()
            if t.element.element_type == element_type
        ]

    def find_at_point(self, x: int, y: int) -> Optional[TrackedElement]:
        """Find tracked element at a screen point."""
        for tracked in self._tracked.values():
            if tracked.element.contains_point(x, y):
                return tracked
        return None

    def get_new_elements(self, since_frames: int = 5) -> List[TrackedElement]:
        """Get elements that appeared recently."""
        return [
            t for t in self._tracked.values()
            if t.frame_count <= since_frames
        ]

    def get_disappeared_elements(self, within_seconds: float = 1.0) -> List[str]:
        """Get IDs of elements that recently disappeared."""
        cutoff = time.time() - within_seconds
        return [
            track_id for track_id, tracked in self._tracked.items()
            if tracked.last_seen < cutoff and tracked.time_since_update < self.max_age
        ]

    def clear(self):
        """Clear all tracked elements."""
        self._tracked.clear()

    @property
    def count(self) -> int:
        """Number of currently tracked elements."""
        return len(self._tracked)

    @property
    def stable_count(self) -> int:
        """Number of stable elements."""
        return len(self.get_stable_elements())


class ElementChangeDetector:
    """
    Detects changes in UI elements between frames.
    """

    def __init__(self):
        self._previous_elements: Dict[str, UIElement] = {}
        self._changes: List[Dict] = []

    def update(self, tracked_elements: List[TrackedElement]) -> List[Dict]:
        """
        Update with tracked elements and detect changes.

        Args:
            tracked_elements: Current tracked elements

        Returns:
            List of changes detected
        """
        changes = []
        current_ids = set()

        for tracked in tracked_elements:
            elem_id = tracked.id
            current_ids.add(elem_id)

            if elem_id not in self._previous_elements:
                # New element appeared
                changes.append({
                    'type': 'appeared',
                    'element_id': elem_id,
                    'element': tracked.element,
                })
            else:
                # Check for changes
                prev = self._previous_elements[elem_id]
                curr = tracked.element

                # Position change
                if abs(prev.center_x - curr.center_x) > 5 or \
                   abs(prev.center_y - curr.center_y) > 5:
                    changes.append({
                        'type': 'moved',
                        'element_id': elem_id,
                        'from': prev.center,
                        'to': curr.center,
                    })

                # Label change
                if prev.label != curr.label:
                    changes.append({
                        'type': 'label_changed',
                        'element_id': elem_id,
                        'from': prev.label,
                        'to': curr.label,
                    })

        # Check for disappeared elements
        for elem_id in self._previous_elements:
            if elem_id not in current_ids:
                changes.append({
                    'type': 'disappeared',
                    'element_id': elem_id,
                })

        # Update previous state
        self._previous_elements = {
            t.id: t.element for t in tracked_elements
        }

        self._changes = changes
        return changes

    def get_last_changes(self) -> List[Dict]:
        """Get changes from last update."""
        return self._changes
