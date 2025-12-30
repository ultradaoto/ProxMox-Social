"""
Profile Analyzer

Analyzes recorded sessions to extract personal behavioral signatures.
Uses statistical analysis including Fitts's Law fitting.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import json
import math
import logging

logger = logging.getLogger(__name__)

# Try to import numpy/scipy, provide fallbacks
try:
    import numpy as np
    from scipy import stats
    from scipy.optimize import curve_fit
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    logger.warning("scipy not available, using basic statistics")


@dataclass
class MouseProfile:
    """Personal mouse movement profile."""
    # Fitts's Law coefficients (T = a + b * log2(D/W + 1))
    fitts_a: float  # Intercept (base reaction time in ms)
    fitts_b: float  # Slope (time per bit of difficulty)
    fitts_r2: float  # Goodness of fit

    # Movement characteristics
    avg_velocity: float  # Average movement speed (pixels/sec)
    velocity_std: float  # Velocity variation
    acceleration_profile: List[float]  # Normalized acceleration curve (10 bins)

    # Trajectory shape
    curvature_mean: float  # Average trajectory curvature (path/direct ratio)
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

    # Additional characteristics
    direction_bias: Optional[float] = None  # Tendency toward certain directions
    speed_per_distance: Optional[Dict[str, float]] = None  # Speed at different distances


@dataclass
class KeyboardProfile:
    """Personal typing profile."""
    # Overall speed
    wpm_mean: float
    wpm_std: float

    # Inter-key intervals
    iki_mean: float  # Mean inter-key interval (ms)
    iki_std: float
    iki_distribution: str  # 'normal', 'lognormal', 'gamma'

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

    # Additional characteristics
    burst_wpm: Optional[float] = None  # WPM during burst typing
    key_specific_timing: Optional[Dict[str, float]] = None  # Per-key timing


@dataclass
class InteractionProfile:
    """Interaction pattern profile."""
    # Think time before actions
    think_time_mean: float
    think_time_std: float
    think_time_distribution: str

    # Read time (based on pause before scroll/click after page load)
    read_speed_chars_per_sec: float

    # Action sequences
    common_sequences: List[Tuple[str, str, float]]  # (action1, action2, typical_delay)

    # Recovery patterns
    error_recovery_delay: float


class ProfileAnalyzer:
    """
    Analyzes recorded sessions to build personal profiles.

    Features:
        - Fitts's Law coefficient extraction
        - Velocity and trajectory analysis
        - Typing rhythm analysis
        - Digraph timing extraction
        - Statistical distribution fitting
    """

    def __init__(self):
        """Initialize profile analyzer."""
        pass

    def analyze_mouse_session(self, events: List[dict]) -> MouseProfile:
        """
        Analyze mouse events and extract profile.

        Args:
            events: List of mouse event dictionaries

        Returns:
            MouseProfile with extracted characteristics
        """
        # Extract movements (sequences between clicks)
        movements = self._extract_movements(events)

        # Fit Fitts's Law
        fitts_a, fitts_b, fitts_r2 = self._fit_fitts_law(movements)

        # Analyze velocity profile
        velocities = self._calculate_velocities(events)
        avg_velocity = self._mean(velocities) if velocities else 500
        velocity_std = self._std(velocities) if velocities else 200

        # Analyze trajectory curvature
        curvatures = self._calculate_curvatures(movements)
        curvature_mean = self._mean(curvatures) if curvatures else 1.1
        curvature_std = self._std(curvatures) if curvatures else 0.15

        # Detect overshoots
        overshoot_rate, overshoot_distances = self._detect_overshoots(movements)
        overshoot_distance_mean = self._mean(overshoot_distances) if overshoot_distances else 0

        # Analyze jitter (micro-movements while "stationary")
        jitter_amp, jitter_freq = self._analyze_jitter(events)

        # Analyze clicks
        click_durations = self._get_click_durations(events)
        double_click_intervals = self._get_double_click_intervals(events)

        # Get acceleration profile
        accel_profile = self._get_acceleration_profile(movements)

        return MouseProfile(
            fitts_a=fitts_a,
            fitts_b=fitts_b,
            fitts_r2=fitts_r2,
            avg_velocity=avg_velocity,
            velocity_std=velocity_std,
            acceleration_profile=accel_profile,
            curvature_mean=curvature_mean,
            curvature_std=curvature_std,
            overshoot_rate=overshoot_rate,
            overshoot_distance_mean=overshoot_distance_mean,
            jitter_amplitude=jitter_amp,
            jitter_frequency=jitter_freq,
            click_duration_mean=self._mean(click_durations) if click_durations else 100,
            click_duration_std=self._std(click_durations) if click_durations else 30,
            double_click_interval_mean=self._mean(double_click_intervals) if double_click_intervals else 150,
            double_click_interval_std=self._std(double_click_intervals) if double_click_intervals else 40
        )

    def analyze_keyboard_session(self, events: List[dict]) -> KeyboardProfile:
        """
        Analyze keyboard events and extract profile.

        Args:
            events: List of keyboard event dictionaries

        Returns:
            KeyboardProfile with extracted characteristics
        """
        # Filter press events
        press_events = [e for e in events if e.get('event_type') == 'press']

        if len(press_events) < 10:
            return self._default_keyboard_profile()

        # Extract inter-key intervals
        ikis = []
        for i in range(1, len(press_events)):
            iki = press_events[i].get('inter_key_interval')
            if iki and iki < 2000:  # Filter extreme values
                ikis.append(iki)

        iki_mean = self._mean(ikis) if ikis else 150
        iki_std = self._std(ikis) if ikis else 50

        # Determine IKI distribution
        iki_distribution = self._fit_distribution(ikis) if ikis else 'lognormal'

        # Extract hold durations
        release_events = [e for e in events if e.get('event_type') == 'release']
        hold_durations = [e.get('hold_duration') for e in release_events
                        if e.get('hold_duration') and e['hold_duration'] < 500]

        hold_mean = self._mean(hold_durations) if hold_durations else 100
        hold_std = self._std(hold_durations) if hold_durations else 30

        # Calculate WPM
        wpm_values = self._calculate_wpm_samples(press_events)
        wpm_mean = self._mean(wpm_values) if wpm_values else 50
        wpm_std = self._std(wpm_values) if wpm_values else 15

        # Extract digraph timing
        digraph_timing = self._extract_digraph_timing(press_events)

        # Analyze errors
        error_rate = self._calculate_error_rate(press_events)
        common_errors = self._categorize_errors(press_events)
        correction_delay = self._get_correction_delay(press_events)

        # Analyze pause patterns
        word_pause, sentence_pause = self._analyze_pauses(press_events)
        think_threshold = self._calculate_think_threshold(ikis) if ikis else 1500

        return KeyboardProfile(
            wpm_mean=wpm_mean,
            wpm_std=wpm_std,
            iki_mean=iki_mean,
            iki_std=iki_std,
            iki_distribution=iki_distribution,
            hold_duration_mean=hold_mean,
            hold_duration_std=hold_std,
            digraph_timing=digraph_timing,
            error_rate=error_rate,
            common_errors=common_errors,
            correction_delay_mean=correction_delay,
            word_pause_mean=word_pause,
            sentence_pause_mean=sentence_pause,
            think_pause_threshold=think_threshold
        )

    def _fit_fitts_law(self, movements: List[dict]) -> Tuple[float, float, float]:
        """
        Fit Fitts's Law: T = a + b * log2(D/W + 1)

        Returns: (a, b, r_squared)
        """
        if len(movements) < 10:
            return 50.0, 150.0, 0.0

        # Extract distance and time for each movement
        distances = []
        times = []
        target_widths = []

        for movement in movements:
            d = movement.get('distance', 0)
            w = movement.get('target_width', 20)
            t = movement.get('duration', 0) * 1000  # Convert to ms

            if d > 10 and t > 0 and w > 0:
                distances.append(d)
                target_widths.append(w)
                times.append(t)

        if len(distances) < 5:
            return 50.0, 150.0, 0.0

        # Calculate index of difficulty
        id_values = [math.log2(d/w + 1) for d, w in zip(distances, target_widths)]

        if HAS_SCIPY:
            # Linear regression
            slope, intercept, r_value, p_value, std_err = stats.linregress(id_values, times)
            return float(intercept), float(slope), float(r_value ** 2)
        else:
            # Basic linear regression
            n = len(id_values)
            sum_x = sum(id_values)
            sum_y = sum(times)
            sum_xy = sum(x*y for x, y in zip(id_values, times))
            sum_xx = sum(x*x for x in id_values)

            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            intercept = (sum_y - slope * sum_x) / n

            # Calculate R²
            y_mean = sum_y / n
            ss_tot = sum((y - y_mean)**2 for y in times)
            ss_res = sum((y - (intercept + slope*x))**2 for x, y in zip(id_values, times))
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

            return intercept, slope, r2

    def _extract_movements(self, events: List[dict]) -> List[dict]:
        """Extract complete movements (start to click/stop)."""
        movements = []
        current_movement = {'points': [], 'start_time': None}

        for event in events:
            if event.get('event_type') == 'move':
                if current_movement['start_time'] is None:
                    current_movement['start_time'] = event['timestamp']
                current_movement['points'].append({
                    'x': event['x'],
                    'y': event['y'],
                    't': event['timestamp']
                })

            elif event.get('event_type') == 'click' and event.get('pressed'):
                # End of movement
                if current_movement['points']:
                    points = current_movement['points']
                    start = (points[0]['x'], points[0]['y'])
                    end = (points[-1]['x'], points[-1]['y'])

                    distance = math.sqrt((end[0]-start[0])**2 + (end[1]-start[1])**2)

                    movement = {
                        'points': [(p['x'], p['y']) for p in points],
                        'start_point': start,
                        'end_point': end,
                        'distance': distance,
                        'duration': event['timestamp'] - current_movement['start_time'],
                        'target_width': 20  # Estimate
                    }
                    movements.append(movement)

                current_movement = {'points': [], 'start_time': None}

        return movements

    def _calculate_velocities(self, events: List[dict]) -> List[float]:
        """Calculate velocity for each movement event."""
        velocities = []
        for event in events:
            if event.get('event_type') == 'move' and event.get('velocity'):
                velocities.append(event['velocity'])
        return velocities

    def _calculate_curvatures(self, movements: List[dict]) -> List[float]:
        """Calculate trajectory curvature (path length / direct distance)."""
        curvatures = []
        for movement in movements:
            points = movement.get('points', [])
            if len(points) >= 3 and movement.get('distance', 0) > 10:
                # Calculate path length
                path_length = 0
                for i in range(1, len(points)):
                    dx = points[i][0] - points[i-1][0]
                    dy = points[i][1] - points[i-1][1]
                    path_length += math.sqrt(dx*dx + dy*dy)

                curvature = path_length / movement['distance']
                if curvature < 5:  # Filter extreme values
                    curvatures.append(curvature)

        return curvatures

    def _detect_overshoots(self, movements: List[dict]) -> Tuple[float, List[float]]:
        """Detect movements that overshoot and correct."""
        overshoots = 0
        overshoot_distances = []

        for movement in movements:
            points = movement.get('points', [])
            if len(points) < 5:
                continue

            start = movement['start_point']
            end = movement['end_point']
            end_dist = movement['distance']

            for point in points[:-1]:
                dist_from_start = math.sqrt((point[0]-start[0])**2 + (point[1]-start[1])**2)
                if dist_from_start > end_dist * 1.05:  # 5% threshold
                    overshoots += 1
                    overshoot_distances.append(dist_from_start - end_dist)
                    break

        rate = overshoots / len(movements) if movements else 0
        return rate, overshoot_distances

    def _analyze_jitter(self, events: List[dict]) -> Tuple[float, float]:
        """Analyze micro-movements during idle periods."""
        if not events:
            return 3.0, 10.0

        # Find periods with minimal net movement
        window_size = 0.5  # 500ms
        jitter_values = []

        move_events = [e for e in events if e.get('event_type') == 'move']

        i = 0
        while i < len(move_events):
            window = []
            start_time = move_events[i]['timestamp']

            while i < len(move_events) and move_events[i]['timestamp'] - start_time < window_size:
                window.append(move_events[i])
                i += 1

            if len(window) > 2:
                positions = [(e['x'], e['y']) for e in window]
                center_x = sum(p[0] for p in positions) / len(positions)
                center_y = sum(p[1] for p in positions) / len(positions)

                distances = [math.sqrt((p[0]-center_x)**2 + (p[1]-center_y)**2) for p in positions]
                rms = math.sqrt(sum(d*d for d in distances) / len(distances))

                if rms < 30:  # Small movement = jitter
                    jitter_values.extend(distances)

        if jitter_values:
            jitter_amp = math.sqrt(sum(v*v for v in jitter_values) / len(jitter_values))
            jitter_freq = len(jitter_values) / (events[-1]['timestamp'] - events[0]['timestamp'])
        else:
            jitter_amp = 3.0
            jitter_freq = 10.0

        return jitter_amp, jitter_freq

    def _get_click_durations(self, events: List[dict]) -> List[float]:
        """Extract click durations (press to release)."""
        durations = []
        press_times = {}

        for event in events:
            if event.get('event_type') == 'click':
                button = event.get('button', 'left')
                if event.get('pressed'):
                    press_times[button] = event['timestamp']
                else:
                    if button in press_times:
                        duration = (event['timestamp'] - press_times[button]) * 1000
                        if duration < 1000:  # Filter extreme values
                            durations.append(duration)
                        del press_times[button]

        return durations

    def _get_double_click_intervals(self, events: List[dict]) -> List[float]:
        """Extract intervals between double-clicks."""
        intervals = []
        last_click_time = None

        for event in events:
            if event.get('event_type') == 'click' and event.get('pressed'):
                if last_click_time:
                    interval = (event['timestamp'] - last_click_time) * 1000
                    if interval < 500:  # Likely double-click
                        intervals.append(interval)
                last_click_time = event['timestamp']

        return intervals

    def _get_acceleration_profile(self, movements: List[dict]) -> List[float]:
        """Get normalized acceleration profile across movements."""
        profiles = []

        for movement in movements:
            points = movement.get('points', [])
            if len(points) >= 10:
                # Calculate velocity at each point
                velocities = []
                for i in range(1, len(points)):
                    dx = points[i][0] - points[i-1][0]
                    dy = points[i][1] - points[i-1][1]
                    velocities.append(math.sqrt(dx*dx + dy*dy))

                if velocities:
                    # Bin into 10 segments
                    bin_size = len(velocities) // 10
                    if bin_size > 0:
                        binned = []
                        for b in range(10):
                            start = b * bin_size
                            end = start + bin_size if b < 9 else len(velocities)
                            binned.append(sum(velocities[start:end]) / (end - start))

                        # Normalize
                        max_v = max(binned) if binned else 1
                        profile = [v / max_v for v in binned]
                        profiles.append(profile)

        if profiles:
            # Average across all movements
            avg_profile = []
            for i in range(10):
                values = [p[i] for p in profiles if len(p) > i]
                avg_profile.append(sum(values) / len(values) if values else 0.5)
            return avg_profile
        else:
            # Default bell curve
            return [0.2, 0.5, 0.8, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1]

    def _calculate_wpm_samples(self, press_events: List[dict]) -> List[float]:
        """Calculate WPM for sliding windows."""
        if len(press_events) < 20:
            return []

        wpm_values = []
        window_size = 30  # 30 keystrokes

        for i in range(0, len(press_events) - window_size, 10):
            window = press_events[i:i + window_size]
            duration = window[-1]['timestamp'] - window[0]['timestamp']
            if duration > 0:
                # Estimate words (average 5 characters per word)
                words = window_size / 5
                wpm = (words / duration) * 60
                if 10 < wpm < 200:  # Filter unreasonable values
                    wpm_values.append(wpm)

        return wpm_values

    def _extract_digraph_timing(self, press_events: List[dict]) -> Dict[str, Tuple[float, float]]:
        """Extract timing for digraphs (letter pairs)."""
        digraph_times = {}

        for i in range(1, len(press_events)):
            prev_key = press_events[i-1].get('key', '')
            curr_key = press_events[i].get('key', '')

            # Only consider letter keys
            if len(prev_key) == 1 and len(curr_key) == 1:
                if prev_key.isalpha() and curr_key.isalpha():
                    digraph = f"{prev_key}_{curr_key}".lower()
                    iki = press_events[i].get('inter_key_interval')

                    if iki and iki < 2000:
                        if digraph not in digraph_times:
                            digraph_times[digraph] = []
                        digraph_times[digraph].append(iki)

        # Calculate statistics for each digraph
        result = {}
        for digraph, times in digraph_times.items():
            if len(times) >= 3:
                result[digraph] = (self._mean(times), self._std(times))

        # Return top 50 by frequency
        sorted_digraphs = sorted(result.items(), key=lambda x: -len(digraph_times.get(x[0], [])))
        return dict(sorted_digraphs[:50])

    def _calculate_error_rate(self, press_events: List[dict]) -> float:
        """Calculate error rate (backspaces per 100 keystrokes)."""
        backspaces = sum(1 for e in press_events if e.get('key') == 'backspace')
        total = len(press_events)
        return (backspaces / total) * 100 if total > 0 else 0

    def _categorize_errors(self, press_events: List[dict]) -> Dict[str, float]:
        """Categorize error types."""
        errors = {
            'immediate': 0,
            'delayed': 0,
            'repeated': 0,
            'adjacent': 0
        }

        for i, event in enumerate(press_events):
            if event.get('key') == 'backspace':
                iki = event.get('inter_key_interval', 0)
                if iki < 300:
                    errors['immediate'] += 1
                else:
                    errors['delayed'] += 1

        # Normalize to percentages
        total = sum(errors.values())
        if total > 0:
            return {k: v / total for k, v in errors.items()}
        return errors

    def _get_correction_delay(self, press_events: List[dict]) -> float:
        """Get average delay before backspace correction."""
        delays = []
        for event in press_events:
            if event.get('key') == 'backspace':
                iki = event.get('inter_key_interval')
                if iki and iki < 3000:
                    delays.append(iki)
        return self._mean(delays) if delays else 500

    def _analyze_pauses(self, press_events: List[dict]) -> Tuple[float, float]:
        """Analyze pause patterns."""
        word_pauses = []
        sentence_pauses = []

        for event in press_events:
            key = event.get('key', '')
            iki = event.get('inter_key_interval')

            if not iki:
                continue

            if key == 'space':
                if 200 < iki < 2000:
                    word_pauses.append(iki)
            elif key in '.!?':
                if 300 < iki < 5000:
                    sentence_pauses.append(iki)

        word_mean = self._mean(word_pauses) if word_pauses else 300
        sentence_mean = self._mean(sentence_pauses) if sentence_pauses else 800

        return word_mean, sentence_mean

    def _calculate_think_threshold(self, ikis: List[float]) -> float:
        """Calculate threshold for 'thinking' pauses."""
        if not ikis:
            return 1500

        # Use 90th percentile as threshold
        sorted_ikis = sorted(ikis)
        idx = int(len(sorted_ikis) * 0.9)
        return sorted_ikis[idx]

    def _fit_distribution(self, values: List[float]) -> str:
        """Determine best-fitting distribution."""
        if not HAS_SCIPY or len(values) < 20:
            return 'lognormal'

        # Test different distributions
        distributions = {
            'normal': stats.norm,
            'lognormal': stats.lognorm,
            'gamma': stats.gamma
        }

        best_dist = 'lognormal'
        best_sse = float('inf')

        for name, dist in distributions.items():
            try:
                params = dist.fit(values)
                fitted = dist.pdf(sorted(values), *params)
                actual = [1/len(values)] * len(values)
                sse = sum((f - a)**2 for f, a in zip(fitted, actual))
                if sse < best_sse:
                    best_sse = sse
                    best_dist = name
            except:
                pass

        return best_dist

    def _default_keyboard_profile(self) -> KeyboardProfile:
        """Return default keyboard profile."""
        return KeyboardProfile(
            wpm_mean=50.0,
            wpm_std=15.0,
            iki_mean=150.0,
            iki_std=50.0,
            iki_distribution='lognormal',
            hold_duration_mean=100.0,
            hold_duration_std=30.0,
            digraph_timing={},
            error_rate=2.0,
            common_errors={'immediate': 0.6, 'delayed': 0.4},
            correction_delay_mean=500.0,
            word_pause_mean=300.0,
            sentence_pause_mean=800.0,
            think_pause_threshold=1500.0
        )

    def _mean(self, values: List[float]) -> float:
        """Calculate mean."""
        return sum(values) / len(values) if values else 0

    def _std(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0
        mean = self._mean(values)
        variance = sum((x - mean)**2 for x in values) / len(values)
        return math.sqrt(variance)
