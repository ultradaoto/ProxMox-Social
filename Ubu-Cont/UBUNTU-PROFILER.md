# UBUNTU-PROFILER.md - Personal Behavioral Biometrics System

## Overview

This document describes a **Personal Profiler System** that captures YOUR unique computer usage patterns and replays them when the AI controls the Windows VM. The goal: make AI-generated input **indistinguishable from your personal behavior**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROFILER ARCHITECTURE                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 1: RECORDING MODE                           │   │
│  │                                                                       │   │
│  │   YOU (Human) ───▶ Windows VM ───▶ Ubuntu Records Everything         │   │
│  │                                                                       │   │
│  │   Captures: Mouse trajectories, click timing, typing rhythm,         │   │
│  │             scroll patterns, think time, error corrections           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 2: PROFILE GENERATION                       │   │
│  │                                                                       │   │
│  │   Raw Data ───▶ Statistical Analysis ───▶ Personal Profile YAML      │   │
│  │                                                                       │   │
│  │   Outputs: Fitts coefficients, typing WPM distribution,              │   │
│  │            movement signatures, reaction time histogram              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                   │                                         │
│                                   ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    PHASE 3: REPLAY MODE                              │   │
│  │                                                                       │   │
│  │   AI Decision ───▶ Profile-Adjusted Input ───▶ Windows VM            │   │
│  │                                                                       │   │
│  │   AI uses YOUR movement patterns, YOUR typing speed,                 │   │
│  │   YOUR hesitation patterns, YOUR error correction style              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## What Gets Captured

### Mouse Behavior Metrics

| Metric | Description | Why It Matters |
|--------|-------------|----------------|
| **Trajectory Shape** | Bezier control points for each movement | Your arm creates unique curves |
| **Velocity Profile** | Speed at each point in movement | Acceleration patterns are personal |
| **Fitts's Law Coefficients** | Your personal a and b values | Target difficulty timing |
| **Overshoot Rate** | How often you overshoot targets | Muscle memory signature |
| **Correction Pattern** | How you correct overshoots | Direction, speed of correction |
| **Jitter Amplitude** | Natural hand tremor level | Varies person to person |
| **Click Duration** | Time between press and release | Personal click "weight" |
| **Double-Click Interval** | Time between clicks | Muscle memory timing |
| **Scroll Acceleration** | How you scroll (fast/slow, chunky/smooth) | Reading pattern |
| **Idle Drift** | Tiny movements while thinking | Subconscious micro-movements |

### Keyboard Behavior Metrics

| Metric | Description | Why It Matters |
|--------|-------------|----------------|
| **Inter-Key Interval (IKI)** | Time between keystrokes | Typing rhythm signature |
| **Key Hold Duration** | How long each key is pressed | Typing "weight" |
| **Digraph Timing** | Time for specific letter pairs | "th", "er", "ing" patterns |
| **Error Rate** | How often you make typos | Natural error frequency |
| **Error Types** | Adjacent key, transposition, etc. | Which mistakes you make |
| **Correction Delay** | Time before backspacing | How fast you notice errors |
| **Burst Patterns** | Fast typing for common words | "the", "and", etc. |
| **Pause Patterns** | Thinking pauses mid-sentence | Cognitive load indicators |
| **Shift Key Usage** | Hold vs tap for capitals | Technique variation |
| **Special Key Timing** | Enter, Tab, punctuation speed | Context-specific speed |

### Interaction Pattern Metrics

| Metric | Description | Why It Matters |
|--------|-------------|----------------|
| **Think Time** | Pause before actions | Decision-making speed |
| **Read Time** | Time spent viewing content | Reading speed |
| **Scan Pattern** | Eye-tracking proxy from mouse | How you scan pages |
| **Action Sequences** | Common action patterns | Click-type-click rhythms |
| **Recovery Patterns** | How you handle unexpected events | Error recovery style |

---

## File Structure

```
ubu-cont/
├── src/
│   └── profiler/
│       ├── __init__.py
│       ├── recorder.py           # Main recording orchestrator
│       ├── mouse_recorder.py     # Mouse movement capture
│       ├── keyboard_recorder.py  # Keystroke capture
│       ├── screen_recorder.py    # Screen state during recording
│       ├── session_manager.py    # Recording session management
│       ├── analyzer.py           # Statistical analysis of recordings
│       ├── profile_generator.py  # Generate personal profile YAML
│       ├── profile_applier.py    # Apply profile to AI output
│       ├── replay_engine.py      # Replay recordings for testing
│       ├── calibration.py        # Calibration exercises
│       └── visualizer.py         # Visualize your patterns
│
├── profiles/
│   ├── default.yaml              # Default (generic human) profile
│   ├── sterling.yaml             # YOUR personal profile
│   └── calibration/
│       ├── mouse_calibration.json
│       ├── typing_calibration.json
│       └── interaction_calibration.json
│
├── recordings/
│   ├── sessions/
│   │   ├── 2025-01-15_session_001/
│   │   │   ├── mouse_events.jsonl
│   │   │   ├── keyboard_events.jsonl
│   │   │   ├── screen_captures/
│   │   │   └── metadata.json
│   │   └── ...
│   └── calibration/
│       ├── fitts_law_test.jsonl
│       ├── typing_test.jsonl
│       └── scroll_test.jsonl
│
└── config/
    └── profiler_config.yaml
```

---

## Implementation Plan

### TASK 1: VNC Passthrough Mode

**Goal**: Let you control Windows VM through Ubuntu's VNC viewer while recording.

```python
# src/profiler/vnc_passthrough.py

class VNCPassthrough:
    """
    Bidirectional VNC that:
    1. Displays Windows VM screen to you
    2. Captures your input before forwarding
    3. Records everything for analysis
    """
    
    def __init__(self, config):
        self.vnc_capture = VNCCapturer(config.vnc)
        self.mouse_recorder = MouseRecorder()
        self.keyboard_recorder = KeyboardRecorder()
        self.display = LocalDisplay()  # Shows VNC to you
        self.hid_sender = HIDSender(config.host)  # Sends to Windows
        
    def start_passthrough(self):
        """Start passthrough mode - you control Windows, we record."""
        # Start VNC capture
        self.vnc_capture.connect()
        self.vnc_capture.start_capture()
        
        # Start local display
        self.display.start()
        
        # Hook local input
        self.mouse_recorder.start_recording()
        self.keyboard_recorder.start_recording()
        
        # Main loop
        while self.running:
            # Get latest frame
            frame = self.vnc_capture.capture_frame()
            self.display.show(frame)
            
            # Get your input (recorded automatically)
            mouse_events = self.mouse_recorder.get_events()
            keyboard_events = self.keyboard_recorder.get_events()
            
            # Forward to Windows VM
            for event in mouse_events:
                self.hid_sender.send_mouse(event)
            for event in keyboard_events:
                self.hid_sender.send_keyboard(event)
```

