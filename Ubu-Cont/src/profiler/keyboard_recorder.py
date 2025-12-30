"""
Keyboard Event Recorder

Captures keystroke timing with digraph analysis for
behavioral biometric profiling.

Captures:
    - Key press/release with microsecond timing
    - Inter-key intervals
    - Key hold durations
    - Digraph (letter pair) timing
    - Error rate and correction patterns
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Callable, Any, Tuple
from collections import defaultdict
from pathlib import Path
import time
import json
import threading
import queue
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class KeyEvent:
    """Single keyboard event."""
    timestamp: float          # Unix timestamp (microsecond precision)
    event_type: str           # 'press', 'release'
    key: str                  # Key name or character
    key_code: Optional[int] = None  # Virtual key code
    modifiers: Optional[List[str]] = None  # ['shift', 'ctrl', 'alt']
    hold_duration: Optional[float] = None  # For release events (ms)
    inter_key_interval: Optional[float] = None  # Time since last key (ms)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class TypingSession:
    """A continuous typing session."""
    start_time: float
    end_time: float
    text_typed: str
    key_count: int
    word_count: int
    error_count: int  # Backspaces
    wpm: float
    accuracy: float
    avg_iki: float  # Average inter-key interval
    digraph_timings: Dict[str, List[float]]


class KeyboardRecorder:
    """
    Records keyboard events with timing analysis.

    Features:
        - Microsecond timestamp precision
        - Inter-key interval (IKI) tracking
        - Key hold duration measurement
        - Digraph timing analysis
        - Error detection and correction tracking
        - Burst pattern detection
    """

    def __init__(
        self,
        track_digraphs: bool = True,
        max_digraph_interval_ms: float = 2000,
        burst_threshold_ms: float = 100
    ):
        """
        Initialize keyboard recorder.

        Args:
            track_digraphs: Enable digraph timing analysis
            max_digraph_interval_ms: Max interval for digraph consideration
            burst_threshold_ms: Threshold for burst typing detection
        """
        self.track_digraphs = track_digraphs
        self.max_digraph_interval = max_digraph_interval_ms / 1000
        self.burst_threshold = burst_threshold_ms / 1000

        # State
        self.events: List[KeyEvent] = []
        self.recording = False
        self.listener = None
        self._lock = threading.Lock()
        self._event_queue = queue.Queue()

        # Timing tracking
        self.key_press_times: Dict[str, float] = {}
        self.last_key_time: float = 0
        self.last_key: Optional[str] = None
        self.current_modifiers: set = set()

        # Digraph tracking
        self.digraph_times: Dict[str, List[float]] = defaultdict(list)

        # Text tracking
        self.typed_buffer: List[str] = []
        self.error_count: int = 0

        # Session tracking
        self.sessions: List[TypingSession] = []
        self.current_session_start: Optional[float] = None
        self.session_keys: List[str] = []
        self.pause_threshold = 5.0  # 5 seconds = new session

        # Statistics
        self.iki_values: List[float] = []  # All inter-key intervals
        self.hold_durations: Dict[str, List[float]] = defaultdict(list)
        self.burst_sequences: List[List[Tuple[str, float]]] = []

        # Callbacks
        self.on_event: Optional[Callable[[KeyEvent], None]] = None
        self.on_session_complete: Optional[Callable[[TypingSession], None]] = None

    def start_recording(self) -> None:
        """Start recording keyboard events."""
        try:
            from pynput import keyboard
        except ImportError:
            logger.warning("pynput not available, using mock recorder")
            self._start_mock_recording()
            return

        with self._lock:
            self.events = []
            self.sessions = []
            self.digraph_times = defaultdict(list)
            self.typed_buffer = []
            self.error_count = 0
            self.iki_values = []
            self.hold_durations = defaultdict(list)
            self.recording = True
            self.last_key_time = time.time()

        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()

        # Start processing thread
        self._processing_thread = threading.Thread(target=self._process_events, daemon=True)
        self._processing_thread.start()

        logger.info("Keyboard recording started")

    def _start_mock_recording(self) -> None:
        """Start mock recording for testing without pynput."""
        with self._lock:
            self.events = []
            self.sessions = []
            self.recording = True
            self.last_key_time = time.time()
        logger.info("Keyboard recording started (mock mode)")

    def stop_recording(self) -> List[KeyEvent]:
        """
        Stop recording and return events.

        Returns:
            List of all recorded keyboard events
        """
        with self._lock:
            self.recording = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        # Finalize current session
        self._finalize_current_session()

        logger.info(f"Keyboard recording stopped. Captured {len(self.events)} events, "
                   f"{len(self.sessions)} typing sessions")

        return self.events.copy()

    def _key_to_string(self, key) -> str:
        """Convert pynput key to string representation."""
        try:
            # Character key
            return key.char if key.char else str(key).replace('Key.', '')
        except AttributeError:
            # Special key
            return str(key).replace('Key.', '')

    def _is_modifier(self, key_str: str) -> bool:
        """Check if key is a modifier."""
        modifiers = {'shift', 'shift_r', 'ctrl', 'ctrl_r', 'ctrl_l',
                    'alt', 'alt_r', 'alt_l', 'cmd', 'cmd_r'}
        return key_str.lower() in modifiers

    def _on_press(self, key) -> None:
        """Handle key press."""
        if not self.recording:
            return

        now = time.time()
        key_str = self._key_to_string(key)

        # Update modifiers
        if self._is_modifier(key_str):
            base_modifier = key_str.replace('_r', '').replace('_l', '')
            self.current_modifiers.add(base_modifier)

        # Calculate inter-key interval
        iki = (now - self.last_key_time) * 1000 if self.last_key_time else None

        # Record digraph timing
        if self.track_digraphs and self.last_key and iki:
            if iki < self.max_digraph_interval * 1000:
                digraph = f"{self.last_key}_{key_str}"
                self.digraph_times[digraph].append(iki)

        # Check for new session (long pause)
        if iki and iki > self.pause_threshold * 1000:
            self._finalize_current_session()

        # Start new session if needed
        if self.current_session_start is None:
            self.current_session_start = now
            self.session_keys = []

        # Track for session
        self.session_keys.append(key_str)

        # Track text
        if len(key_str) == 1:
            self.typed_buffer.append(key_str)
        elif key_str == 'space':
            self.typed_buffer.append(' ')
        elif key_str == 'backspace':
            if self.typed_buffer:
                self.typed_buffer.pop()
            self.error_count += 1
        elif key_str == 'enter':
            self.typed_buffer.append('\n')

        # Track IKI
        if iki is not None:
            self.iki_values.append(iki)

        event = KeyEvent(
            timestamp=now,
            event_type='press',
            key=key_str,
            modifiers=list(self.current_modifiers) if self.current_modifiers else None,
            inter_key_interval=iki
        )

        self._queue_event(event)

        # Track for hold duration
        self.key_press_times[key_str] = now
        self.last_key = key_str
        self.last_key_time = now

    def _on_release(self, key) -> None:
        """Handle key release."""
        if not self.recording:
            return

        now = time.time()
        key_str = self._key_to_string(key)

        # Update modifiers
        if self._is_modifier(key_str):
            base_modifier = key_str.replace('_r', '').replace('_l', '')
            self.current_modifiers.discard(base_modifier)

        # Calculate hold duration
        hold_duration = None
        if key_str in self.key_press_times:
            hold_duration = (now - self.key_press_times[key_str]) * 1000
            self.hold_durations[key_str].append(hold_duration)
            del self.key_press_times[key_str]

        event = KeyEvent(
            timestamp=now,
            event_type='release',
            key=key_str,
            modifiers=list(self.current_modifiers) if self.current_modifiers else None,
            hold_duration=hold_duration
        )

        self._queue_event(event)

    def _queue_event(self, event: KeyEvent) -> None:
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
                pass

    def _finalize_current_session(self) -> None:
        """Finalize and store current typing session."""
        if self.current_session_start is None or not self.session_keys:
            return

        now = time.time()
        text = ''.join(self.typed_buffer)
        duration = now - self.current_session_start

        # Calculate WPM
        word_count = len(text.split())
        wpm = (word_count / duration) * 60 if duration > 0 else 0

        # Calculate accuracy
        total_keys = len(self.session_keys)
        accuracy = 1 - (self.error_count / total_keys) if total_keys > 0 else 1.0

        # Average IKI for session
        session_ikis = [e.inter_key_interval for e in self.events
                       if e.inter_key_interval and e.timestamp >= self.current_session_start]
        avg_iki = sum(session_ikis) / len(session_ikis) if session_ikis else 0

        session = TypingSession(
            start_time=self.current_session_start,
            end_time=now,
            text_typed=text,
            key_count=total_keys,
            word_count=word_count,
            error_count=self.error_count,
            wpm=wpm,
            accuracy=accuracy,
            avg_iki=avg_iki,
            digraph_timings=dict(self.digraph_times)
        )

        self.sessions.append(session)

        if self.on_session_complete:
            self.on_session_complete(session)

        # Reset
        self.current_session_start = None
        self.session_keys = []
        self.error_count = 0
        self.digraph_times = defaultdict(list)

    def get_events(self) -> List[KeyEvent]:
        """Get copy of current events."""
        with self._lock:
            return self.events.copy()

    def get_digraph_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get statistics for each digraph.

        Returns:
            Dict mapping digraph to {mean, std, min, max, count}
        """
        import numpy as np

        stats = {}
        for digraph, times in self.digraph_times.items():
            if len(times) >= 3:  # Need enough samples
                stats[digraph] = {
                    'mean': float(np.mean(times)),
                    'std': float(np.std(times)),
                    'min': float(np.min(times)),
                    'max': float(np.max(times)),
                    'count': len(times)
                }
        return stats

    def get_hold_duration_stats(self) -> Dict[str, Dict[str, float]]:
        """Get key hold duration statistics."""
        import numpy as np

        stats = {}
        for key, durations in self.hold_durations.items():
            if len(durations) >= 3:
                stats[key] = {
                    'mean': float(np.mean(durations)),
                    'std': float(np.std(durations)),
                    'min': float(np.min(durations)),
                    'max': float(np.max(durations)),
                    'count': len(durations)
                }
        return stats

    def get_statistics(self) -> Dict[str, Any]:
        """Get recording statistics."""
        import numpy as np

        events = self.get_events()
        press_events = [e for e in events if e.event_type == 'press']

        # IKI stats
        ikis = [e.inter_key_interval for e in press_events if e.inter_key_interval]

        # Calculate WPM from all text
        text = ''.join(self.typed_buffer)
        duration = events[-1].timestamp - events[0].timestamp if len(events) > 1 else 0
        word_count = len(text.split())
        wpm = (word_count / duration) * 60 if duration > 0 else 0

        return {
            'total_events': len(events),
            'press_events': len(press_events),
            'unique_keys': len(set(e.key for e in press_events)),
            'total_errors': self.error_count,
            'text_length': len(text),
            'word_count': word_count,
            'wpm': wpm,
            'iki_mean': float(np.mean(ikis)) if ikis else 0,
            'iki_std': float(np.std(ikis)) if ikis else 0,
            'iki_min': float(np.min(ikis)) if ikis else 0,
            'iki_max': float(np.max(ikis)) if ikis else 0,
            'digraph_count': len(self.digraph_times),
            'session_count': len(self.sessions),
            'recording_duration': duration
        }

    def get_common_errors(self) -> Dict[str, int]:
        """
        Analyze common error patterns.

        Returns:
            Dict of error type -> count
        """
        errors = {
            'backspace_immediate': 0,  # Quick backspace after typo
            'backspace_delayed': 0,    # Delayed correction
            'repeated_key': 0,         # Double key press
            'adjacent_key': 0          # Adjacent key on QWERTY
        }

        events = self.get_events()
        press_events = [e for e in events if e.event_type == 'press']

        # QWERTY adjacency map
        adjacent = {
            'q': 'wa', 'w': 'qeas', 'e': 'wrsд', 'r': 'edft',
            't': 'rfgy', 'y': 'tghu', 'u': 'yhji', 'i': 'ujko',
            'o': 'iklp', 'p': 'ol',
            'a': 'qwsz', 's': 'awedxz', 'd': 'serfcx', 'f': 'drtgvc',
            'g': 'ftyhbv', 'h': 'gyujnb', 'j': 'huikmn', 'k': 'jiolm',
            'l': 'kop',
            'z': 'asx', 'x': 'zsdc', 'c': 'xdfv', 'v': 'cfgb',
            'b': 'vghn', 'n': 'bhjm', 'm': 'njk'
        }

        for i, event in enumerate(press_events):
            if event.key == 'backspace':
                # Check timing
                if event.inter_key_interval and event.inter_key_interval < 300:
                    errors['backspace_immediate'] += 1
                else:
                    errors['backspace_delayed'] += 1

            elif i > 0:
                prev = press_events[i-1]

                # Repeated key
                if event.key == prev.key and event.inter_key_interval and event.inter_key_interval < 100:
                    errors['repeated_key'] += 1

                # Adjacent key error (followed by backspace)
                if i < len(press_events) - 1:
                    next_event = press_events[i+1]
                    if next_event.key == 'backspace':
                        if prev.key in adjacent and event.key in adjacent.get(prev.key, ''):
                            errors['adjacent_key'] += 1

        return errors

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

        logger.info(f"Saved {len(self.events)} keyboard events to {path}")

    def save_digraphs_to_file(self, path: str) -> None:
        """Save digraph timing data to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        stats = self.get_digraph_stats()

        with open(path, 'w') as f:
            json.dump(stats, f, indent=2)

    @staticmethod
    def load_from_file(path: str) -> List[KeyEvent]:
        """
        Load events from JSONL file.

        Args:
            path: Input file path

        Returns:
            List of KeyEvent objects
        """
        events = []
        with open(path) as f:
            for line in f:
                data = json.loads(line)
                events.append(KeyEvent(**data))
        return events
