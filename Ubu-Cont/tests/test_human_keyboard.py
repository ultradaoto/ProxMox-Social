#!/usr/bin/env python3
"""
Test suite for human-like keyboard input.
"""

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from input.human_keyboard import HumanKeyboard, KeyboardConfig, QWERTY_NEIGHBORS


class TestQwertyNeighbors:
    """Tests for QWERTY keyboard neighbor mappings."""

    def test_all_letters_have_neighbors(self):
        """Test that all letters have neighbor mappings."""
        for char in 'abcdefghijklmnopqrstuvwxyz':
            assert char in QWERTY_NEIGHBORS
            assert len(QWERTY_NEIGHBORS[char]) > 0

    def test_neighbors_are_adjacent(self):
        """Test some specific neighbor relationships."""
        assert 's' in QWERTY_NEIGHBORS['a']
        assert 'w' in QWERTY_NEIGHBORS['q']
        assert 'l' in QWERTY_NEIGHBORS['k']


class TestKeyboardConfig:
    """Tests for KeyboardConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = KeyboardConfig()

        assert config.base_wpm > 0
        assert config.wpm_variance >= 0
        assert 0 <= config.typo_rate <= 1
        assert len(config.burst_words) > 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = KeyboardConfig(
            base_wpm=60,
            wpm_variance=5,
            typo_rate=0.05
        )

        assert config.base_wpm == 60
        assert config.wpm_variance == 5
        assert config.typo_rate == 0.05


class TestHumanKeyboard:
    """Tests for HumanKeyboard class."""

    @pytest.fixture
    def keyboard(self):
        """Create a keyboard instance for testing."""
        return HumanKeyboard(dry_run=True)

    def test_keystroke_delay_positive(self, keyboard):
        """Test that keystroke delays are positive."""
        delay = keyboard._calculate_keystroke_delay('a')
        assert delay > 0

    def test_keystroke_delay_varies(self, keyboard):
        """Test that keystroke delays have variation."""
        delays = [keyboard._calculate_keystroke_delay('a') for _ in range(10)]

        # Should have some variation
        assert len(set(delays)) > 1

    def test_different_hands_detection(self, keyboard):
        """Test detection of different-hand transitions."""
        # 'a' is left hand, 'k' is right hand
        assert keyboard._different_hands('a', 'k')
        assert keyboard._different_hands('f', 'j')

        # Same hand
        assert not keyboard._different_hands('a', 's')
        assert not keyboard._different_hands('j', 'k')

    def test_same_finger_detection(self, keyboard):
        """Test detection of same-finger sequences."""
        # Same finger (vertical on keyboard)
        assert keyboard._same_finger('e', 'd')
        assert keyboard._same_finger('r', 'f')

        # Different fingers
        assert not keyboard._same_finger('a', 's')

    def test_typo_generation_returns_adjacent(self, keyboard):
        """Test that typos return adjacent keys."""
        keyboard.config.typo_rate = 1.0  # Always generate typo

        typos = []
        for _ in range(50):
            typo = keyboard._generate_typo('a')
            if typo and typo != 'a':
                typos.append(typo)

        # All typos should be neighbors of 'a'
        for typo in typos:
            assert typo.lower() in QWERTY_NEIGHBORS['a'] or typo.lower() == 'a'


class TestHumanKeyboardIntegration:
    """Integration tests for HumanKeyboard."""

    def test_type_text_dry_run(self):
        """Test typing text in dry run mode."""
        keyboard = HumanKeyboard(dry_run=True)
        keyboard.type_text("hello world")  # Should not raise

    def test_type_text_no_typos(self):
        """Test typing without typos."""
        config = KeyboardConfig(typo_rate=0)
        keyboard = HumanKeyboard(config=config, dry_run=True)
        keyboard.type_text("test")  # Should not raise

    def test_hotkey_dry_run(self):
        """Test hotkey in dry run mode."""
        keyboard = HumanKeyboard(dry_run=True)
        keyboard.hotkey('ctrl', 'c')  # Should not raise

    def test_special_keys(self):
        """Test special key methods."""
        keyboard = HumanKeyboard(dry_run=True)

        keyboard.enter()
        keyboard.tab()
        keyboard.escape()
        keyboard.backspace()
        keyboard.delete()


class TestTypingSpeed:
    """Tests for typing speed calculations."""

    def test_burst_words_faster(self):
        """Test that burst words are typed faster."""
        config = KeyboardConfig(burst_words=['the'])
        keyboard = HumanKeyboard(config=config, dry_run=True)

        burst_delays = []
        normal_delays = []

        for _ in range(20):
            burst_delays.append(
                keyboard._calculate_keystroke_delay('t', in_burst=True)
            )
            normal_delays.append(
                keyboard._calculate_keystroke_delay('t', in_burst=False)
            )

        # Burst typing should be faster on average
        assert sum(burst_delays) / len(burst_delays) < sum(normal_delays) / len(normal_delays)

    def test_uppercase_slower(self):
        """Test that uppercase letters take longer (shift key)."""
        keyboard = HumanKeyboard(dry_run=True)

        lower_delays = [keyboard._calculate_keystroke_delay('a') for _ in range(20)]
        upper_delays = [keyboard._calculate_keystroke_delay('A') for _ in range(20)]

        # Uppercase should be slower on average
        avg_lower = sum(lower_delays) / len(lower_delays)
        avg_upper = sum(upper_delays) / len(upper_delays)
        assert avg_upper > avg_lower


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
