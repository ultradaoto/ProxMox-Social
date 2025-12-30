"""
Profile Applier

Applies personal behavioral profile to AI-generated actions,
making them indistinguishable from the user's actual behavior.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import random
import math
import json
import logging

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

logger = logging.getLogger(__name__)


@dataclass
class AdjustedMouseAction:
    """Mouse action with profile-adjusted parameters."""
    x: int
    y: int
    duration_ms: float
    curve_points: List[Tuple[int, int]]  # Bezier control points
    overshoot: Optional[Tuple[int, int]] = None
    click_duration_ms: Optional[float] = None
    pre_click_pause_ms: float = 0
    jitter_points: Optional[List[Tuple[int, int]]] = None


@dataclass
class AdjustedKeyboardAction:
    """Keyboard action with profile-adjusted parameters."""
    text: str
    key_timings: List[Tuple[str, float, float]]  # (key, delay_ms, hold_ms)
    typos: List[Tuple[int, str, str]]  # (position, wrong_char, correct_char)
    pause_points: List[Tuple[int, float]]  # (position, pause_ms)


class ProfileApplier:
    """
    Applies personal profile to AI-generated actions.

    Features:
        - Fitts's Law timing calculation
        - Trajectory shaping with profile curves
        - Typing rhythm application
        - Error injection matching personal patterns
        - Jitter and micro-movement addition
    """

    def __init__(
        self,
        profile_path: Optional[str] = None,
        strictness: float = 0.8
    ):
        """
        Initialize profile applier.

        Args:
            profile_path: Path to profile YAML/JSON file
            strictness: How strictly to follow profile (0-1)
                       1.0 = exact match, 0.0 = generic human
        """
        self.strictness = strictness
        self.profile: Dict[str, Any] = {}

        if profile_path:
            self.load_profile(profile_path)

        # Fatigue simulation state
        self._session_start_time: Optional[float] = None
        self._action_count: int = 0

    def load_profile(self, path: str) -> None:
        """
        Load profile from file.

        Args:
            path: Path to profile file
        """
        path = Path(path)

        if not path.exists():
            logger.error(f"Profile not found: {path}")
            return

        with open(path) as f:
            if path.suffix in ['.yaml', '.yml']:
                if HAS_YAML:
                    self.profile = yaml.safe_load(f)
                else:
                    raise ImportError("PyYAML required for YAML files")
            else:
                self.profile = json.load(f)

        logger.info(f"Loaded profile: {self.profile.get('metadata', {}).get('profile_name', 'unknown')}")

    def calculate_movement_time(
        self,
        distance: float,
        target_width: float = 20
    ) -> float:
        """
        Calculate movement time using personal Fitts's Law coefficients.

        Args:
            distance: Distance to target in pixels
            target_width: Target width in pixels

        Returns:
            Movement time in milliseconds
        """
        fitts = self.profile.get('mouse', {}).get('fitts_law', {})
        a = fitts.get('a', 50)
        b = fitts.get('b', 150)

        # Fitts's Law: T = a + b * log2(D/W + 1)
        if distance <= 0:
            return a

        id_value = math.log2(distance / target_width + 1)
        base_time = a + b * id_value

        # Apply strictness and add variance
        variance = (1 - self.strictness) * base_time * 0.3
        adjusted_time = base_time + random.gauss(0, variance)

        # Apply fatigue if enabled
        adjusted_time *= self._get_fatigue_multiplier()

        return max(50, adjusted_time)  # Minimum 50ms

    def adjust_mouse_movement(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        target_width: float = 20
    ) -> AdjustedMouseAction:
        """
        Adjust mouse movement to match personal profile.

        Args:
            start: Starting position (x, y)
            end: Target position (x, y)
            target_width: Target element width

        Returns:
            AdjustedMouseAction with all parameters
        """
        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        # Calculate duration
        duration = self.calculate_movement_time(distance, target_width)

        # Generate curve points based on profile
        curve_points = self._generate_curve_points(start, end)

        # Determine if overshoot should occur
        overshoot = self._generate_overshoot(end) if self._should_overshoot() else None

        # Pre-click pause
        mouse_config = self.profile.get('mouse', {})
        clicks = mouse_config.get('clicks', {})
        pre_pause = random.gauss(100, 30)  # Base pause

        # Click duration
        click_duration = random.gauss(
            clicks.get('duration_mean_ms', 100),
            clicks.get('duration_std_ms', 30)
        )

        # Generate jitter points for idle periods
        jitter = self._generate_jitter_points(end, 5) if random.random() < 0.3 else None

        return AdjustedMouseAction(
            x=end[0],
            y=end[1],
            duration_ms=duration,
            curve_points=curve_points,
            overshoot=overshoot,
            click_duration_ms=max(50, click_duration),
            pre_click_pause_ms=max(0, pre_pause),
            jitter_points=jitter
        )

    def adjust_keyboard_input(
        self,
        text: str,
        context: str = "normal"
    ) -> AdjustedKeyboardAction:
        """
        Adjust keyboard input to match personal profile.

        Args:
            text: Text to type
            context: Typing context ('normal', 'password', 'code', 'fast')

        Returns:
            AdjustedKeyboardAction with all parameters
        """
        keyboard = self.profile.get('keyboard', {})
        timing = keyboard.get('timing', {})
        errors = keyboard.get('errors', {})
        pauses = keyboard.get('pauses', {})
        digraphs = keyboard.get('digraph_timing', {})

        key_timings = []
        typos = []
        pause_points = []

        base_iki = timing.get('inter_key_interval_mean_ms', 150)
        iki_std = timing.get('inter_key_interval_std_ms', 50)
        hold_mean = timing.get('hold_duration_mean_ms', 100)
        hold_std = timing.get('hold_duration_std_ms', 30)
        error_rate = errors.get('rate_per_100_keys', 2) / 100

        prev_char = None
        i = 0
        while i < len(text):
            char = text[i]

            # Calculate inter-key interval
            delay = self._get_key_delay(
                prev_char, char, base_iki, iki_std, digraphs, context
            )

            # Calculate hold duration
            hold = max(30, random.gauss(hold_mean, hold_std))

            # Check for word/sentence pauses
            if char == ' ':
                delay += random.gauss(
                    pauses.get('word_pause_mean_ms', 100),
                    50
                )
            elif char in '.!?\n':
                delay += random.gauss(
                    pauses.get('sentence_pause_mean_ms', 300),
                    100
                )
                pause_points.append((i, delay))

            # Inject typo based on error rate
            if random.random() < error_rate * self.strictness:
                typo_char = self._generate_typo(char)
                if typo_char:
                    typos.append((i, typo_char, char))
                    # Add typo keystroke
                    key_timings.append((typo_char, delay, hold))
                    # Add backspace
                    correction_delay = random.gauss(
                        errors.get('correction_delay_ms', 300),
                        100
                    )
                    key_timings.append(('backspace', max(50, correction_delay), 50))
                    # Continue with correct character
                    delay = base_iki * 0.7  # Faster after correction

            key_timings.append((char, max(30, delay), hold))

            prev_char = char
            i += 1

        # Apply fatigue
        fatigue = self._get_fatigue_multiplier()
        if fatigue > 1.0:
            key_timings = [
                (k, d * fatigue, h) for k, d, h in key_timings
            ]

        return AdjustedKeyboardAction(
            text=text,
            key_timings=key_timings,
            typos=typos,
            pause_points=pause_points
        )

    def adjust_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adjust a generic event based on profile.

        Args:
            event: Event dictionary with type and parameters

        Returns:
            Adjusted event dictionary
        """
        event_type = event.get('event_type') or event.get('type')

        if event_type == 'move':
            # Adjust velocity based on profile
            velocity = self.profile.get('mouse', {}).get('velocity', {})
            target_velocity = random.gauss(
                velocity.get('mean_pixels_per_sec', 500),
                velocity.get('std', 200)
            )
            event['velocity'] = target_velocity

        elif event_type == 'click':
            # Adjust click duration
            clicks = self.profile.get('mouse', {}).get('clicks', {})
            event['click_duration'] = random.gauss(
                clicks.get('duration_mean_ms', 100),
                clicks.get('duration_std_ms', 30)
            )

        elif event_type in ['press', 'release']:
            # Adjust key timing
            timing = self.profile.get('keyboard', {}).get('timing', {})
            if 'inter_key_interval' not in event:
                event['inter_key_interval'] = random.gauss(
                    timing.get('inter_key_interval_mean_ms', 150),
                    timing.get('inter_key_interval_std_ms', 50)
                )

        return event

    def _generate_curve_points(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Generate Bezier curve control points based on profile."""
        trajectory = self.profile.get('mouse', {}).get('trajectory', {})
        curvature = trajectory.get('curvature_mean', 1.1)

        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        # Calculate perpendicular offset for control points
        dx = end[0] - start[0]
        dy = end[1] - start[1]

        # Perpendicular direction
        perp_x = -dy
        perp_y = dx

        # Normalize
        length = math.sqrt(perp_x**2 + perp_y**2) or 1
        perp_x /= length
        perp_y /= length

        # Offset based on curvature
        offset = distance * (curvature - 1) * random.choice([-1, 1])
        offset *= random.gauss(1, 0.3)

        # Two control points at 1/3 and 2/3 of path
        ctrl1 = (
            int(start[0] + dx * 0.33 + perp_x * offset * 0.7),
            int(start[1] + dy * 0.33 + perp_y * offset * 0.7)
        )
        ctrl2 = (
            int(start[0] + dx * 0.67 + perp_x * offset * 0.5),
            int(start[1] + dy * 0.67 + perp_y * offset * 0.5)
        )

        return [start, ctrl1, ctrl2, end]

    def _should_overshoot(self) -> bool:
        """Determine if movement should overshoot based on profile."""
        trajectory = self.profile.get('mouse', {}).get('trajectory', {})
        rate = trajectory.get('overshoot_rate', 0.15)
        return random.random() < rate * self.strictness

    def _generate_overshoot(self, target: Tuple[int, int]) -> Tuple[int, int]:
        """Generate overshoot position."""
        trajectory = self.profile.get('mouse', {}).get('trajectory', {})
        distance = trajectory.get('overshoot_distance_mean', 10)

        angle = random.uniform(0, 2 * math.pi)
        offset_x = int(distance * math.cos(angle) * random.gauss(1, 0.3))
        offset_y = int(distance * math.sin(angle) * random.gauss(1, 0.3))

        return (target[0] + offset_x, target[1] + offset_y)

    def _generate_jitter_points(
        self,
        center: Tuple[int, int],
        count: int
    ) -> List[Tuple[int, int]]:
        """Generate jitter micro-movement points."""
        jitter = self.profile.get('mouse', {}).get('jitter', {})
        amplitude = jitter.get('amplitude_pixels', 3)

        points = []
        for _ in range(count):
            offset_x = int(random.gauss(0, amplitude))
            offset_y = int(random.gauss(0, amplitude))
            points.append((center[0] + offset_x, center[1] + offset_y))

        return points

    def _get_key_delay(
        self,
        prev_char: Optional[str],
        char: str,
        base_iki: float,
        iki_std: float,
        digraphs: Dict[str, Dict],
        context: str
    ) -> float:
        """Calculate delay before pressing a key."""
        # Check for digraph-specific timing
        if prev_char:
            digraph = f"{prev_char}_{char}".lower()
            if digraph in digraphs:
                timing = digraphs[digraph]
                return random.gauss(
                    timing.get('mean_ms', base_iki),
                    timing.get('std_ms', iki_std)
                )

        # Context adjustments
        context_multiplier = {
            'normal': 1.0,
            'password': 1.3,  # Slower for passwords
            'code': 0.9,      # Slightly faster for code
            'fast': 0.7       # Burst typing
        }.get(context, 1.0)

        delay = random.gauss(base_iki, iki_std) * context_multiplier

        return delay

    def _generate_typo(self, char: str) -> Optional[str]:
        """Generate a typo for a character."""
        if not char.isalpha():
            return None

        # QWERTY adjacency map
        adjacent = {
            'q': 'wa', 'w': 'qeas', 'e': 'wrd', 'r': 'eft',
            't': 'rgy', 'y': 'thu', 'u': 'yji', 'i': 'uko',
            'o': 'ilp', 'p': 'ol',
            'a': 'qsz', 's': 'awdx', 'd': 'sefc', 'f': 'drgv',
            'g': 'fthb', 'h': 'gyjn', 'j': 'hukm', 'k': 'jil',
            'l': 'kop',
            'z': 'asx', 'x': 'zdc', 'c': 'xfv', 'v': 'cgb',
            'b': 'vhn', 'n': 'bjm', 'm': 'nk'
        }

        lower = char.lower()
        if lower in adjacent:
            typo = random.choice(adjacent[lower])
            return typo.upper() if char.isupper() else typo

        return None

    def _get_fatigue_multiplier(self) -> float:
        """Get fatigue multiplier based on session duration."""
        advanced = self.profile.get('advanced', {})
        fatigue = advanced.get('fatigue_simulation', {})

        if not fatigue.get('enabled', False):
            return 1.0

        import time
        if self._session_start_time is None:
            self._session_start_time = time.time()

        hours = (time.time() - self._session_start_time) / 3600
        rate = fatigue.get('degradation_rate', 0.02)

        return 1.0 + (hours * rate)

    def reset_fatigue(self) -> None:
        """Reset fatigue simulation (e.g., after a break)."""
        self._session_start_time = None
        self._action_count = 0

    def get_think_time(self) -> float:
        """Get a think time delay based on profile."""
        think = self.profile.get('interaction', {}).get('think_time', {})

        min_ms = think.get('min_ms', 200)
        max_ms = think.get('max_ms', 3000)
        mean_ms = think.get('mean_ms', 800)
        distribution = think.get('distribution', 'lognormal')

        if distribution == 'lognormal':
            # Log-normal distribution
            value = random.lognormvariate(math.log(mean_ms), 0.5)
        else:
            value = random.gauss(mean_ms, mean_ms * 0.3)

        return max(min_ms, min(max_ms, value))

    def get_double_click_interval(self) -> float:
        """Get double-click interval based on profile."""
        clicks = self.profile.get('mouse', {}).get('clicks', {})
        return random.gauss(
            clicks.get('double_click_interval_mean_ms', 150),
            clicks.get('double_click_interval_std_ms', 40)
        )