**Dependencies**:
- `pygame` or `tkinter` for local display
- `pynput` for local input capture
- Existing VNC capturer and HID sender

---

### TASK 2: Mouse Movement Recorder

**Goal**: Capture every mouse movement with microsecond precision.

```python
# src/profiler/mouse_recorder.py

from dataclasses import dataclass
from typing import List, Tuple, Optional
import time
import json
from pynput import mouse
import numpy as np

@dataclass
class MouseEvent:
    """Single mouse event with all relevant data."""
    timestamp: float          # Unix timestamp (microsecond precision)
    event_type: str           # 'move', 'click', 'scroll'
    x: int                    # Screen X coordinate
    y: int                    # Screen Y coordinate
    dx: Optional[int] = None  # Delta X (for relative)
    dy: Optional[int] = None  # Delta Y (for relative)
    button: Optional[str] = None  # 'left', 'right', 'middle'
    pressed: Optional[bool] = None  # True=down, False=up
    scroll_dx: Optional[int] = None  # Horizontal scroll
    scroll_dy: Optional[int] = None  # Vertical scroll

class MouseRecorder:
    """Records mouse movements with high precision."""
    
    def __init__(self, sample_rate_hz: int = 1000):
        self.sample_rate = sample_rate_hz
        self.events: List[MouseEvent] = []
        self.recording = False
        self.listener = None
        
        # Movement analysis buffers
        self.movement_buffer: List[Tuple[float, int, int]] = []
        self.last_position = (0, 0)
        self.last_time = 0
        
    def start_recording(self):
        """Start recording mouse events."""
        self.events = []
        self.recording = True
        
        self.listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll
        )
        self.listener.start()
        
    def stop_recording(self) -> List[MouseEvent]:
        """Stop recording and return events."""
        self.recording = False
        if self.listener:
            self.listener.stop()
        return self.events
    
    def _on_move(self, x: int, y: int):
        """Handle mouse movement."""
        if not self.recording:
            return
            
        now = time.time()
        
        # Calculate delta from last position
        dx = x - self.last_position[0]
        dy = y - self.last_position[1]
        
        event = MouseEvent(
            timestamp=now,
            event_type='move',
            x=x, y=y,
            dx=dx, dy=dy
        )
        self.events.append(event)
        
        # Update tracking
        self.last_position = (x, y)
        self.last_time = now
        
    def _on_click(self, x: int, y: int, button, pressed: bool):
        """Handle mouse click."""
        if not self.recording:
            return
            
        event = MouseEvent(
            timestamp=time.time(),
            event_type='click',
            x=x, y=y,
            button=button.name,
            pressed=pressed
        )
        self.events.append(event)
        
    def _on_scroll(self, x: int, y: int, dx: int, dy: int):
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
        self.events.append(event)
    
    def save_to_file(self, path: str):
        """Save events to JSONL file."""
        with open(path, 'w') as f:
            for event in self.events:
                f.write(json.dumps(event.__dict__) + '\n')
```

---

### TASK 3: Keyboard Recorder

**Goal**: Capture keystroke timing with digraph analysis.

```python
# src/profiler/keyboard_recorder.py

from dataclasses import dataclass
from typing import List, Dict, Optional
import time
import json
from pynput import keyboard
from collections import defaultdict

@dataclass
class KeyEvent:
    """Single keyboard event."""
    timestamp: float
    event_type: str  # 'press', 'release'
    key: str         # Key name or character
    key_code: Optional[int] = None
    modifiers: List[str] = None  # ['shift', 'ctrl', 'alt']

class KeyboardRecorder:
    """Records keyboard events with timing analysis."""
    
    def __init__(self):
        self.events: List[KeyEvent] = []
        self.recording = False
        self.listener = None
        
        # Timing analysis
        self.key_press_times: Dict[str, float] = {}  # Track press time per key
        self.last_key_time = 0
        self.current_modifiers: set = set()
        
        # Digraph tracking
        self.last_key = None
        self.digraph_times: Dict[str, List[float]] = defaultdict(list)
        
    def start_recording(self):
        """Start recording keyboard events."""
        self.events = []
        self.recording = True
        
        self.listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release
        )
        self.listener.start()
        
    def stop_recording(self) -> List[KeyEvent]:
        """Stop recording and return events."""
        self.recording = False
        if self.listener:
            self.listener.stop()
        return self.events
    
    def _key_to_string(self, key) -> str:
        """Convert pynput key to string."""
        try:
            return key.char
        except AttributeError:
            return str(key).replace('Key.', '')
    
    def _on_press(self, key):
        """Handle key press."""
        if not self.recording:
            return
            
        now = time.time()
        key_str = self._key_to_string(key)
        
        # Track modifiers
        if key_str in ('shift', 'shift_r', 'ctrl', 'ctrl_r', 'alt', 'alt_r'):
            self.current_modifiers.add(key_str.replace('_r', ''))
        
        # Record digraph timing
        if self.last_key and now - self.last_key_time < 2.0:
            digraph = f"{self.last_key}_{key_str}"
            self.digraph_times[digraph].append(now - self.last_key_time)
        
        event = KeyEvent(
            timestamp=now,
            event_type='press',
            key=key_str,
            modifiers=list(self.current_modifiers)
        )
        self.events.append(event)
        
        # Track for hold duration
        self.key_press_times[key_str] = now
        self.last_key = key_str
        self.last_key_time = now
        
    def _on_release(self, key):
        """Handle key release."""
        if not self.recording:
            return
            
        now = time.time()
        key_str = self._key_to_string(key)
        
        # Track modifiers
        if key_str in ('shift', 'shift_r', 'ctrl', 'ctrl_r', 'alt', 'alt_r'):
            self.current_modifiers.discard(key_str.replace('_r', ''))
        
        # Calculate hold duration
        hold_duration = None
        if key_str in self.key_press_times:
            hold_duration = now - self.key_press_times[key_str]
            del self.key_press_times[key_str]
        
        event = KeyEvent(
            timestamp=now,
            event_type='release',
            key=key_str,
            modifiers=list(self.current_modifiers)
        )
        self.events.append(event)
    
    def get_digraph_stats(self) -> Dict[str, Dict]:
        """Get statistics for each digraph."""
        stats = {}
        for digraph, times in self.digraph_times.items():
            if len(times) >= 3:  # Need enough samples
                stats[digraph] = {
                    'mean': np.mean(times),
                    'std': np.std(times),
                    'min': np.min(times),
                    'max': np.max(times),
                    'count': len(times)
                }
        return stats
    
    def save_to_file(self, path: str):
        """Save events to JSONL file."""
        with open(path, 'w') as f:
            for event in self.events:
                f.write(json.dumps(event.__dict__) + '\n')
```

