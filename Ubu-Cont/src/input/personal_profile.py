"""
Personal Profile Learning

Records and learns from real human input patterns
to create personalized behavior profiles.
"""

import json
import time
import logging
import statistics
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class MouseMovementSample:
    """A recorded mouse movement sample."""
    start: Tuple[int, int]
    end: Tuple[int, int]
    duration_ms: float
    distance: float
    path_length: float  # Total path length (may be > distance due to curves)
    overshoot: bool
    timestamp: str


@dataclass
class KeystrokeSample:
    """A recorded keystroke timing sample."""
    key: str
    prev_key: str
    delay_ms: float
    hold_duration_ms: float
    timestamp: str


@dataclass
class PersonalProfile:
    """Complete personal behavior profile."""
    name: str = "default"
    created: str = ""
    updated: str = ""

    # Mouse parameters (learned)
    mouse_avg_speed: float = 500.0  # pixels per second
    mouse_speed_variance: float = 100.0
    mouse_overshoot_rate: float = 0.15
    mouse_jitter_amount: float = 3.0
    fitts_law_a: float = 50.0
    fitts_law_b: float = 150.0

    # Keyboard parameters (learned)
    typing_wpm: float = 45.0
    typing_wpm_variance: float = 10.0
    typo_rate: float = 0.02
    key_hold_duration_ms: float = 80.0
    inter_key_interval_ms: float = 100.0

    # Recorded samples (for further learning)
    mouse_samples: List[Dict] = field(default_factory=list)
    keystroke_samples: List[Dict] = field(default_factory=list)


