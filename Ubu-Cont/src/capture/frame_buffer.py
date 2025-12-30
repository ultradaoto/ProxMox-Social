"""
Frame Buffer Management

Provides thread-safe frame buffering with timestamp tracking.
"""

import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional, List, Tuple

import numpy as np


@dataclass
class TimestampedFrame:
    """Frame with capture timestamp."""
    frame: np.ndarray
    timestamp: float
    frame_number: int


class FrameBuffer:
    """
    Thread-safe frame buffer with configurable size.

    Stores recent frames for temporal analysis and comparison.
    """

    def __init__(self, max_size: int = 10, max_age_seconds: float = 5.0):
        """
        Initialize frame buffer.

        Args:
            max_size: Maximum number of frames to store
            max_age_seconds: Maximum age of frames before eviction
        """
        self.max_size = max_size
        self.max_age = max_age_seconds

        self._buffer: deque[TimestampedFrame] = deque(maxlen=max_size)
        self._lock = threading.RLock()
        self._frame_counter = 0

    def add(self, frame: np.ndarray, timestamp: Optional[float] = None) -> int:
        """
        Add a frame to the buffer.

        Args:
            frame: Image frame (numpy array)
            timestamp: Frame timestamp (uses current time if None)

        Returns:
            Frame number
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self._frame_counter += 1
            timestamped = TimestampedFrame(
                frame=frame.copy(),
                timestamp=timestamp,
                frame_number=self._frame_counter
            )
            self._buffer.append(timestamped)

            # Evict old frames
            self._evict_old()

            return self._frame_counter

    def get_latest(self) -> Optional[TimestampedFrame]:
        """Get the most recent frame."""
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
            return None

    def get_by_age(self, max_age: float) -> List[TimestampedFrame]:
        """
        Get all frames within a time window.

        Args:
            max_age: Maximum age in seconds

        Returns:
            List of frames within the time window
        """
        cutoff = time.time() - max_age
        with self._lock:
            return [f for f in self._buffer if f.timestamp >= cutoff]

    def get_frame_pair(self) -> Optional[Tuple[TimestampedFrame, TimestampedFrame]]:
        """
        Get the two most recent frames for comparison.

        Returns:
            Tuple of (previous_frame, current_frame) or None
        """
        with self._lock:
            if len(self._buffer) >= 2:
                return (self._buffer[-2], self._buffer[-1])
            return None

    def get_all(self) -> List[TimestampedFrame]:
        """Get all frames in buffer."""
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        """Clear all frames from buffer."""
        with self._lock:
            self._buffer.clear()

    def _evict_old(self) -> None:
        """Remove frames older than max_age."""
        cutoff = time.time() - self.max_age
        while self._buffer and self._buffer[0].timestamp < cutoff:
            self._buffer.popleft()

    def size(self) -> int:
        """Get current buffer size."""
        with self._lock:
            return len(self._buffer)

    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return self.size() == 0


class FrameDiffer:
    """
    Computes differences between frames for change detection.
    """

    def __init__(self, threshold: float = 30.0):
        """
        Initialize frame differ.

        Args:
            threshold: Pixel difference threshold (0-255)
        """
        self.threshold = threshold

    def compute_diff(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray
    ) -> Tuple[float, np.ndarray]:
        """
        Compute difference between two frames.

        Args:
            frame1: First frame
            frame2: Second frame

        Returns:
            Tuple of (change_percentage, diff_mask)
        """
        try:
            import cv2
        except ImportError:
            # Fallback without OpenCV
            diff = np.abs(frame1.astype(float) - frame2.astype(float))
            mask = diff.mean(axis=2) > self.threshold
            change_pct = mask.sum() / mask.size * 100
            return change_pct, mask.astype(np.uint8) * 255

        # Convert to grayscale
        if len(frame1.shape) == 3:
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        else:
            gray1, gray2 = frame1, frame2

        # Compute absolute difference
        diff = cv2.absdiff(gray1, gray2)

        # Threshold to get binary mask
        _, mask = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)

        # Calculate change percentage
        change_pct = np.count_nonzero(mask) / mask.size * 100

        return change_pct, mask

    def has_significant_change(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        min_change_pct: float = 1.0
    ) -> bool:
        """
        Check if there's significant change between frames.

        Args:
            frame1: First frame
            frame2: Second frame
            min_change_pct: Minimum change percentage to be significant

        Returns:
            True if change exceeds threshold
        """
        change_pct, _ = self.compute_diff(frame1, frame2)
        return change_pct >= min_change_pct

    def find_changed_regions(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        min_area: int = 100
    ) -> List[Tuple[int, int, int, int]]:
        """
        Find regions that changed between frames.

        Args:
            frame1: First frame
            frame2: Second frame
            min_area: Minimum contour area to include

        Returns:
            List of bounding boxes (x, y, width, height)
        """
        try:
            import cv2
        except ImportError:
            return []

        _, mask = self.compute_diff(frame1, frame2)

        # Find contours
        contours, _ = cv2.findContours(
            mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # Get bounding boxes for significant contours
        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= min_area:
                x, y, w, h = cv2.boundingRect(contour)
                boxes.append((x, y, w, h))

        return boxes


class ScreenStateTracker:
    """
    Tracks screen state changes over time.
    """

    def __init__(self, stable_threshold: float = 0.5, stable_frames: int = 3):
        """
        Initialize state tracker.

        Args:
            stable_threshold: Change percentage below which screen is stable
            stable_frames: Number of stable frames required
        """
        self.stable_threshold = stable_threshold
        self.stable_frames = stable_frames

        self._buffer = FrameBuffer(max_size=10)
        self._differ = FrameDiffer()
        self._consecutive_stable = 0
        self._last_significant_change = 0.0

    def update(self, frame: np.ndarray) -> bool:
        """
        Update with new frame.

        Args:
            frame: New screen frame

        Returns:
            True if screen is stable
        """
        self._buffer.add(frame)

        pair = self._buffer.get_frame_pair()
        if pair is None:
            return False

        prev, curr = pair
        change_pct, _ = self._differ.compute_diff(prev.frame, curr.frame)

        if change_pct < self.stable_threshold:
            self._consecutive_stable += 1
        else:
            self._consecutive_stable = 0
            self._last_significant_change = time.time()

        return self._consecutive_stable >= self.stable_frames

    def is_stable(self) -> bool:
        """Check if screen is currently stable."""
        return self._consecutive_stable >= self.stable_frames

    def time_since_change(self) -> float:
        """Get seconds since last significant change."""
        if self._last_significant_change == 0:
            return 0.0
        return time.time() - self._last_significant_change

    def wait_for_stable(self, timeout: float = 5.0) -> bool:
        """
        Wait for screen to become stable.

        Args:
            timeout: Maximum wait time

        Returns:
            True if screen became stable, False if timeout
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_stable():
                return True
            time.sleep(0.1)
        return False
