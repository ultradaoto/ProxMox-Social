"""
Human-Like Keyboard Input

Simulates realistic human typing with:
- Variable WPM based on text complexity
- Natural typos and corrections
- Pauses between words and sentences
- Burst typing for common words
"""

import random
import time
import logging
import re
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class KeyboardConfig:
    """Keyboard behavior configuration."""
    base_wpm: int = 45
    wpm_variance: int = 10
    typo_rate: float = 0.02
    correction_delay_ms: float = 200.0
    word_pause_min_ms: float = 50.0
    word_pause_max_ms: float = 200.0
    sentence_pause_min_ms: float = 200.0
    sentence_pause_max_ms: float = 600.0
    burst_words: List[str] = field(default_factory=lambda: [
        'the', 'and', 'is', 'to', 'in', 'a', 'of', 'for', 'it', 'be'
    ])


# Common typo patterns (adjacent keys on QWERTY)
QWERTY_NEIGHBORS = {
    'a': ['s', 'q', 'z', 'w'],
    'b': ['v', 'n', 'g', 'h'],
    'c': ['x', 'v', 'd', 'f'],
    'd': ['s', 'f', 'e', 'r', 'c', 'x'],
    'e': ['w', 'r', 'd', 's'],
    'f': ['d', 'g', 'r', 't', 'v', 'c'],
    'g': ['f', 'h', 't', 'y', 'b', 'v'],
    'h': ['g', 'j', 'y', 'u', 'n', 'b'],
    'i': ['u', 'o', 'k', 'j'],
    'j': ['h', 'k', 'u', 'i', 'm', 'n'],
    'k': ['j', 'l', 'i', 'o', 'm'],
    'l': ['k', 'o', 'p'],
    'm': ['n', 'j', 'k'],
    'n': ['b', 'm', 'h', 'j'],
    'o': ['i', 'p', 'l', 'k'],
    'p': ['o', 'l'],
    'q': ['w', 'a'],
    'r': ['e', 't', 'f', 'd'],
    's': ['a', 'd', 'w', 'e', 'z', 'x'],
    't': ['r', 'y', 'g', 'f'],
    'u': ['y', 'i', 'j', 'h'],
    'v': ['c', 'b', 'f', 'g'],
    'w': ['q', 'e', 'a', 's'],
    'x': ['z', 'c', 's', 'd'],
    'y': ['t', 'u', 'h', 'g'],
    'z': ['a', 'x', 's'],
}