---

### TASK 4: Profile Analyzer

**Goal**: Analyze recordings and extract your personal biometric signature.

```python
# src/profiler/analyzer.py

import numpy as np
from scipy import stats
from scipy.optimize import curve_fit
from typing import List, Dict, Tuple
from dataclasses import dataclass
import json

@dataclass
class MouseProfile:
    """Your personal mouse movement profile."""
    # Fitts's Law coefficients (T = a + b * log2(D/W + 1))
    fitts_a: float  # Intercept (base reaction time in ms)
    fitts_b: float  # Slope (time per bit of difficulty)
    fitts_r2: float  # Goodness of fit
    
    # Movement characteristics
    avg_velocity: float  # Average movement speed (pixels/sec)
    velocity_std: float  # Velocity variation
    acceleration_profile: List[float]  # Normalized acceleration curve
    
    # Trajectory shape
    curvature_mean: float  # Average trajectory curvature
    curvature_std: float   # Curvature variation
    overshoot_rate: float  # Proportion of movements with overshoot
    overshoot_distance_mean: float  # Average overshoot in pixels
    
    # Jitter characteristics
    jitter_amplitude: float  # RMS of micro-movements (pixels)
    jitter_frequency: float  # Dominant jitter frequency (Hz)
    
    # Click characteristics
    click_duration_mean: float  # Average click duration (ms)
    click_duration_std: float
    double_click_interval_mean: float
    double_click_interval_std: float

@dataclass  
class KeyboardProfile:
    """Your personal typing profile."""
    # Overall speed
    wpm_mean: float
    wpm_std: float
    
    # Inter-key intervals
    iki_mean: float  # Mean inter-key interval (ms)
    iki_std: float
    iki_distribution: str  # 'normal', 'lognormal', etc.
    
    # Key hold durations
    hold_duration_mean: float
    hold_duration_std: float
    
    # Digraph-specific timing (top 50 most common)
    digraph_timing: Dict[str, Tuple[float, float]]  # digraph -> (mean, std)
    
    # Error characteristics
    error_rate: float  # Errors per 100 keystrokes
    common_errors: Dict[str, float]  # Error type -> frequency
    correction_delay_mean: float  # Time before backspace (ms)
    
    # Pause patterns
    word_pause_mean: float  # Pause between words (ms)
    sentence_pause_mean: float  # Pause at sentence end (ms)
    think_pause_threshold: float  # What counts as "thinking" (ms)

class ProfileAnalyzer:
    """Analyzes recorded sessions to build your profile."""
    
    def __init__(self):
        pass
    
    def analyze_mouse_session(self, events: List[dict]) -> MouseProfile:
        """Analyze mouse events and extract profile."""
        
        # Extract movements (sequences between clicks)
        movements = self._extract_movements(events)
        
        # Fit Fitts's Law
        fitts_a, fitts_b, fitts_r2 = self._fit_fitts_law(movements)
        
        # Analyze velocity profile
        velocities = self._calculate_velocities(movements)
        avg_velocity = np.mean(velocities)
        velocity_std = np.std(velocities)
        
        # Analyze trajectory curvature
        curvatures = self._calculate_curvatures(movements)
        
        # Detect overshoots
        overshoot_rate, overshoot_distances = self._detect_overshoots(movements)
        
        # Analyze jitter (micro-movements while "stationary")
        jitter_amp, jitter_freq = self._analyze_jitter(events)
        
        # Analyze clicks
        click_durations = self._get_click_durations(events)
        double_click_intervals = self._get_double_click_intervals(events)
        
        return MouseProfile(
            fitts_a=fitts_a,
            fitts_b=fitts_b,
            fitts_r2=fitts_r2,
            avg_velocity=avg_velocity,
            velocity_std=velocity_std,
            acceleration_profile=self._get_acceleration_profile(movements),
            curvature_mean=np.mean(curvatures) if curvatures else 0,
            curvature_std=np.std(curvatures) if curvatures else 0,
            overshoot_rate=overshoot_rate,
            overshoot_distance_mean=np.mean(overshoot_distances) if overshoot_distances else 0,
            jitter_amplitude=jitter_amp,
            jitter_frequency=jitter_freq,
            click_duration_mean=np.mean(click_durations) if click_durations else 100,
            click_duration_std=np.std(click_durations) if click_durations else 20,
            double_click_interval_mean=np.mean(double_click_intervals) if double_click_intervals else 100,
            double_click_interval_std=np.std(double_click_intervals) if double_click_intervals else 20
        )
    
    def _fit_fitts_law(self, movements: List) -> Tuple[float, float, float]:
        """
        Fit Fitts's Law: T = a + b * log2(D/W + 1)
        
        Returns: (a, b, r_squared)
        """
        if len(movements) < 10:
            return 50, 150, 0  # Default values
        
        # Extract distance and time for each movement
        distances = []
        times = []
        target_widths = []
        
        for movement in movements:
            if movement.get('target_width'):
                d = movement['distance']
                w = movement['target_width']
                t = movement['duration'] * 1000  # Convert to ms
                
                distances.append(d)
                target_widths.append(w)
                times.append(t)
        
        if len(distances) < 5:
            return 50, 150, 0
        
        # Calculate index of difficulty
        distances = np.array(distances)
        target_widths = np.array(target_widths)
        times = np.array(times)
        
        # ID = log2(D/W + 1)
        id_values = np.log2(distances / target_widths + 1)
        
        # Linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(id_values, times)
        
        return intercept, slope, r_value ** 2
    
    def _calculate_velocities(self, movements: List) -> List[float]:
        """Calculate velocity for each movement."""
        velocities = []
        for movement in movements:
            if movement['duration'] > 0:
                velocity = movement['distance'] / movement['duration']
                velocities.append(velocity)
        return velocities
    
    def _calculate_curvatures(self, movements: List) -> List[float]:
        """Calculate trajectory curvature for each movement."""
        curvatures = []
        for movement in movements:
            points = movement.get('points', [])
            if len(points) >= 3:
                # Calculate curvature as path length / straight distance
                path_length = sum(
                    np.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
                    for p1, p2 in zip(points[:-1], points[1:])
                )
                straight_distance = movement['distance']
                if straight_distance > 0:
                    curvatures.append(path_length / straight_distance)
        return curvatures
    
    def _detect_overshoots(self, movements: List) -> Tuple[float, List[float]]:
        """Detect movements that overshoot and correct."""
        overshoots = 0
        overshoot_distances = []
        
        for movement in movements:
            points = movement.get('points', [])
            if len(points) >= 3 and movement.get('end_point'):
                end = movement['end_point']
                
                # Check if any point is beyond the target
                for point in points:
                    d_to_end = np.sqrt((point[0]-end[0])**2 + (point[1]-end[1])**2)
                    if d_to_end > movement['distance'] * 0.1:  # Moved past target
                        overshoots += 1
                        overshoot_distances.append(d_to_end)
                        break
        
        rate = overshoots / len(movements) if movements else 0
        return rate, overshoot_distances
    
    def _analyze_jitter(self, events: List) -> Tuple[float, float]:
        """Analyze micro-movements (jitter) during stationary periods."""
        # Find periods with minimal movement
        stationary_movements = []
        
        # Group events by time windows
        window_size = 0.5  # 500ms windows
        current_window = []
        
        for event in events:
            if event['event_type'] == 'move':
                current_window.append(event)
                
                if len(current_window) > 1:
                    time_diff = current_window[-1]['timestamp'] - current_window[0]['timestamp']
                    if time_diff >= window_size:
                        # Analyze this window
                        positions = [(e['x'], e['y']) for e in current_window]
                        
                        # Calculate RMS of movements
                        if len(positions) > 1:
                            center_x = np.mean([p[0] for p in positions])
                            center_y = np.mean([p[1] for p in positions])
                            
                            distances = [
                                np.sqrt((p[0]-center_x)**2 + (p[1]-center_y)**2)
                                for p in positions
                            ]
                            
                            rms = np.sqrt(np.mean(np.array(distances)**2))
                            
                            # If RMS is small, this is "stationary" jitter
                            if rms < 50:  # Less than 50 pixels total movement
                                stationary_movements.extend(distances)
                        
                        current_window = []
        
        if stationary_movements:
            jitter_amp = np.sqrt(np.mean(np.array(stationary_movements)**2))
            # Estimate frequency from number of movements per second
            jitter_freq = len(stationary_movements) / (len(events) * 0.001)  # Rough estimate
        else:
            jitter_amp = 3.0  # Default
            jitter_freq = 10.0
            
        return jitter_amp, jitter_freq
    
    def _extract_movements(self, events: List) -> List[dict]:
        """Extract complete movements (start to click/stop)."""
        movements = []
        current_movement = {'points': [], 'start_time': None}
        
        for event in events:
            if event['event_type'] == 'move':
                if current_movement['start_time'] is None:
                    current_movement['start_time'] = event['timestamp']
                current_movement['points'].append((event['x'], event['y']))
                
            elif event['event_type'] == 'click' and event.get('pressed'):
                # End of movement
                if current_movement['points']:
                    points = current_movement['points']
                    movement = {
                        'points': points,
                        'start_point': points[0],
                        'end_point': points[-1],
                        'distance': np.sqrt(
                            (points[-1][0] - points[0][0])**2 +
                            (points[-1][1] - points[0][1])**2
                        ),
                        'duration': event['timestamp'] - current_movement['start_time'],
                        'target_width': 20  # Estimate - could detect from screen
                    }
                    movements.append(movement)
                
                current_movement = {'points': [], 'start_time': None}
        
        return movements
    
    def _get_click_durations(self, events: List) -> List[float]:
        """Extract click durations (press to release)."""
        durations = []
        press_times = {}
        
        for event in events:
            if event['event_type'] == 'click':
                button = event.get('button', 'left')
                if event.get('pressed'):
                    press_times[button] = event['timestamp']
                else:
                    if button in press_times:
                        duration = (event['timestamp'] - press_times[button]) * 1000
                        durations.append(duration)
                        del press_times[button]
        
        return durations
    
    def _get_double_click_intervals(self, events: List) -> List[float]:
        """Extract intervals between double-clicks."""
        intervals = []
        last_click_time = None
        
        for event in events:
            if event['event_type'] == 'click' and event.get('pressed'):
                if last_click_time:
                    interval = (event['timestamp'] - last_click_time) * 1000
                    if interval < 500:  # Likely double-click
                        intervals.append(interval)
                last_click_time = event['timestamp']
        
        return intervals
    
    def _get_acceleration_profile(self, movements: List) -> List[float]:
        """Get normalized acceleration profile across movements."""
        # Bin acceleration into 10 segments
        profiles = []
        
        for movement in movements:
            points = movement.get('points', [])
            if len(points) >= 10:
                # Calculate velocity at each point
                velocities = []
                for i in range(1, len(points)):
                    dx = points[i][0] - points[i-1][0]
                    dy = points[i][1] - points[i-1][1]
                    velocities.append(np.sqrt(dx**2 + dy**2))
                
                # Normalize to 10 bins
                bins = np.array_split(velocities, 10)
                profile = [np.mean(b) for b in bins]
                
                # Normalize
                max_v = max(profile) if max(profile) > 0 else 1
                profile = [v / max_v for v in profile]
                
                profiles.append(profile)
        
        if profiles:
            # Average across all movements
            return list(np.mean(profiles, axis=0))
        else:
            # Default bell curve
            return [0.2, 0.5, 0.8, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1]
```

