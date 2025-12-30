#!/usr/bin/env python3
"""
Test suite for human-like mouse movement.
"""

import sys
import math
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from input.human_mouse import HumanMouse, MouseConfig, BezierCurve


class TestBezierCurve:
    """Tests for Bezier curve generation."""

    def test_quadratic_endpoints(self):
        """Test that quadratic curve starts and ends at correct points."""
        p0 = (0.0, 0.0)
        p1 = (50.0, 100.0)
        p2 = (100.0, 0.0)

        start = BezierCurve.quadratic(p0, p1, p2, 0.0)
        end = BezierCurve.quadratic(p0, p1, p2, 1.0)

        assert start == p0
        assert end == p2

    def test_cubic_endpoints(self):
        """Test that cubic curve starts and ends at correct points."""
        p0 = (0.0, 0.0)
        p1 = (25.0, 100.0)
        p2 = (75.0, 100.0)
        p3 = (100.0, 0.0)

        start = BezierCurve.cubic(p0, p1, p2, p3, 0.0)
        end = BezierCurve.cubic(p0, p1, p2, p3, 1.0)

        assert start == p0
        assert end == p3

    def test_quadratic_midpoint(self):
        """Test that quadratic curve passes near control point."""
        p0 = (0.0, 0.0)
        p1 = (50.0, 100.0)
        p2 = (100.0, 0.0)

        mid = BezierCurve.quadratic(p0, p1, p2, 0.5)

        # Midpoint should be influenced by control point
        assert mid[1] > 0  # Y should be positive (curved up)


class TestHumanMouse:
    """Tests for HumanMouse class."""

    @pytest.fixture
    def mouse(self):
        """Create a mouse instance for testing."""
        return HumanMouse(dry_run=True)

    def test_position_tracking(self, mouse):
        """Test that position is tracked correctly."""
        mouse.set_position(100, 200)
        assert mouse.position == (100, 200)

    def test_calculate_duration_short_distance(self, mouse):
        """Test duration calculation for short distances."""
        duration = mouse.calculate_duration((0, 0), (10, 10))
        # Short distance should still have minimum duration
        assert duration >= mouse.config.min_duration_ms / 1000

    def test_calculate_duration_long_distance(self, mouse):
        """Test duration calculation for long distances."""
        duration = mouse.calculate_duration((0, 0), (1000, 1000))
        # Long distance should take longer
        assert duration >= mouse.config.min_duration_ms / 1000
        assert duration <= mouse.config.max_duration_ms / 1000

    def test_calculate_duration_fitts_law(self, mouse):
        """Test that Fitts's Law is applied (harder targets take longer)."""
        # Same distance, different target widths
        duration_small = mouse.calculate_duration((0, 0), (500, 0), target_width=10)
        duration_large = mouse.calculate_duration((0, 0), (500, 0), target_width=100)

        # Smaller targets should take longer
        assert duration_small >= duration_large

    def test_generate_control_points_count(self, mouse):
        """Test that control points are generated correctly."""
        points = mouse.generate_control_points((0, 0), (500, 500))

        # Should have at least start and end
        assert len(points) >= 2
        assert points[0] == (0, 0)
        assert points[-1] == (500, 500)

    def test_generate_trajectory_reaches_target(self, mouse):
        """Test that trajectory ends at target."""
        trajectory = mouse.generate_trajectory((0, 0), (500, 300))

        # Last point should be at or very near target
        last_x, last_y, _ = trajectory[-1]
        distance = math.hypot(last_x - 500, last_y - 300)
        assert distance < 20  # Within 20 pixels (accounting for overshoot correction)

    def test_generate_trajectory_has_multiple_points(self, mouse):
        """Test that trajectory has many points for smooth movement."""
        trajectory = mouse.generate_trajectory((0, 0), (500, 300))

        # Should have many points for smooth movement
        assert len(trajectory) >= 10

    def test_generate_trajectory_timestamps_increasing(self, mouse):
        """Test that timestamps are monotonically increasing."""
        trajectory = mouse.generate_trajectory((0, 0), (500, 300))

        for i in range(1, len(trajectory)):
            assert trajectory[i][2] >= trajectory[i-1][2]

    def test_plan_trajectory_returns_coordinates(self, mouse):
        """Test plan_trajectory returns list of coordinate tuples."""
        trajectory = mouse.plan_trajectory((0, 0), (500, 300))

        assert len(trajectory) > 0
        assert all(len(p) == 2 for p in trajectory)
        assert all(isinstance(p[0], int) and isinstance(p[1], int) for p in trajectory)


class TestMouseConfig:
    """Tests for MouseConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = MouseConfig()

        assert config.min_duration_ms > 0
        assert config.max_duration_ms > config.min_duration_ms
        assert 0 <= config.overshoot_probability <= 1
        assert config.jitter_pixels >= 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = MouseConfig(
            min_duration_ms=50,
            max_duration_ms=500,
            overshoot_probability=0.5,
            jitter_pixels=5
        )

        assert config.min_duration_ms == 50
        assert config.max_duration_ms == 500
        assert config.overshoot_probability == 0.5
        assert config.jitter_pixels == 5


class TestHumanMouseIntegration:
    """Integration tests for HumanMouse."""

    def test_full_movement_dry_run(self):
        """Test full movement in dry run mode."""
        mouse = HumanMouse(dry_run=True)
        mouse.set_position(0, 0)

        mouse.move_to(500, 300)

        # Position should be updated
        assert mouse.position == (500, 300)

    def test_click_dry_run(self):
        """Test clicking in dry run mode."""
        mouse = HumanMouse(dry_run=True)
        mouse.click()  # Should not raise

    def test_scroll_dry_run(self):
        """Test scrolling in dry run mode."""
        mouse = HumanMouse(dry_run=True)
        mouse.scroll(100, direction='down')  # Should not raise


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