class HumanKeyboard:
    """
    Simulates human-like keyboard input.

    Uses timing patterns and error models based on typing research.
    """

    def __init__(
        self,
        config: KeyboardConfig = None,
        dry_run: bool = False
    ):
        """
        Initialize human keyboard.

        Args:
            config: Keyboard behavior configuration
            dry_run: If True, don't actually send commands
        """
        self.config = config or KeyboardConfig()
        self.dry_run = dry_run
        self._sender = None

        # Track modifier state
        self._shift_held = False
        self._ctrl_held = False
        self._alt_held = False

    def set_sender(self, sender) -> None:
        """Set the remote sender for actual keyboard control."""
        self._sender = sender

    def _calculate_keystroke_delay(
        self,
        char: str,
        prev_char: str = None,
        in_burst: bool = False
    ) -> float:
        """
        Calculate delay before keystroke.

        Args:
            char: Current character
            prev_char: Previous character
            in_burst: Whether typing a common/burst word

        Returns:
            Delay in seconds
        """
        # Base delay from WPM (5 chars per word average)
        wpm = self.config.base_wpm + random.randint(
            -self.config.wpm_variance,
            self.config.wpm_variance
        )
        base_delay = 60.0 / (wpm * 5)

        # Faster for burst words
        if in_burst:
            base_delay *= 0.7

        # Adjust for character type
        if char.isupper():
            base_delay *= 1.2  # Shift takes time
        elif char.isdigit():
            base_delay *= 1.3  # Number row is harder
        elif char in '!@#$%^&*()':
            base_delay *= 1.5  # Special characters

        # Hand transitions
        if prev_char and self._different_hands(prev_char, char):
            base_delay *= 0.9  # Alternating hands is faster

        # Same finger repetition
        if prev_char and self._same_finger(prev_char, char):
            base_delay *= 1.4  # Same finger is slower

        # Add random variation
        base_delay *= random.uniform(0.7, 1.3)

        return base_delay

    def _different_hands(self, char1: str, char2: str) -> bool:
        """Check if characters are typed with different hands."""
        left_hand = set('qwertasdfgzxcvb12345`~!@#$%')
        c1_left = char1.lower() in left_hand
        c2_left = char2.lower() in left_hand
        return c1_left != c2_left

    def _same_finger(self, char1: str, char2: str) -> bool:
        """Check if characters use the same finger."""
        finger_groups = [
            'qaz1!',
            'wsx2@',
            'edc3#',
            'rfv4$tgb5%',
            'yhn6^ujm7&',
            'ik8*',
            'ol9(',
            'p0)-=',
        ]
        for group in finger_groups:
            if char1.lower() in group and char2.lower() in group:
                return True
        return False

    def _generate_typo(self, char: str) -> Optional[str]:
        """
        Generate a realistic typo for a character.

        Returns:
            Typo character or None if no typo
        """
        if random.random() > self.config.typo_rate:
            return None

        char_lower = char.lower()

        # Use adjacent key
        if char_lower in QWERTY_NEIGHBORS:
            neighbors = QWERTY_NEIGHBORS[char_lower]
            typo = random.choice(neighbors)

            # Preserve case
            if char.isupper():
                typo = typo.upper()
            return typo

        # Double keystroke
        if random.random() < 0.3:
            return char

        return None

    def type_text(
        self,
        text: str,
        wpm: int = None,
        make_typos: bool = True
    ) -> None:
        """
        Type text with human-like timing and errors.

        Args:
            text: Text to type
            wpm: Words per minute (uses config if None)
            make_typos: Whether to simulate typos
        """
        if not text:
            return

        if wpm:
            original_wpm = self.config.base_wpm
            self.config.base_wpm = wpm

        try:
            self._type_text_internal(text, make_typos)
        finally:
            if wpm:
                self.config.base_wpm = original_wpm

    def _type_text_internal(self, text: str, make_typos: bool) -> None:
        """Internal text typing implementation."""
        words = text.split()
        prev_char = None

        for i, word in enumerate(words):
            # Check if this is a burst word
            is_burst = word.lower().strip('.,!?;:') in self.config.burst_words

            # Type each character
            for j, char in enumerate(word):
                # Generate potential typo
                typo = None
                if make_typos:
                    typo = self._generate_typo(char)

                if typo:
                    # Type the wrong key
                    delay = self._calculate_keystroke_delay(typo, prev_char, is_burst)
                    time.sleep(delay)
                    self._press_key(typo)
                    prev_char = typo

                    # Pause before noticing error
                    pause = random.uniform(0.1, 0.3)
                    time.sleep(pause)

                    # Backspace to correct
                    time.sleep(self.config.correction_delay_ms / 1000)
                    self._press_key('backspace')

                # Type correct character
                delay = self._calculate_keystroke_delay(char, prev_char, is_burst)
                time.sleep(delay)
                self._press_key(char)
                prev_char = char

            # Space between words (except last)
            if i < len(words) - 1:
                delay = random.uniform(
                    self.config.word_pause_min_ms / 1000,
                    self.config.word_pause_max_ms / 1000
                )
                time.sleep(delay)
                self._press_key('space')
                prev_char = ' '

        # Sentence end pause
        if text and text[-1] in '.!?':
            pause = random.uniform(
                self.config.sentence_pause_min_ms / 1000,
                self.config.sentence_pause_max_ms / 1000
            )
            time.sleep(pause)

    def _press_key(self, key: str) -> None:
        """Press a single key."""
        if self.dry_run:
            logger.debug(f"Would press: {key}")
            return

        if self._sender:
            self._sender.send_key(key, 'press')

    def press_key(self, key: str) -> None:
        """
        Press a key (public method).

        Args:
            key: Key to press ('a', 'enter', 'backspace', etc.)
        """
        self._press_key(key)

    def key_down(self, key: str) -> None:
        """Hold a key down."""
        if not self.dry_run and self._sender:
            self._sender.send_key(key, 'down')

    def key_up(self, key: str) -> None:
        """Release a key."""
        if not self.dry_run and self._sender:
            self._sender.send_key(key, 'up')

    def hotkey(self, *keys: str) -> None:
        """
        Press a key combination.

        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')
        """
        # Press all keys down
        for key in keys:
            self.key_down(key)
            time.sleep(random.uniform(0.02, 0.05))

        # Brief hold
        time.sleep(random.uniform(0.05, 0.1))

        # Release in reverse order
        for key in reversed(keys):
            self.key_up(key)
            time.sleep(random.uniform(0.02, 0.05))

    def type_slowly(self, text: str, wpm: int = 20) -> None:
        """Type text slowly (for passwords, important fields)."""
        self.type_text(text, wpm=wpm, make_typos=False)

    def paste(self, text: str = None) -> None:
        """
        Simulate paste operation.

        Args:
            text: Text to paste (if supported by sender)
        """
        self.hotkey('ctrl', 'v')

    def copy(self) -> None:
        """Simulate copy operation."""
        self.hotkey('ctrl', 'c')

    def select_all(self) -> None:
        """Select all text."""
        self.hotkey('ctrl', 'a')

    def undo(self) -> None:
        """Undo last action."""
        self.hotkey('ctrl', 'z')

    def enter(self) -> None:
        """Press Enter key."""
        self.press_key('enter')

    def tab(self) -> None:
        """Press Tab key."""
        self.press_key('tab')

    def escape(self) -> None:
        """Press Escape key."""
        self.press_key('escape')

    def backspace(self, count: int = 1) -> None:
        """Press Backspace key."""
        for _ in range(count):
            self.press_key('backspace')
            time.sleep(random.uniform(0.03, 0.08))

    def delete(self, count: int = 1) -> None:
        """Press Delete key."""
        for _ in range(count):
            self.press_key('delete')
            time.sleep(random.uniform(0.03, 0.08))

    def arrow_key(self, direction: str, count: int = 1) -> None:
        """
        Press arrow key.

        Args:
            direction: 'up', 'down', 'left', 'right'
            count: Number of times to press
        """
        for _ in range(count):
            self.press_key(direction)
            time.sleep(random.uniform(0.05, 0.1))