class ProfileRecorder:
    """
    Records human input for profile learning.

    Note: This runs on the Ubuntu VM but would need access
    to actual input device data for real recording.
    """

    def __init__(self, profile_path: str = None):
        """
        Initialize recorder.

        Args:
            profile_path: Path to save/load profile
        """
        self.profile_path = Path(profile_path) if profile_path else None
        self.profile = PersonalProfile()
        self.recording = False

        self._mouse_samples: List[MouseMovementSample] = []
        self._keystroke_samples: List[KeystrokeSample] = []
        self._last_mouse_pos: Optional[Tuple[int, int]] = None
        self._last_mouse_time: float = 0
        self._last_key: str = ""
        self._last_key_time: float = 0

    def start_recording(self) -> None:
        """Start recording input."""
        self.recording = True
        logger.info("Started recording input for profile")

    def stop_recording(self) -> None:
        """Stop recording and analyze data."""
        self.recording = False
        self._analyze_samples()
        logger.info("Stopped recording, analyzed samples")

    def record_mouse_move(
        self,
        x: int,
        y: int,
        path_points: List[Tuple[int, int]] = None
    ) -> None:
        """
        Record a mouse movement.

        Args:
            x, y: Current position
            path_points: Full path if available
        """
        if not self.recording:
            return

        current_time = time.time()

        if self._last_mouse_pos:
            start = self._last_mouse_pos
            end = (x, y)
            duration_ms = (current_time - self._last_mouse_time) * 1000

            import math
            distance = math.hypot(end[0] - start[0], end[1] - start[1])

            # Calculate path length
            path_length = distance
            if path_points and len(path_points) > 1:
                path_length = sum(
                    math.hypot(
                        path_points[i][0] - path_points[i-1][0],
                        path_points[i][1] - path_points[i-1][1]
                    )
                    for i in range(1, len(path_points))
                )

            # Detect overshoot (path significantly longer than distance)
            overshoot = path_length > distance * 1.1

            sample = MouseMovementSample(
                start=start,
                end=end,
                duration_ms=duration_ms,
                distance=distance,
                path_length=path_length,
                overshoot=overshoot,
                timestamp=datetime.now().isoformat()
            )
            self._mouse_samples.append(sample)

        self._last_mouse_pos = (x, y)
        self._last_mouse_time = current_time

    def record_keystroke(
        self,
        key: str,
        hold_duration_ms: float = 80.0
    ) -> None:
        """
        Record a keystroke.

        Args:
            key: Key pressed
            hold_duration_ms: How long key was held
        """
        if not self.recording:
            return

        current_time = time.time()

        if self._last_key:
            delay_ms = (current_time - self._last_key_time) * 1000

            sample = KeystrokeSample(
                key=key,
                prev_key=self._last_key,
                delay_ms=delay_ms,
                hold_duration_ms=hold_duration_ms,
                timestamp=datetime.now().isoformat()
            )
            self._keystroke_samples.append(sample)

        self._last_key = key
        self._last_key_time = current_time

    def _analyze_samples(self) -> None:
        """Analyze recorded samples and update profile."""
        if self._mouse_samples:
            self._analyze_mouse_samples()
        if self._keystroke_samples:
            self._analyze_keystroke_samples()

        self.profile.updated = datetime.now().isoformat()

        # Store samples in profile
        self.profile.mouse_samples = [asdict(s) for s in self._mouse_samples]
        self.profile.keystroke_samples = [asdict(s) for s in self._keystroke_samples]

    def _analyze_mouse_samples(self) -> None:
        """Analyze mouse movement samples."""
        # Calculate speeds
        speeds = []
        for sample in self._mouse_samples:
            if sample.duration_ms > 0:
                speed = sample.distance / (sample.duration_ms / 1000)
                speeds.append(speed)

        if speeds:
            self.profile.mouse_avg_speed = statistics.mean(speeds)
            if len(speeds) > 1:
                self.profile.mouse_speed_variance = statistics.stdev(speeds)

        # Calculate overshoot rate
        overshoots = [s.overshoot for s in self._mouse_samples]
        if overshoots:
            self.profile.mouse_overshoot_rate = sum(overshoots) / len(overshoots)

        # Estimate Fitts's Law parameters
        self._estimate_fitts_law()

    def _estimate_fitts_law(self) -> None:
        """Estimate Fitts's Law parameters from samples."""
        import math

        # Collect (ID, MT) pairs where ID = log2(D/W + 1)
        # Assume target width of 50 pixels for now
        target_width = 50

        data_points = []
        for sample in self._mouse_samples:
            if sample.distance > 10:  # Skip very short movements
                id_val = math.log2(sample.distance / target_width + 1)
                mt_val = sample.duration_ms
                data_points.append((id_val, mt_val))

        if len(data_points) < 5:
            return

        # Simple linear regression
        n = len(data_points)
        sum_x = sum(p[0] for p in data_points)
        sum_y = sum(p[1] for p in data_points)
        sum_xy = sum(p[0] * p[1] for p in data_points)
        sum_xx = sum(p[0] * p[0] for p in data_points)

        denom = n * sum_xx - sum_x * sum_x
        if denom != 0:
            b = (n * sum_xy - sum_x * sum_y) / denom
            a = (sum_y - b * sum_x) / n
            self.profile.fitts_law_a = max(0, a)
            self.profile.fitts_law_b = max(0, b)

    def _analyze_keystroke_samples(self) -> None:
        """Analyze keystroke timing samples."""
        delays = [s.delay_ms for s in self._keystroke_samples if s.delay_ms < 2000]
        holds = [s.hold_duration_ms for s in self._keystroke_samples]

        if delays:
            # Calculate WPM from average delay
            # 5 chars per word, delay in ms
            avg_delay = statistics.mean(delays)
            if avg_delay > 0:
                self.profile.typing_wpm = 60000 / (avg_delay * 5)

            if len(delays) > 1:
                self.profile.typing_wpm_variance = statistics.stdev(delays) / avg_delay * self.profile.typing_wpm

            self.profile.inter_key_interval_ms = avg_delay

        if holds:
            self.profile.key_hold_duration_ms = statistics.mean(holds)

    def save(self, path: str = None) -> None:
        """Save profile to file."""
        save_path = Path(path) if path else self.profile_path
        if not save_path:
            logger.warning("No path specified for saving profile")
            return

        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w') as f:
            json.dump(asdict(self.profile), f, indent=2)

        logger.info(f"Saved profile to {save_path}")

    def load(self, path: str = None) -> bool:
        """
        Load profile from file.

        Returns:
            True if loaded successfully
        """
        load_path = Path(path) if path else self.profile_path
        if not load_path or not load_path.exists():
            return False

        try:
            with open(load_path, 'r') as f:
                data = json.load(f)

            self.profile = PersonalProfile(**data)
            logger.info(f"Loaded profile from {load_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load profile: {e}")
            return False

    def get_mouse_config(self) -> Dict[str, Any]:
        """Get mouse configuration from profile."""
        return {
            'min_duration_ms': self.profile.fitts_law_a,
            'max_duration_ms': self.profile.fitts_law_a + self.profile.fitts_law_b * 3,
            'overshoot_probability': self.profile.mouse_overshoot_rate,
            'jitter_pixels': int(self.profile.mouse_jitter_amount),
            'fitts_law_a': self.profile.fitts_law_a,
            'fitts_law_b': self.profile.fitts_law_b,
        }

    def get_keyboard_config(self) -> Dict[str, Any]:
        """Get keyboard configuration from profile."""
        return {
            'base_wpm': int(self.profile.typing_wpm),
            'wpm_variance': int(self.profile.typing_wpm_variance),
            'typo_rate': self.profile.typo_rate,
        }