---

### TASK 5: Profile Generator

**Goal**: Generate final YAML profile from analysis.

```python
# src/profiler/profile_generator.py

import yaml
from datetime import datetime
from typing import List
from .analyzer import ProfileAnalyzer, MouseProfile, KeyboardProfile

class ProfileGenerator:
    """Generates personal profile YAML from analysis."""
    
    def __init__(self, analyzer: ProfileAnalyzer):
        self.analyzer = analyzer
        
    def generate_profile(
        self,
        mouse_sessions: List[str],  # Paths to mouse recording files
        keyboard_sessions: List[str],  # Paths to keyboard recording files
        output_path: str
    ) -> str:
        """
        Generate complete personal profile.
        
        Args:
            mouse_sessions: List of paths to mouse recording JSONL files
            keyboard_sessions: List of paths to keyboard recording JSONL files
            output_path: Where to save the profile YAML
            
        Returns:
            Path to generated profile
        """
        # Load and combine all sessions
        all_mouse_events = []
        all_keyboard_events = []
        
        for path in mouse_sessions:
            events = self._load_jsonl(path)
            all_mouse_events.extend(events)
            
        for path in keyboard_sessions:
            events = self._load_jsonl(path)
            all_keyboard_events.extend(events)
        
        # Analyze
        mouse_profile = self.analyzer.analyze_mouse_session(all_mouse_events)
        keyboard_profile = self.analyzer.analyze_keyboard_session(all_keyboard_events)
        
        # Build profile dict
        profile = {
            'metadata': {
                'generated_at': datetime.now().isoformat(),
                'mouse_samples': len(all_mouse_events),
                'keyboard_samples': len(all_keyboard_events),
                'version': '1.0'
            },
            
            'mouse': {
                'fitts_law': {
                    'a': round(mouse_profile.fitts_a, 2),
                    'b': round(mouse_profile.fitts_b, 2),
                    'r_squared': round(mouse_profile.fitts_r2, 3)
                },
                'velocity': {
                    'mean_pixels_per_sec': round(mouse_profile.avg_velocity, 1),
                    'std': round(mouse_profile.velocity_std, 1)
                },
                'trajectory': {
                    'curvature_mean': round(mouse_profile.curvature_mean, 3),
                    'curvature_std': round(mouse_profile.curvature_std, 3),
                    'overshoot_rate': round(mouse_profile.overshoot_rate, 3),
                    'overshoot_distance_mean': round(mouse_profile.overshoot_distance_mean, 1)
                },
                'jitter': {
                    'amplitude_pixels': round(mouse_profile.jitter_amplitude, 2),
                    'frequency_hz': round(mouse_profile.jitter_frequency, 1)
                },
                'clicks': {
                    'duration_mean_ms': round(mouse_profile.click_duration_mean, 1),
                    'duration_std_ms': round(mouse_profile.click_duration_std, 1),
                    'double_click_interval_mean_ms': round(mouse_profile.double_click_interval_mean, 1),
                    'double_click_interval_std_ms': round(mouse_profile.double_click_interval_std, 1)
                },
                'acceleration_profile': [round(v, 3) for v in mouse_profile.acceleration_profile]
            },
            
            'keyboard': {
                'speed': {
                    'wpm_mean': round(keyboard_profile.wpm_mean, 1),
                    'wpm_std': round(keyboard_profile.wpm_std, 1)
                },
                'timing': {
                    'inter_key_interval_mean_ms': round(keyboard_profile.iki_mean, 1),
                    'inter_key_interval_std_ms': round(keyboard_profile.iki_std, 1),
                    'hold_duration_mean_ms': round(keyboard_profile.hold_duration_mean, 1),
                    'hold_duration_std_ms': round(keyboard_profile.hold_duration_std, 1)
                },
                'errors': {
                    'rate_per_100_keys': round(keyboard_profile.error_rate, 2),
                    'correction_delay_ms': round(keyboard_profile.correction_delay_mean, 1)
                },
                'pauses': {
                    'word_pause_mean_ms': round(keyboard_profile.word_pause_mean, 1),
                    'sentence_pause_mean_ms': round(keyboard_profile.sentence_pause_mean, 1),
                    'think_pause_threshold_ms': round(keyboard_profile.think_pause_threshold, 1)
                },
                'digraph_timing': {
                    k: {'mean_ms': round(v[0], 1), 'std_ms': round(v[1], 1)}
                    for k, v in list(keyboard_profile.digraph_timing.items())[:50]
                }
            },
            
            'interaction': {
                'think_time': {
                    'min_ms': 300,
                    'max_ms': 2000,
                    'distribution': 'lognormal'
                },
                'action_sequences': {
                    # Common patterns detected
                }
            }
        }
        
        # Save
        with open(output_path, 'w') as f:
            yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
        
        return output_path
    
    def _load_jsonl(self, path: str) -> List[dict]:
        """Load events from JSONL file."""
        events = []
        with open(path) as f:
            for line in f:
                events.append(json.loads(line))
        return events
```

