"""
Mouse Movement Recorder

Captures every mouse movement with microsecond precision for
behavioral biometric profiling.

Captures:
    - Movement trajectories with timestamps
    - Click events with duration
    - Scroll events with direction and magnitude
    - Idle micro-movements (jitter)
"""

from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional, Callable, Dict, Any
from collections import deque
from pathlib import Path
import time
import json
import threading
import queue
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class MouseEvent:
    """Single mouse event with all relevant data."""
    timestamp: float          # Unix timestamp (microsecond precision)
    event_type: str           # 'move', 'click', 'scroll', 'idle'
    x: int                    # Screen X coordinate
    y: int                    # Screen Y coordinate
    dx: Optional[int] = None  # Delta X (for relative movement)
    dy: Optional[int] = None  # Delta Y (for relative movement)
    button: Optional[str] = None  # 'left', 'right', 'middle'
    pressed: Optional[bool] = None  # True=down, False=up
    scroll_dx: Optional[int] = None  # Horizontal scroll
    scroll_dy: Optional[int] = None  # Vertical scroll
    velocity: Optional[float] = None  # Instantaneous velocity (pixels/sec)
    acceleration: Optional[float] = None  # Instantaneous acceleration

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class MovementSegment:
    """A complete movement from start to target click."""
    start_point: Tuple[int, int]
    end_point: Tuple[int, int]
    points: List[Tuple[float, int, int]]  # (timestamp, x, y)
    duration: float
    distance: float
    path_length: float
    peak_velocity: float
    avg_velocity: float
    has_overshoot: bool
    overshoot_distance: float
    click_duration: Optional[float] = None
    target_width: Optional[int] = None


