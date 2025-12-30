"""
Calibration Exercises

Guided exercises to capture personal behavioral patterns
under controlled conditions.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Callable
from pathlib import Path
import time
import random
import math
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class CalibrationTarget:
    """A target for Fitts's Law calibration."""
    x: int
    y: int
    width: int
    height: int
    color: str = 'red'

    @property
    def center(self) -> Tuple[int, int]:
        """Get target center."""
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class FittsTrialResult:
    """Result from a single Fitts's Law trial."""
    trial_number: int
    target_size: int
    target_distance: int
    movement_time_ms: float
    hit: bool
    click_position: Tuple[int, int]
    target_position: Tuple[int, int]
    index_of_difficulty: float
    events: List[Dict]


@dataclass
class TypingTrialResult:
    """Result from a single typing trial."""
    passage: str
    typed_text: str
    wpm: float
    errors: int
    accuracy: float
    total_time_sec: float
    events: List[Dict]


class CalibrationExercises:
    """
    Guided exercises to capture personal behavioral patterns.

    Exercises:
        - Fitts's Law Test: Click targets at various sizes/distances
        - Typing Test: Type displayed passages
        - Scroll Test: Scroll through content
        - Free Form: General usage recording

    Each exercise captures data under controlled conditions
    for accurate profile generation.
    """

    def __init__(
        self,
        mouse_recorder: Optional[Any] = None,
        keyboard_recorder: Optional[Any] = None,
        display: Optional[Any] = None,
        output_dir: str = "recordings/calibration"
    ):
        """
        Initialize calibration exercises.

        Args:
            mouse_recorder: MouseRecorder instance
            keyboard_recorder: KeyboardRecorder instance
            display: Display interface for showing exercises
            output_dir: Directory to save calibration data
        """
        self.mouse_recorder = mouse_recorder
        self.keyboard_recorder = keyboard_recorder
        self.display = display
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Callbacks
        self.on_trial_complete: Optional[Callable[[Dict], None]] = None
        self.on_exercise_complete: Optional[Callable[[str, Dict], None]] = None

    def run_fitts_law_test(
        self,
        num_trials: int = 50,
        target_sizes: Optional[List[int]] = None,
        distances: Optional[List[int]] = None,
        screen_width: int = 1920,
        screen_height: int = 1080
    ) -> List[FittsTrialResult]:
        """
        Run Fitts's Law calibration.

        Displays targets at various sizes and distances.
        User clicks each target as quickly and accurately as possible.

        Args:
            num_trials: Number of trials to run
            target_sizes: List of target widths in pixels
            distances: List of target distances in pixels
            screen_width: Screen width
            screen_height: Screen height

        Returns:
            List of trial results
        """
        if target_sizes is None:
            target_sizes = [10, 20, 40, 80]
        if distances is None:
            distances = [100, 200, 400, 800]

        results = []
        center_x = screen_width // 2
        center_y = screen_height // 2

        logger.info(f"Starting Fitts's Law calibration: {num_trials} trials")

        for trial in range(num_trials):
            # Random target size and position
            size = random.choice(target_sizes)
            distance = random.choice(distances)
            angle = random.uniform(0, 2 * math.pi)

            # Calculate target position
            target_x = int(center_x + distance * math.cos(angle))
            target_y = int(center_y + distance * math.sin(angle))

            # Clamp to screen bounds
            target_x = max(size, min(screen_width - size, target_x))
            target_y = max(size, min(screen_height - size, target_y))

            target = CalibrationTarget(
                x=target_x - size // 2,
                y=target_y - size // 2,
                width=size,
                height=size
            )

            # Show start position if display available
            if self.display:
                self.display.show_target(center_x, center_y, 20, color='green')
                self.display.show_message(f"Click green dot (Trial {trial + 1}/{num_trials})")
                start_click = self.display.wait_for_click()
            else:
                start_click = (center_x, center_y)
                time.sleep(0.5)

            # Show target
            start_time = time.time()

            if self.display:
                self.display.clear()
                self.display.show_target(target_x, target_y, size, color='red')

            # Record movement
            if self.mouse_recorder:
                self.mouse_recorder.start_recording()

            # Wait for click
            if self.display:
                end_click = self.display.wait_for_click()
            else:
                # Simulate wait
                time.sleep(random.uniform(0.2, 1.0))
                end_click = (target_x + random.randint(-size//2, size//2),
                            target_y + random.randint(-size//2, size//2))

            end_time = time.time()

            # Get events
            events = []
            if self.mouse_recorder:
                events = [e.to_dict() for e in self.mouse_recorder.stop_recording()]

            # Calculate results
            movement_time = (end_time - start_time) * 1000  # ms
            click_distance = math.sqrt(
                (end_click[0] - target_x)**2 +
                (end_click[1] - target_y)**2
            )
            hit = click_distance <= size / 2
            id_value = math.log2(distance / size + 1)

            result = FittsTrialResult(
                trial_number=trial,
                target_size=size,
                target_distance=distance,
                movement_time_ms=movement_time,
                hit=hit,
                click_position=end_click,
                target_position=(target_x, target_y),
                index_of_difficulty=id_value,
                events=events
            )
            results.append(result)

            if self.on_trial_complete:
                self.on_trial_complete({'type': 'fitts', 'trial': result})

            # Brief pause between trials
            time.sleep(0.3)

        # Save results
        self._save_fitts_results(results)

        if self.on_exercise_complete:
            self.on_exercise_complete('fitts_law', {'trials': len(results)})

        logger.info(f"Fitts's Law calibration complete: {len(results)} trials")

        return results

    def run_typing_test(
        self,
        passages: Optional[List[str]] = None,
        num_passages: int = 10
    ) -> List[TypingTrialResult]:
        """
        Run typing calibration.

        User types displayed text passages.
        Captures typing rhythm and patterns.

        Args:
            passages: List of passages to type
            num_passages: Number of passages if not provided

        Returns:
            List of trial results
        """
        if passages is None:
            passages = self._get_default_passages()

        # Limit to requested number
        passages = passages[:num_passages]

        results = []

        logger.info(f"Starting typing calibration: {len(passages)} passages")

        for i, passage in enumerate(passages):
            if self.display:
                self.display.show_typing_prompt(passage, f"Passage {i + 1}/{len(passages)}")

            # Start recording
            if self.keyboard_recorder:
                self.keyboard_recorder.start_recording()

            start_time = time.time()

            # Wait for typing
            if self.display:
                typed_text = self.display.wait_for_typing(len(passage))
            else:
                # Simulate typing
                time.sleep(len(passage) * 0.1)
                typed_text = passage

            end_time = time.time()

            # Get events
            events = []
            if self.keyboard_recorder:
                events = [e.to_dict() for e in self.keyboard_recorder.stop_recording()]

            # Calculate metrics
            total_time = end_time - start_time
            words = len(passage.split())
            wpm = (words / total_time) * 60 if total_time > 0 else 0

            # Count errors (backspaces)
            errors = sum(1 for e in events if e.get('key') == 'backspace')

            # Calculate accuracy
            correct_chars = sum(1 for a, b in zip(typed_text, passage) if a == b)
            accuracy = correct_chars / len(passage) if passage else 1.0

            result = TypingTrialResult(
                passage=passage,
                typed_text=typed_text,
                wpm=wpm,
                errors=errors,
                accuracy=accuracy,
                total_time_sec=total_time,
                events=events
            )
            results.append(result)

            if self.on_trial_complete:
                self.on_trial_complete({'type': 'typing', 'trial': result})

            # Brief pause between passages
            time.sleep(0.5)

        # Save results
        self._save_typing_results(results)

        if self.on_exercise_complete:
            self.on_exercise_complete('typing', {'trials': len(results)})

        logger.info(f"Typing calibration complete: {len(results)} passages")

        return results

    def run_scroll_test(
        self,
        duration_sec: float = 60,
        content_length: int = 5000
    ) -> Dict[str, Any]:
        """
        Run scroll behavior calibration.

        User scrolls through content naturally.

        Args:
            duration_sec: Duration of test in seconds
            content_length: Length of scrollable content

        Returns:
            Scroll test results
        """
        logger.info(f"Starting scroll calibration: {duration_sec}s")

        if self.display:
            self.display.show_scrollable_content(content_length)
            self.display.show_message("Scroll through the content naturally. Press ESC when done.")

        if self.mouse_recorder:
            self.mouse_recorder.start_recording()

        start_time = time.time()

        # Wait for duration or ESC
        if self.display:
            self.display.wait_for_key('escape', timeout=duration_sec)
        else:
            time.sleep(duration_sec)

        end_time = time.time()

        events = []
        if self.mouse_recorder:
            events = [e.to_dict() for e in self.mouse_recorder.stop_recording()]

        # Analyze scroll events
        scroll_events = [e for e in events if e.get('event_type') == 'scroll']

        results = {
            'duration_sec': end_time - start_time,
            'total_scrolls': len(scroll_events),
            'events': events
        }

        # Save results
        self._save_scroll_results(results)

        if self.on_exercise_complete:
            self.on_exercise_complete('scroll', results)

        logger.info(f"Scroll calibration complete: {len(scroll_events)} scroll events")

        return results

    def run_full_calibration(self) -> Dict[str, Any]:
        """
        Run complete calibration suite.

        Returns:
            Combined results from all exercises
        """
        logger.info("Starting full calibration suite")

        results = {
            'timestamp': time.time(),
            'fitts_law': None,
            'typing': None,
            'scroll': None
        }

        # Show instructions
        if self.display:
            self.display.show_instructions("""
FULL CALIBRATION SUITE

This will capture your personal behavioral patterns through:
1. Fitts's Law Test (~5 min) - Click targets
2. Typing Test (~5 min) - Type passages
3. Scroll Test (~2 min) - Scroll through content

Type naturally and move the mouse as you normally would.
Don't try to be fast or slow - just be yourself.

Press SPACE to begin.
            """)
            self.display.wait_for_key('space')

        # Run each test
        try:
            fitts_results = self.run_fitts_law_test()
            results['fitts_law'] = [
                {
                    'size': r.target_size,
                    'distance': r.target_distance,
                    'time_ms': r.movement_time_ms,
                    'id': r.index_of_difficulty,
                    'hit': r.hit
                }
                for r in fitts_results
            ]
        except Exception as e:
            logger.error(f"Fitts's Law test failed: {e}")

        try:
            typing_results = self.run_typing_test()
            results['typing'] = [
                {
                    'wpm': r.wpm,
                    'errors': r.errors,
                    'accuracy': r.accuracy,
                    'time_sec': r.total_time_sec
                }
                for r in typing_results
            ]
        except Exception as e:
            logger.error(f"Typing test failed: {e}")

        try:
            scroll_results = self.run_scroll_test(duration_sec=60)
            results['scroll'] = {
                'duration': scroll_results['duration_sec'],
                'scroll_count': scroll_results['total_scrolls']
            }
        except Exception as e:
            logger.error(f"Scroll test failed: {e}")

        # Save combined results
        output_path = self.output_dir / f"full_calibration_{int(time.time())}.json"
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        logger.info(f"Full calibration complete. Saved to {output_path}")

        return results

    def _get_default_passages(self) -> List[str]:
        """Get default typing passages."""
        return [
            "The quick brown fox jumps over the lazy dog.",
            "Pack my box with five dozen liquor jugs.",
            "How vexingly quick daft zebras jump!",
            "The five boxing wizards jump quickly.",
            "Sphinx of black quartz, judge my vow.",
            "I need to send an email to the team about tomorrow's meeting.",
            "Please review the attached document and let me know your thoughts.",
            "Thanks for your help with the project last week.",
            "The weather forecast shows rain expected later today.",
            "Can you schedule a call for next Tuesday afternoon?",
            "I'll be working from home tomorrow if that's okay.",
            "The new software update includes several bug fixes.",
            "Please make sure to save your work before closing.",
            "The meeting has been moved to conference room B.",
            "Let me know if you have any questions about the proposal.",
        ]

    def _save_fitts_results(self, results: List[FittsTrialResult]) -> None:
        """Save Fitts's Law results."""
        output_path = self.output_dir / f"fitts_law_{int(time.time())}.jsonl"

        with open(output_path, 'w') as f:
            for result in results:
                data = {
                    'trial': result.trial_number,
                    'target_size': result.target_size,
                    'target_distance': result.target_distance,
                    'movement_time_ms': result.movement_time_ms,
                    'hit': result.hit,
                    'id': result.index_of_difficulty,
                    'click_position': result.click_position,
                    'target_position': result.target_position
                }
                f.write(json.dumps(data) + '\n')

        # Also save raw events
        events_path = self.output_dir / f"fitts_law_{int(time.time())}_events.jsonl"
        with open(events_path, 'w') as f:
            for result in results:
                for event in result.events:
                    event['trial'] = result.trial_number
                    f.write(json.dumps(event) + '\n')

    def _save_typing_results(self, results: List[TypingTrialResult]) -> None:
        """Save typing test results."""
        output_path = self.output_dir / f"typing_test_{int(time.time())}.jsonl"

        with open(output_path, 'w') as f:
            for i, result in enumerate(results):
                data = {
                    'trial': i,
                    'passage': result.passage,
                    'typed': result.typed_text,
                    'wpm': result.wpm,
                    'errors': result.errors,
                    'accuracy': result.accuracy,
                    'time_sec': result.total_time_sec
                }
                f.write(json.dumps(data) + '\n')

        # Save raw events
        events_path = self.output_dir / f"typing_test_{int(time.time())}_events.jsonl"
        with open(events_path, 'w') as f:
            for i, result in enumerate(results):
                for event in result.events:
                    event['trial'] = i
                    f.write(json.dumps(event) + '\n')

    def _save_scroll_results(self, results: Dict[str, Any]) -> None:
        """Save scroll test results."""
        output_path = self.output_dir / f"scroll_test_{int(time.time())}.json"

        # Separate events for size
        events = results.pop('events', [])
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)

        events_path = self.output_dir / f"scroll_test_{int(time.time())}_events.jsonl"
        with open(events_path, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')


class CalibrationDisplay:
    """
    Display interface for calibration exercises.

    Can be implemented with pygame, tkinter, or any GUI framework.
    This is an abstract interface - implement for your display system.
    """

    def show_target(self, x: int, y: int, size: int, color: str = 'red') -> None:
        """Show a target at position."""
        raise NotImplementedError

    def show_message(self, message: str) -> None:
        """Show a message to the user."""
        raise NotImplementedError

    def show_instructions(self, text: str) -> None:
        """Show instruction text."""
        raise NotImplementedError

    def show_typing_prompt(self, text: str, title: str = "") -> None:
        """Show text to type."""
        raise NotImplementedError

    def show_scrollable_content(self, length: int) -> None:
        """Show scrollable content."""
        raise NotImplementedError

    def clear(self) -> None:
        """Clear the display."""
        raise NotImplementedError

    def wait_for_click(self) -> Tuple[int, int]:
        """Wait for mouse click, return position."""
        raise NotImplementedError

    def wait_for_key(self, key: str, timeout: Optional[float] = None) -> bool:
        """Wait for specific key press."""
        raise NotImplementedError

    def wait_for_typing(self, expected_length: int) -> str:
        """Wait for typing to complete."""
        raise NotImplementedError