---

### TASK 6: OpenRouter Integration

**Goal**: Connect to OpenRouter for Qwen Coder and Qwen Vision models.

```python
# src/ai/openrouter_client.py

import httpx
import base64
import json
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

@dataclass
class OpenRouterConfig:
    """OpenRouter configuration."""
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    coder_model: str = "qwen/qwen-2.5-coder-32b-instruct"
    vision_model: str = "qwen/qwen-2-vl-72b-instruct"
    timeout: int = 120

class OpenRouterClient:
    """
    Client for OpenRouter API.
    
    Provides access to:
    - Qwen 2.5 Coder: For decision making and code generation
    - Qwen 2 VL: For vision/screen understanding
    """
    
    def __init__(self, config: OpenRouterConfig):
        self.config = config
        self.client = httpx.Client(
            base_url=config.base_url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "HTTP-Referer": "https://github.com/your-project",
                "X-Title": "AI Computer Control"
            },
            timeout=config.timeout
        )
        
    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> str:
        """
        Send chat completion request.
        
        Args:
            messages: List of message dicts
            model: Model to use (defaults to coder model)
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            
        Returns:
            Assistant response
        """
        model = model or self.config.coder_model
        
        response = self.client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
        )
        response.raise_for_status()
        
        return response.json()["choices"][0]["message"]["content"]
    
    def analyze_screen(
        self,
        image_path: str,
        query: str,
        context: Optional[str] = None
    ) -> str:
        """
        Analyze screenshot using vision model.
        
        Args:
            image_path: Path to screenshot
            query: What to look for / analyze
            context: Optional context about current task
            
        Returns:
            Analysis result
        """
        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        
        # Determine image type
        if image_path.endswith('.png'):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"
        
        messages = [
            {
                "role": "system",
                "content": """You are an expert at analyzing computer screenshots.
You identify UI elements, buttons, text fields, and describe what's on screen.
When asked to find elements, provide their approximate pixel coordinates.
Be precise and concise."""
            }
        ]
        
        if context:
            messages.append({
                "role": "user",
                "content": f"Context: {context}"
            })
        
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}"
                    }
                },
                {
                    "type": "text",
                    "text": query
                }
            ]
        })
        
        return self.chat(messages, model=self.config.vision_model)
    
    def decide_next_action(
        self,
        screen_analysis: str,
        task_description: str,
        action_history: List[Dict],
        available_actions: List[str]
    ) -> Dict[str, Any]:
        """
        Decide what action to take next.
        
        Args:
            screen_analysis: Description of current screen
            task_description: What we're trying to accomplish
            action_history: Previous actions taken
            available_actions: What actions are possible
            
        Returns:
            Dict with action type and parameters
        """
        prompt = f"""You are controlling a computer to complete a task.

TASK: {task_description}

CURRENT SCREEN STATE:
{screen_analysis}

PREVIOUS ACTIONS:
{json.dumps(action_history[-5:], indent=2) if action_history else "None"}

AVAILABLE ACTIONS:
- click(x, y): Click at coordinates
- double_click(x, y): Double-click at coordinates
- right_click(x, y): Right-click at coordinates
- type(text): Type text
- scroll(direction, amount): Scroll up/down
- wait(seconds): Wait for page to load
- done(): Task is complete

What is the next best action? Respond with ONLY a JSON object:
{{"action": "action_name", "params": {{...}}}}"""

        response = self.chat([
            {"role": "system", "content": "You are a precise computer control agent. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ])
        
        # Parse JSON response
        try:
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except:
            pass
        
        return {"action": "wait", "params": {"seconds": 1}}
    
    def find_element(
        self,
        image_path: str,
        element_description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a specific element on screen.
        
        Args:
            image_path: Screenshot path
            element_description: What to find (e.g., "login button", "search box")
            
        Returns:
            Dict with element info and coordinates, or None
        """
        query = f"""Find the "{element_description}" on this screen.

If found, respond with JSON:
{{"found": true, "x": <center_x>, "y": <center_y>, "width": <width>, "height": <height>, "confidence": <0-1>}}

If not found:
{{"found": false, "reason": "explanation"}}"""

        response = self.analyze_screen(image_path, query)
        
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except:
            pass
        
        return None


# Example config
OPENROUTER_CONFIG = OpenRouterConfig(
    api_key="YOUR_OPENROUTER_API_KEY",
    coder_model="qwen/qwen-2.5-coder-32b-instruct",
    vision_model="qwen/qwen-2-vl-72b-instruct"
)
```

