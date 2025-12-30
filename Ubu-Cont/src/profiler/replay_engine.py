"""
Replay Engine

Replays recorded sessions for verification and testing.
Compares AI-generated actions to recorded human actions.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Callable, Tuple
from pathlib import Path
import time
import json
import math
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReplayConfig:
    """Replay configuration."""
    speed_multiplier: float = 1.0  # 1.0 = real time
    apply_profile: bool = True     # Apply profile adjustments
    visual_mode: bool = False      # Show visual feedback
    pause_between_actions: float = 0.0  # Extra pause
    dry_run: bool = False          # Don't actually send events


class ReplayEngine:
    """
    Replays recorded sessions for verification.

    Features:
        - Real-time or accelerated playback
        - Profile-adjusted replay
        - Visual mode for monitoring
        - Dry run capability
        - Pause/resume control
    """

    def __init__(
        self,
        hid_sender: Optional[Any] = None,
        profile_applier: Optional[Any] = None
    ):
        """
        Initialize replay engine.

        Args:
            hid_sender: HID sender for sending events to Windows
            profile_applier: ProfileApplier for adjusting events
        """
        self.hid_sender = hid_sender
        self.profile_applier = profile_applier

        # State
        self.playing = False
        self.paused = False
        self.current_event_index = 0

        # Callbacks
        self.on_event: Optional[Callable[[Dict], None]] = None
        self.on_progress: Optional[Callable[[int, int], None]] = None
        self.on_complete: Optional[Callable[[], None]] = None

    def replay_session(
        self,
        session_path: str,
        config: Optional[ReplayConfig] = None
    ) -> Dict[str, Any]:
        """
        Replay a recorded session.

        Args:
            session_path: Path to session directory
            config: Replay configuration

        Returns:
            Replay statistics
        """
        config = config or ReplayConfig()
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

        all_events.sort(key=lambda e: e.get('timestamp', 0))

        if not all_events:
            logger.warning("No events to replay")
            return {'status': 'empty', 'events_replayed': 0}

        logger.info(f"Replaying {len(all_events)} events from {session_path}")

        # Replay
        self.playing = True
        self.paused = False
        self.current_event_index = 0

        start_time = time.time()
        base_timestamp = all_events[0].get('timestamp', 0)
        events_replayed = 0

        for i, event in enumerate(all_events):
            if not self.playing:
                break

            while self.paused:
                time.sleep(0.1)
                if not self.playing:
                    break

            self.current_event_index = i

            # Calculate when to send this event
            event_offset = (event.get('timestamp', 0) - base_timestamp) / config.speed_multiplier
            target_time = start_time + event_offset

            # Wait until it's time
            wait_time = target_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)

            # Apply profile adjustments if enabled
            if config.apply_profile and self.profile_applier:
                event = self.profile_applier.adjust_event(event)

            # Send event
            if not config.dry_run:
                self._send_event(event)

            events_replayed += 1

            # Callbacks
            if self.on_event:
                self.on_event(event)
            if self.on_progress:
                self.on_progress(i + 1, len(all_events))

            # Extra pause if configured
            if config.pause_between_actions > 0:
                time.sleep(config.pause_between_actions)

        self.playing = False

        if self.on_complete:
            self.on_complete()

        duration = time.time() - start_time
        original_duration = all_events[-1].get('timestamp', 0) - base_timestamp

        return {
            'status': 'complete',
            'events_replayed': events_replayed,
            'total_events': len(all_events),
            'replay_duration': duration,
            'original_duration': original_duration,
            'speed_multiplier': config.speed_multiplier
        }

    def replay_movement(
        self,
        movement_points: List[Tuple[float, int, int]],
        config: Optional[ReplayConfig] = None
    ) -> None:
        """
        Replay a single mouse movement.

        Args:
            movement_points: List of (timestamp, x, y) tuples
            config: Replay configuration
        """
        config = config or ReplayConfig()

        if not movement_points:
            return

        base_time = movement_points[0][0]
        start_time = time.time()

        for timestamp, x, y in movement_points:
            if not self.playing:
                break

            offset = (timestamp - base_time) / config.speed_multiplier
            target_time = start_time + offset

            wait_time = target_time - time.time()
            if wait_time > 0:
                time.sleep(wait_time)

            if not config.dry_run and self.hid_sender:
                self.hid_sender.send_mouse({
                    'type': 'mouse_move',
                    'x': x,
                    'y': y
                })

    def pause(self) -> None:
        """Pause replay."""
        self.paused = True
        logger.info("Replay paused")

    def resume(self) -> None:
        """Resume replay."""
        self.paused = False
        logger.info("Replay resumed")

    def stop(self) -> None:
        """Stop replay."""
        self.playing = False
        logger.info("Replay stopped")

    def _load_events(self, path: Path) -> List[Dict]:
        """Load events from JSONL file."""
        events = []
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        return events

    def _send_event(self, event: Dict) -> None:
        """Send event through HID sender."""
        if not self.hid_sender:
            return

        source = event.get('source', 'mouse')

        if source == 'mouse':
            self._send_mouse_event(event)
        else:
            self._send_keyboard_event(event)

    def _send_mouse_event(self, event: Dict) -> None:
        """Send mouse event."""
        event_type = event.get('event_type')

        if event_type == 'move':
            self.hid_sender.send_mouse({
                'type': 'mouse_move',
                'x': event.get('x', 0),
                'y': event.get('y', 0)
            })

        elif event_type == 'click':
            action = 'down' if event.get('pressed') else 'up'
            self.hid_sender.send_mouse({
                'type': 'mouse_button',
                'button': event.get('button', 'left'),
                'action': action
            })

        elif event_type == 'scroll':
            self.hid_sender.send_mouse({
                'type': 'mouse_wheel',
                'delta': event.get('scroll_dy', 0)
            })

    def _send_keyboard_event(self, event: Dict) -> None:
        """Send keyboard event."""
        action = 'down' if event.get('event_type') == 'press' else 'up'
        self.hid_sender.send_keyboard({
            'type': 'keyboard',
            'key': event.get('key'),
            'action': action
        })


class ProfileTester:
    """
    Tests profile accuracy against recordings.

    Compares AI-generated input to recorded human input
    to measure how well the profile matches.
    """

    def __init__(
        self,
        profile: Dict[str, Any],
        human_mouse: Any,
        human_keyboard: Any
    ):
        """
        Initialize profile tester.

        Args:
            profile: Personal profile dictionary
            human_mouse: HumanMouseController instance
            human_keyboard: HumanKeyboardController instance
        """
        self.profile = profile
        self.human_mouse = human_mouse
        self.human_keyboard = human_keyboard

    def test_movement_similarity(
        self,
        recorded_movement: List[Dict],
        target: Tuple[int, int]
    ) -> Dict[str, float]:
        """
        Compare AI movement to recorded movement.

        Args:
            recorded_movement: List of recorded mouse events
            target: Target position

        Returns:
            Similarity metrics
        """
        if not recorded_movement:
            return {'error': 'No recorded movement'}

        start = (recorded_movement[0]['x'], recorded_movement[0]['y'])

        # Get recorded trajectory
        recorded_points = [(e['x'], e['y']) for e in recorded_movement
                         if e.get('event_type') == 'move']

        if not recorded_points:
            return {'error': 'No movement points in recording'}

        # Generate AI trajectory
        if self.human_mouse:
            ai_trajectory = self.human_mouse.plan_trajectory(start, target)
            ai_points = [(int(p.x), int(p.y)) for p in ai_trajectory]
        else:
            # Simple linear trajectory for testing
            ai_points = self._generate_linear_trajectory(start, target, len(recorded_points))

        # Calculate similarity metrics
        trajectory_sim = self._trajectory_similarity(recorded_points, ai_points)
        timing_sim = self._timing_similarity(recorded_movement)
        velocity_sim = self._velocity_profile_similarity(recorded_movement)

        return {
            'trajectory_similarity': trajectory_sim,
            'timing_similarity': timing_sim,
            'velocity_profile_similarity': velocity_sim,
            'overall_similarity': (trajectory_sim + timing_sim + velocity_sim) / 3
        }

    def test_typing_similarity(
        self,
        recorded_typing: List[Dict],
        text: str
    ) -> Dict[str, float]:
        """
        Compare AI typing to recorded typing.

        Args:
            recorded_typing: List of recorded keyboard events
            text: Text that was typed

        Returns:
            Similarity metrics
        """
        if not recorded_typing:
            return {'error': 'No recorded typing'}

        # Extract recorded inter-key intervals
        recorded_ikis = []
        for i in range(1, len(recorded_typing)):
            if recorded_typing[i].get('event_type') == 'press':
                iki = recorded_typing[i].get('inter_key_interval')
                if iki and iki < 2000:
                    recorded_ikis.append(iki)

        if not recorded_ikis:
            return {'error': 'No IKI data in recording'}

        # Generate AI timing
        if self.human_keyboard:
            ai_action = self.human_keyboard.plan_typing(text)
            ai_ikis = [t[1] for t in ai_action.key_timings[1:]]  # Skip first (no IKI)
        else:
            # Use profile values
            iki_mean = self.profile.get('keyboard', {}).get('timing', {}).get('inter_key_interval_mean_ms', 150)
            ai_ikis = [iki_mean] * (len(recorded_ikis))

        # Calculate similarity
        iki_sim = self._distribution_similarity(recorded_ikis, ai_ikis)

        return {
            'iki_distribution_similarity': iki_sim,
            'overall_similarity': iki_sim
        }

    def run_full_test(
        self,
        session_path: str
    ) -> Dict[str, Any]:
        """
        Run full profile test against a session.

        Args:
            session_path: Path to session directory

        Returns:
            Comprehensive test results
        """
        session_dir = Path(session_path)

        # Load events
        mouse_events = self._load_events(session_dir / "mouse_events.jsonl")
        keyboard_events = self._load_events(session_dir / "keyboard_events.jsonl")

        results = {
            'session': session_path,
            'mouse_tests': [],
            'keyboard_tests': [],
            'overall_score': 0.0
        }

        # Test mouse movements
        movements = self._extract_movements(mouse_events)
        for movement in movements[:10]:  # Test first 10 movements
            if len(movement) > 5:
                target = (movement[-1]['x'], movement[-1]['y'])
                sim = self.test_movement_similarity(movement, target)
                results['mouse_tests'].append(sim)

        # Test typing
        if keyboard_events:
            sim = self.test_typing_similarity(keyboard_events, "")
            results['keyboard_tests'].append(sim)

        # Calculate overall score
        mouse_scores = [t.get('overall_similarity', 0) for t in results['mouse_tests']
                       if 'overall_similarity' in t]
        keyboard_scores = [t.get('overall_similarity', 0) for t in results['keyboard_tests']
                          if 'overall_similarity' in t]

        all_scores = mouse_scores + keyboard_scores
        results['overall_score'] = sum(all_scores) / len(all_scores) if all_scores else 0

        return results

    def _trajectory_similarity(
        self,
        recorded: List[Tuple[int, int]],
        generated: List[Tuple[int, int]]
    ) -> float:
        """Calculate trajectory similarity using Frechet distance approximation."""
        if not recorded or not generated:
            return 0.0

        # Resample to same number of points
        n_points = min(len(recorded), len(generated), 50)
        recorded_resampled = self._resample_trajectory(recorded, n_points)
        generated_resampled = self._resample_trajectory(generated, n_points)

        # Calculate average point distance
        total_distance = 0
        for p1, p2 in zip(recorded_resampled, generated_resampled):
            dist = math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
            total_distance += dist

        avg_distance = total_distance / n_points

        # Convert to similarity (0-1)
        # Threshold: 50 pixels average distance = 0.5 similarity
        similarity = max(0, 1 - (avg_distance / 100))

        return similarity

    def _timing_similarity(self, movement: List[Dict]) -> float:
        """Calculate timing similarity."""
        if len(movement) < 2:
            return 0.5

        # Calculate actual duration
        duration = movement[-1].get('timestamp', 0) - movement[0].get('timestamp', 0)
        duration_ms = duration * 1000

        # Calculate expected duration from profile
        start = (movement[0]['x'], movement[0]['y'])
        end = (movement[-1]['x'], movement[-1]['y'])
        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        fitts = self.profile.get('mouse', {}).get('fitts_law', {})
        a = fitts.get('a', 50)
        b = fitts.get('b', 150)
        expected_ms = a + b * math.log2(distance / 20 + 1) if distance > 0 else a

        # Calculate similarity
        ratio = min(duration_ms, expected_ms) / max(duration_ms, expected_ms)

        return ratio

    def _velocity_profile_similarity(self, movement: List[Dict]) -> float:
        """Calculate velocity profile similarity."""
        move_events = [e for e in movement if e.get('event_type') == 'move']

        if len(move_events) < 10:
            return 0.5

        # Calculate velocity profile
        velocities = []
        for i in range(1, len(move_events)):
            v = move_events[i].get('velocity', 0)
            if v:
                velocities.append(v)

        if not velocities:
            return 0.5

        # Bin into 10 segments
        bin_size = len(velocities) // 10
        if bin_size == 0:
            return 0.5

        profile = []
        for i in range(10):
            start = i * bin_size
            end = start + bin_size if i < 9 else len(velocities)
            profile.append(sum(velocities[start:end]) / (end - start))

        # Normalize
        max_v = max(profile) if profile else 1
        profile = [v / max_v for v in profile]

        # Compare to expected profile
        expected = self.profile.get('mouse', {}).get('acceleration_profile',
                                                      [0.2, 0.5, 0.8, 1.0, 1.0, 0.9, 0.7, 0.5, 0.3, 0.1])

        # Calculate correlation
        if len(profile) == len(expected):
            diff_sum = sum(abs(p - e) for p, e in zip(profile, expected))
            similarity = max(0, 1 - (diff_sum / 10))
            return similarity

        return 0.5

    def _distribution_similarity(
        self,
        recorded: List[float],
        generated: List[float]
    ) -> float:
        """Calculate distribution similarity."""
        if not recorded or not generated:
            return 0.5

        # Compare means and stds
        rec_mean = sum(recorded) / len(recorded)
        gen_mean = sum(generated) / len(generated)

        rec_std = math.sqrt(sum((x - rec_mean)**2 for x in recorded) / len(recorded))
        gen_std = math.sqrt(sum((x - gen_mean)**2 for x in generated) / len(generated))

        mean_ratio = min(rec_mean, gen_mean) / max(rec_mean, gen_mean) if max(rec_mean, gen_mean) > 0 else 1
        std_ratio = min(rec_std + 1, gen_std + 1) / max(rec_std + 1, gen_std + 1)

        return (mean_ratio + std_ratio) / 2

    def _resample_trajectory(
        self,
        points: List[Tuple[int, int]],
        n: int
    ) -> List[Tuple[int, int]]:
        """Resample trajectory to n points."""
        if len(points) <= n:
            return points

        step = len(points) / n
        return [points[int(i * step)] for i in range(n)]

    def _extract_movements(self, events: List[Dict]) -> List[List[Dict]]:
        """Extract individual movements from events."""
        movements = []
        current = []

        for event in events:
            if event.get('event_type') == 'move':
                current.append(event)
            elif event.get('event_type') == 'click' and event.get('pressed'):
                if current:
                    movements.append(current)
                    current = []

        if current:
            movements.append(current)

        return movements

    def _generate_linear_trajectory(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        n_points: int
    ) -> List[Tuple[int, int]]:
        """Generate linear trajectory for testing."""
        points = []
        for i in range(n_points):
            t = i / (n_points - 1) if n_points > 1 else 0
            x = int(start[0] + (end[0] - start[0]) * t)
            y = int(start[1] + (end[1] - start[1]) * t)
            points.append((x, y))
        return points

    def _load_events(self, path: Path) -> List[Dict]:
        """Load events from JSONL file."""
        events = []
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        return events