class MouseRecorder:
    """
    Records mouse movements with high precision.

    Features:
        - Microsecond timestamp precision
        - Velocity and acceleration calculation
        - Movement segmentation
        - Jitter detection during idle
        - Thread-safe event collection
    """

    def __init__(
        self,
        sample_rate_hz: int = 1000,
        velocity_window_ms: int = 50,
        idle_threshold_ms: int = 500,
        jitter_detection: bool = True
    ):
        """
        Initialize mouse recorder.

        Args:
            sample_rate_hz: Target sample rate for movement capture
            velocity_window_ms: Window for velocity calculation
            idle_threshold_ms: Time threshold for idle detection
            jitter_detection: Enable micro-movement detection when idle
        """
        self.sample_rate = sample_rate_hz
        self.velocity_window_ms = velocity_window_ms
        self.idle_threshold_ms = idle_threshold_ms
        self.jitter_detection = jitter_detection

        # State
        self.events: List[MouseEvent] = []
        self.recording = False
        self.listener = None
        self._lock = threading.Lock()
        self._event_queue = queue.Queue()

        # Movement tracking
        self.last_position: Tuple[int, int] = (0, 0)
        self.last_time: float = 0
        self.last_velocity: float = 0

        # Velocity calculation buffer (circular)
        self.position_buffer: deque = deque(maxlen=20)

        # Movement segmentation
        self.current_segment_points: List[Tuple[float, int, int]] = []
        self.segment_start_time: Optional[float] = None
        self.segments: List[MovementSegment] = []

        # Click tracking
        self.button_press_times: Dict[str, float] = {}
        self.last_click_time: float = 0
        self.double_click_intervals: List[float] = []

        # Idle/jitter tracking
        self.last_movement_time: float = 0
        self.idle_positions: List[Tuple[float, int, int]] = []

        # Callbacks
        self.on_event: Optional[Callable[[MouseEvent], None]] = None
        self.on_segment_complete: Optional[Callable[[MovementSegment], None]] = None

    def start_recording(self) -> None:
        """Start recording mouse events."""
        try:
            from pynput import mouse
        except ImportError:
            logger.warning("pynput not available, using mock recorder")
            self._start_mock_recording()
            return

        with self._lock:
            self.events = []
            self.segments = []
            self.current_segment_points = []
            self.recording = True
            self.last_time = time.time()

        self.listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.listener.start()

        # Start processing thread
        self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processing_thread.start()

        logger.info("Mouse recording started")

    def _start_mock_recording(self) -> None:
        """Start mock recording for testing without pynput."""
        with self._lock:
            self.events = []
            self.segments = []
            self.recording = True
            self.last_time = time.time()
        logger.info("Mouse recording started (mock mode)")

    def stop_recording(self) -> List[MouseEvent]:
        """
        Stop recording and return events.

        Returns:
            List of all recorded mouse events
        """
        with self._lock:
            self.recording = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        # Finalize any in-progress segment
        self._finalize_current_segment()

        logger.info(f"Mouse recording stopped. Captured {len(self.events)} events, "
                   f"{len(self.segments)} segments")

        return self.events.copy()

    def _on_move(self, x: int, y: int) -> None:
        """Handle mouse movement."""
        if not self.recording:
            return

        now = time.time()

        # Calculate delta from last position
        dx = x - self.last_position[0]
        dy = y - self.last_position[1]
        dt = now - self.last_time

        # Calculate velocity
        distance = math.sqrt(dx * dx + dy * dy)
        velocity = distance / dt if dt > 0 else 0

        # Calculate acceleration
        acceleration = (velocity - self.last_velocity) / dt if dt > 0 else 0

        # Update position buffer for smoothed velocity
        self.position_buffer.append((now, x, y))

        event = MouseEvent(
            timestamp=now,
            event_type='move',
            x=x, y=y,
            dx=dx, dy=dy,
            velocity=velocity,
            acceleration=acceleration
        )

        self._queue_event(event)

        # Track for segment
        if self.segment_start_time is None:
            self.segment_start_time = now
        self.current_segment_points.append((now, x, y))

        # Update tracking state
        self.last_position = (x, y)
        self.last_time = now
        self.last_velocity = velocity
        self.last_movement_time = now

    def _on_click(self, x: int, y: int, button, pressed: bool) -> None:
        """Handle mouse click."""
        if not self.recording:
            return

        now = time.time()
        button_name = button.name if hasattr(button, 'name') else str(button)

        event = MouseEvent(
            timestamp=now,
            event_type='click',
            x=x, y=y,
            button=button_name,
            pressed=pressed
        )

        self._queue_event(event)

        if pressed:
            # Button down - track for duration
            self.button_press_times[button_name] = now

            # Track double-click interval
            if now - self.last_click_time < 0.5:
                interval = (now - self.last_click_time) * 1000
                self.double_click_intervals.append(interval)
            self.last_click_time = now

            # Finalize movement segment on click
            self._finalize_current_segment()
        else:
            # Button up - calculate duration
            if button_name in self.button_press_times:
                duration = now - self.button_press_times[button_name]
                # Update last segment with click duration
                if self.segments:
                    self.segments[-1].click_duration = duration * 1000  # ms
                del self.button_press_times[button_name]

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        """Handle mouse scroll."""
        if not self.recording:
            return

        event = MouseEvent(
            timestamp=time.time(),
            event_type='scroll',
            x=x, y=y,
            scroll_dx=dx,
            scroll_dy=dy
        )

        self._queue_event(event)

    def _queue_event(self, event: MouseEvent) -> None:
        """Add event to processing queue."""
        self._event_queue.put(event)

    def _process_events(self) -> None:
        """Process events from queue (runs in separate thread)."""
        while self.recording or not self._event_queue.empty():
            try:
                event = self._event_queue.get(timeout=0.1)

                with self._lock:
                    self.events.append(event)

                # Call callback if set
                if self.on_event:
                    self.on_event(event)

            except queue.Empty:
                # Check for idle jitter
                if self.jitter_detection and self.recording:
                    self._check_idle_jitter()

    def _check_idle_jitter(self) -> None:
        """Detect micro-movements during idle periods."""
        now = time.time()
        idle_duration = now - self.last_movement_time

        if idle_duration > self.idle_threshold_ms / 1000:
            # Record idle position for jitter analysis
            self.idle_positions.append((now, self.last_position[0], self.last_position[1]))

    def _finalize_current_segment(self) -> None:
        """Finalize and store current movement segment."""
        if len(self.current_segment_points) < 3:
            self.current_segment_points = []
            self.segment_start_time = None
            return

        points = self.current_segment_points
        start = (points[0][1], points[0][2])
        end = (points[-1][1], points[-1][2])

        # Calculate metrics
        duration = points[-1][0] - points[0][0]
        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        # Calculate path length
        path_length = 0
        velocities = []
        for i in range(1, len(points)):
            dx = points[i][1] - points[i-1][1]
            dy = points[i][2] - points[i-1][2]
            dt = points[i][0] - points[i-1][0]
            segment_dist = math.sqrt(dx*dx + dy*dy)
            path_length += segment_dist
            if dt > 0:
                velocities.append(segment_dist / dt)

        peak_velocity = max(velocities) if velocities else 0
        avg_velocity = sum(velocities) / len(velocities) if velocities else 0

        # Detect overshoot
        has_overshoot, overshoot_distance = self._detect_overshoot(points, end)

        segment = MovementSegment(
            start_point=start,
            end_point=end,
            points=points,
            duration=duration,
            distance=distance,
            path_length=path_length,
            peak_velocity=peak_velocity,
            avg_velocity=avg_velocity,
            has_overshoot=has_overshoot,
            overshoot_distance=overshoot_distance
        )

        self.segments.append(segment)

        if self.on_segment_complete:
            self.on_segment_complete(segment)

        # Reset
        self.current_segment_points = []
        self.segment_start_time = None

    def _detect_overshoot(
        self,
        points: List[Tuple[float, int, int]],
        end: Tuple[int, int]
    ) -> Tuple[bool, float]:
        """
        Detect if movement overshoots target.

        Returns:
            (has_overshoot, overshoot_distance)
        """
        if len(points) < 5:
            return False, 0.0

        # Check if any point is further from start than end
        start = (points[0][1], points[0][2])
        end_distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        max_overshoot = 0
        for _, x, y in points[:-1]:  # Exclude final point
            dist_from_start = math.sqrt((x - start[0])**2 + (y - start[1])**2)
            if dist_from_start > end_distance:
                overshoot = dist_from_start - end_distance
                max_overshoot = max(max_overshoot, overshoot)

        return max_overshoot > 5, max_overshoot  # 5 pixel threshold

    def get_events(self) -> List[MouseEvent]:
        """Get copy of current events."""
        with self._lock:
            return self.events.copy()

    def get_segments(self) -> List[MovementSegment]:
        """Get movement segments."""
        return self.segments.copy()

    def get_statistics(self) -> Dict[str, Any]:
        """Get recording statistics."""
        events = self.get_events()

        move_events = [e for e in events if e.event_type == 'move']
        click_events = [e for e in events if e.event_type == 'click']
        scroll_events = [e for e in events if e.event_type == 'scroll']

        velocities = [e.velocity for e in move_events if e.velocity is not None]

        return {
            'total_events': len(events),
            'move_events': len(move_events),
            'click_events': len(click_events),
            'scroll_events': len(scroll_events),
            'segments': len(self.segments),
            'avg_velocity': sum(velocities) / len(velocities) if velocities else 0,
            'max_velocity': max(velocities) if velocities else 0,
            'double_click_intervals': self.double_click_intervals.copy(),
            'recording_duration': events[-1].timestamp - events[0].timestamp if len(events) > 1 else 0
        }

    def save_to_file(self, path: str) -> None:
        """
        Save events to JSONL file.

        Args:
            path: Output file path
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, 'w') as f:
            for event in self.events:
                f.write(json.dumps(event.to_dict()) + '\n')

        logger.info(f"Saved {len(self.events)} mouse events to {path}")

    def save_segments_to_file(self, path: str) -> None:
        """Save movement segments to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        segments_data = []
        for seg in self.segments:
            segments_data.append({
                'start_point': seg.start_point,
                'end_point': seg.end_point,
                'duration': seg.duration,
                'distance': seg.distance,
                'path_length': seg.path_length,
                'peak_velocity': seg.peak_velocity,
                'avg_velocity': seg.avg_velocity,
                'has_overshoot': seg.has_overshoot,
                'overshoot_distance': seg.overshoot_distance,
                'click_duration': seg.click_duration,
                'point_count': len(seg.points)
            })

        with open(path, 'w') as f:
            json.dump(segments_data, f, indent=2)

    @staticmethod
    def load_from_file(path: str) -> List[MouseEvent]:
        """
        Load events from JSONL file.

        Args:
            path: Input file path

        Returns:
            List of MouseEvent objects
        """
        events = []
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                events.append(MouseEvent(**data))
        return events