---

### TASK 7: Recording Session Manager

**Goal**: Manage recording sessions with UI.

```python
# src/profiler/session_manager.py

import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict

@dataclass
class SessionMetadata:
    """Recording session metadata."""
    session_id: str
    start_time: str
    end_time: Optional[str]
    duration_seconds: float
    mouse_events: int
    keyboard_events: int
    screenshots: int
    task_description: str
    notes: str

class SessionManager:
    """Manages recording sessions."""
    
    def __init__(self, base_dir: str = "recordings/sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_session: Optional[str] = None
        self.session_start_time: Optional[float] = None
        
    def start_session(self, task_description: str = "") -> str:
        """Start a new recording session."""
        # Generate session ID
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_id = f"session_{timestamp}"
        
        # Create session directory
        session_dir = self.base_dir / session_id
        session_dir.mkdir()
        (session_dir / "screen_captures").mkdir()
        
        # Initialize metadata
        metadata = SessionMetadata(
            session_id=session_id,
            start_time=datetime.now().isoformat(),
            end_time=None,
            duration_seconds=0,
            mouse_events=0,
            keyboard_events=0,
            screenshots=0,
            task_description=task_description,
            notes=""
        )
        
        self._save_metadata(session_id, metadata)
        
        self.current_session = session_id
        self.session_start_time = time.time()
        
        return session_id
    
    def end_session(self) -> Optional[SessionMetadata]:
        """End current recording session."""
        if not self.current_session:
            return None
            
        # Update metadata
        metadata = self._load_metadata(self.current_session)
        metadata.end_time = datetime.now().isoformat()
        metadata.duration_seconds = time.time() - self.session_start_time
        
        # Count events
        session_dir = self.base_dir / self.current_session
        mouse_file = session_dir / "mouse_events.jsonl"
        keyboard_file = session_dir / "keyboard_events.jsonl"
        
        if mouse_file.exists():
            with open(mouse_file) as f:
                metadata.mouse_events = sum(1 for _ in f)
        
        if keyboard_file.exists():
            with open(keyboard_file) as f:
                metadata.keyboard_events = sum(1 for _ in f)
        
        screenshots_dir = session_dir / "screen_captures"
        metadata.screenshots = len(list(screenshots_dir.glob("*.png")))
        
        self._save_metadata(self.current_session, metadata)
        
        result = metadata
        self.current_session = None
        self.session_start_time = None
        
        return result
    
    def get_session_dir(self) -> Optional[Path]:
        """Get current session directory."""
        if self.current_session:
            return self.base_dir / self.current_session
        return None
    
    def list_sessions(self) -> List[SessionMetadata]:
        """List all recording sessions."""
        sessions = []
        for session_dir in sorted(self.base_dir.iterdir()):
            if session_dir.is_dir():
                metadata = self._load_metadata(session_dir.name)
                if metadata:
                    sessions.append(metadata)
        return sessions
    
    def _save_metadata(self, session_id: str, metadata: SessionMetadata):
        """Save session metadata."""
        path = self.base_dir / session_id / "metadata.json"
        with open(path, 'w') as f:
            json.dump(asdict(metadata), f, indent=2)
    
    def _load_metadata(self, session_id: str) -> Optional[SessionMetadata]:
        """Load session metadata."""
        path = self.base_dir / session_id / "metadata.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                return SessionMetadata(**data)
        return None
```

---

### TASK 8: Calibration Exercises

**Goal**: Guided exercises to capture your specific patterns.

```python
# src/profiler/calibration.py

import time
import random
from typing import List, Tuple, Callable
from dataclasses import dataclass

@dataclass
class CalibrationTarget:
    """A target for Fitts's Law calibration."""
    x: int
    y: int
    width: int
    height: int
    
class CalibrationExercises:
    """
    Guided exercises to capture your behavioral patterns.
    
    These provide controlled conditions for measuring:
    - Fitts's Law coefficients
    - Typing speed and rhythm
    - Scroll behavior
    - Think time
    """
    
    def __init__(self, display, mouse_recorder, keyboard_recorder):
        self.display = display
        self.mouse_recorder = mouse_recorder
        self.keyboard_recorder = keyboard_recorder
        
    def run_fitts_law_test(
        self,
        num_trials: int = 50,
        target_sizes: List[int] = [10, 20, 40, 80],
        distances: List[int] = [100, 200, 400, 800]
    ) -> List[dict]:
        """
        Run Fitts's Law calibration.
        
        Displays targets at various sizes and distances.
        You click each target as quickly and accurately as possible.
        """
        results = []
        
        self.display.show_instructions("""
FITTS'S LAW CALIBRATION

You will see targets appear on screen.
Click each target as quickly and accurately as you can.
This measures your personal movement characteristics.

Press SPACE to begin.
        """)
        
        self.display.wait_for_key('space')
        
        for trial in range(num_trials):
            # Random target size and position
            size = random.choice(target_sizes)
            distance = random.choice(distances)
            angle = random.uniform(0, 2 * 3.14159)
            
            # Calculate target position
            center_x, center_y = 960, 540  # Screen center
            target_x = int(center_x + distance * math.cos(angle))
            target_y = int(center_y + distance * math.sin(angle))
            
            # Show starting point
            self.display.show_target(center_x, center_y, 20, color='green')
            self.display.show_message(f"Click the GREEN dot to start (trial {trial+1}/{num_trials})")
            
            # Wait for click on start
            start_click = self.display.wait_for_click()
            
            # Show target
            start_time = time.time()
            self.display.clear()
            self.display.show_target(target_x, target_y, size, color='red')
            
            # Start recording
            self.mouse_recorder.start_recording()
            
            # Wait for click on target
            end_click = self.display.wait_for_click()
            end_time = time.time()
            
            # Stop recording
            events = self.mouse_recorder.stop_recording()
            
            # Check accuracy
            click_distance = math.sqrt(
                (end_click[0] - target_x)**2 + 
                (end_click[1] - target_y)**2
            )
            hit = click_distance <= size / 2
            
            result = {
                'trial': trial,
                'target_size': size,
                'target_distance': distance,
                'movement_time': end_time - start_time,
                'hit': hit,
                'click_distance': click_distance,
                'events': events
            }
            results.append(result)
            
            # Brief pause
            time.sleep(0.3)
        
        self.display.show_message("Calibration complete! Analyzing...")
        return results
    
    def run_typing_test(
        self,
        passages: List[str] = None
    ) -> List[dict]:
        """
        Run typing calibration.
        
        You type displayed text passages.
        This captures your typing rhythm and patterns.
        """
        if passages is None:
            passages = [
                "The quick brown fox jumps over the lazy dog.",
                "Pack my box with five dozen liquor jugs.",
                "How vexingly quick daft zebras jump!",
                "The five boxing wizards jump quickly.",
                "Sphinx of black quartz, judge my vow.",
                # Add more realistic passages
                "I need to send an email to the team about tomorrow's meeting.",
                "Please review the attached document and let me know your thoughts.",
                "Thanks for your help with the project last week.",
            ]
        
        results = []
        
        self.display.show_instructions("""
TYPING CALIBRATION

You will see text passages to type.
Type each passage exactly as shown.
Type naturally - don't try to be fast or slow.

Press SPACE to begin.
        """)
        
        self.display.wait_for_key('space')
        
        for i, passage in enumerate(passages):
            self.display.show_typing_prompt(passage, f"Passage {i+1}/{len(passages)}")
            
            # Start recording
            self.keyboard_recorder.start_recording()
            
            # Wait for typing to complete
            typed_text = self.display.wait_for_typing(len(passage))
            
            # Stop recording
            events = self.keyboard_recorder.stop_recording()
            
            # Calculate metrics
            total_time = events[-1]['timestamp'] - events[0]['timestamp'] if events else 0
            words = len(passage.split())
            wpm = (words / total_time) * 60 if total_time > 0 else 0
            
            # Count errors
            errors = sum(1 for e in events if e['key'] == 'backspace')
            
            result = {
                'passage': passage,
                'typed': typed_text,
                'wpm': wpm,
                'errors': errors,
                'total_time': total_time,
                'events': events
            }
            results.append(result)
            
            # Brief pause
            time.sleep(0.5)
        
        self.display.show_message("Typing calibration complete!")
        return results
    
    def run_scroll_test(self) -> List[dict]:
        """Run scroll behavior calibration."""
        # Show a long scrollable document
        # Record scroll patterns
        pass
    
    def run_full_calibration(self) -> dict:
        """Run complete calibration suite."""
        results = {
            'fitts_law': self.run_fitts_law_test(),
            'typing': self.run_typing_test(),
            'scroll': self.run_scroll_test(),
            'timestamp': time.time()
        }
        return results
```

---

### TASK 9: Replay Engine

**Goal**: Replay your recorded sessions to verify profile accuracy.

```python
# src/profiler/replay_engine.py

import time
import json
from typing import List, Dict, Optional
from pathlib import Path

class ReplayEngine:
    """
    Replays recorded sessions for verification.
    
    This lets you see the AI replicate your movements
    before using it against real detection systems.
    """
    
    def __init__(self, hid_sender, profile_applier):
        self.hid_sender = hid_sender
        self.profile_applier = profile_applier
        
    def replay_session(
        self,
        session_path: str,
        speed_multiplier: float = 1.0,
        apply_profile: bool = True
    ):
        """
        Replay a recorded session.
        
        Args:
            session_path: Path to session directory
            speed_multiplier: 1.0 = real time, 0.5 = half speed, etc.
            apply_profile: If True, applies profile adjustments
        """
        session_dir = Path(session_path)
        
        # Load events
        mouse_events = self._load_events(session_dir / "mouse_events.jsonl")
        keyboard_events = self._load_events(session_dir / "keyboard_events.jsonl")
        
        # Merge and sort by timestamp
        all_events = []
        for event in mouse_events:
            event['source'] = 'mouse'
            all_events.append(event)
        for event in keyboard_events:
            event['source'] = 'keyboard'
            all_events.append(event)
        
        all_events.sort(key=lambda e: e['timestamp'])
        
        if not all_events:
            return
        
        # Replay
        start_time = time.time()
        base_timestamp = all_events[0]['timestamp']
        
        for event in all_events:
            # Calculate when to send this event
            event_offset = (event['timestamp'] - base_timestamp) / speed_multiplier
            target_time = start_time + event_offset
            
            # Wait until it's time
            wait_time = target_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)
            
            # Apply profile adjustments if enabled
            if apply_profile:
                event = self.profile_applier.adjust_event(event)
            
            # Send event
            if event['source'] == 'mouse':
                self._send_mouse_event(event)
            else:
                self._send_keyboard_event(event)
    
    def _load_events(self, path: Path) -> List[dict]:
        """Load events from JSONL file."""
        events = []
        if path.exists():
            with open(path) as f:
                for line in f:
                    events.append(json.loads(line))
        return events
    
    def _send_mouse_event(self, event: dict):
        """Send mouse event through HID."""
        if event['event_type'] == 'move':
            self.hid_sender.send_mouse({
                'type': 'mouse_move',
                'x': event['x'],
                'y': event['y']
            })
        elif event['event_type'] == 'click':
            self.hid_sender.send_mouse({
                'type': 'mouse_button',
                'button': event.get('button', 'left'),
                'action': 'down' if event.get('pressed') else 'up'
            })
        elif event['event_type'] == 'scroll':
            self.hid_sender.send_mouse({
                'type': 'mouse_wheel',
                'delta': event.get('scroll_dy', 0)
            })
    
    def _send_keyboard_event(self, event: dict):
        """Send keyboard event through HID."""
        self.hid_sender.send_keyboard({
            'type': 'keyboard',
            'key': event['key'],
            'action': 'down' if event['event_type'] == 'press' else 'up'
        })


class ProfileTester:
    """
    Tests profile accuracy against recordings.
    
    Compares AI-generated input to your recorded input
    to measure how well the profile matches.
    """
    
    def __init__(self, profile, human_mouse, human_keyboard):
        self.profile = profile
        self.human_mouse = human_mouse
        self.human_keyboard = human_keyboard
        
    def test_movement_similarity(
        self,
        recorded_movement: List[dict],
        target: tuple
    ) -> dict:
        """
        Compare AI movement to recorded movement.
        
        Returns similarity metrics.
        """
        # Generate AI trajectory
        start = (recorded_movement[0]['x'], recorded_movement[0]['y'])
        ai_trajectory = self.human_mouse.plan_trajectory(start, target)
        
        # Compare
        recorded_points = [(e['x'], e['y']) for e in recorded_movement]
        ai_points = [(p.x, p.y) for p in ai_trajectory]
        
        # Calculate similarity metrics
        # ...
        
        return {
            'trajectory_similarity': 0.95,  # Example
            'timing_similarity': 0.92,
            'velocity_profile_similarity': 0.88
        }
```

---

## Usage Workflow

### Step 1: Initial Calibration (15-20 minutes)

```bash
cd ~/proxmox-computer-control/ubu-cont
source venv/bin/activate

# Run calibration exercises
python -m src.profiler.calibrate --user sterling

# This will:
# 1. Run Fitts's Law test (50 targets, ~5 min)
# 2. Run typing test (10 passages, ~5 min)
# 3. Run scroll test (~2 min)
# 4. Generate initial profile
```

### Step 2: Free-Form Recording Sessions (30+ minutes)

```bash
# Start passthrough mode - control Windows through Ubuntu
python -m src.profiler.passthrough --record

# This opens a window showing the Windows VM
# Use it normally - browse, click, type, scroll
# Everything is recorded

# When done:
Ctrl+Q to stop recording
```

### Step 3: Generate Personal Profile

```bash
# Analyze all recordings and generate profile
python -m src.profiler.generate_profile \
    --sessions recordings/sessions/* \
    --calibration recordings/calibration/* \
    --output profiles/sterling.yaml
```

### Step 4: Test Profile (Visual Verification)

```bash
# Replay a recording with your profile applied
python -m src.profiler.replay \
    --session recordings/sessions/2025-01-15_session_001 \
    --profile profiles/sterling.yaml \
    --visual

# Watch the AI replay your actions
# It should look natural and match your style
```

### Step 5: Test Against Google

```bash
# Run AI agent with your profile
python -m src.agent.main_agent \
    --profile profiles/sterling.yaml \
    --task "Navigate to google.com and search for 'weather'"
    --openrouter-key YOUR_KEY

# Monitor for bot detection
# If detected, record more sessions and refine profile
```

---

## Configuration

### profiler_config.yaml

```yaml
# Profiler Configuration

# Recording settings
recording:
  mouse_sample_rate_hz: 1000  # Maximum precision
  keyboard_include_modifiers: true
  save_screenshots: true
  screenshot_interval_ms: 1000  # Every second during recording
  
# Calibration settings
calibration:
  fitts_law:
    num_trials: 50
    target_sizes: [10, 20, 40, 80]
    distances: [100, 200, 400, 800]
  typing:
    passages_count: 10
    min_passage_length: 40
    max_passage_length: 200

# OpenRouter settings
openrouter:
  api_key: "${OPENROUTER_API_KEY}"  # From environment
  coder_model: "qwen/qwen-2.5-coder-32b-instruct"
  vision_model: "qwen/qwen-2-vl-72b-instruct"
  max_tokens: 4096
  temperature: 0.7

# Profile application settings
profile:
  default_profile: "profiles/default.yaml"
  user_profile: "profiles/sterling.yaml"
  
  # How strictly to follow profile
  strictness: 0.8  # 1.0 = exact match, 0.0 = generic human
  
  # Add randomness within profile bounds
  variance_multiplier: 1.0

# Passthrough display settings
display:
  width: 1920
  height: 1080
  fullscreen: false
  show_debug_overlay: true  # Show recording indicator
```

---

## Testing Protocol

### Google Bot Detection Test

1. **Baseline Test**: Navigate to Google, perform search, click results
2. **reCAPTCHA Test**: Visit sites with reCAPTCHA v3, check scores
3. **Login Test**: Log into Google account, check for security challenges
4. **Extended Session**: Run for 30+ minutes, monitor for flags

### Success Criteria

| Test | Pass Criteria |
|------|---------------|
| Mouse movement | No "robotic" detection alerts |
| reCAPTCHA v3 | Score > 0.7 consistently |
| Google Login | No additional verification required |
| Extended session | No account flags or blocks |

### If Detection Occurs

1. Record more calibration data
2. Analyze which patterns differ from recordings
3. Adjust profile parameters
4. Increase variance/randomness
5. Re-test with new profile

---

## Dependencies to Add

```bash
# Add to requirements.txt
pynput>=1.7.6        # Local input capture
pygame>=2.5.0        # Display for calibration/passthrough
scipy>=1.11.0        # Statistical analysis
httpx>=0.25.0        # Async HTTP for OpenRouter
```

---

## Implementation Order

1. **Mouse Recorder** - Basic recording ✓
2. **Keyboard Recorder** - Basic recording ✓
3. **Session Manager** - Save/load sessions ✓
4. **VNC Passthrough** - See + control Windows
5. **Profile Analyzer** - Extract your patterns
6. **Profile Generator** - Create YAML profile
7. **OpenRouter Client** - AI integration
8. **Calibration UI** - Guided exercises
9. **Profile Applier** - Apply to AI output
10. **Replay Engine** - Verify before live use
11. **Detection Testing** - Google validation
