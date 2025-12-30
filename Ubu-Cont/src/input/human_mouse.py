"""
Human-Like Mouse Movement

Generates realistic mouse trajectories using:
- Bezier curves for natural paths
- Fitts's Law for movement timing
- Micro-jitter simulating muscle tremor
- Overshoot and correction near targets
"""

import math
import random
import time
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MouseConfig:
    """Mouse behavior configuration."""
    min_duration_ms: float = 100.0
    max_duration_ms: float = 800.0
    overshoot_probability: float = 0.15
    overshoot_distance: int = 10
    jitter_pixels: int = 3
    fitts_law_a: float = 50.0  # Intercept (reaction time)
    fitts_law_b: float = 150.0  # Slope (movement difficulty)
    points_per_second: int = 60  # Trajectory resolution


class BezierCurve:
    """Generates Bezier curve trajectories."""

    @staticmethod
    def quadratic(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        t: float
    ) -> Tuple[float, float]:
        """Calculate point on quadratic Bezier curve."""
        x = (1-t)**2 * p0[0] + 2*(1-t)*t * p1[0] + t**2 * p2[0]
        y = (1-t)**2 * p0[1] + 2*(1-t)*t * p1[1] + t**2 * p2[1]
        return (x, y)

    @staticmethod
    def cubic(
        p0: Tuple[float, float],
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        t: float
    ) -> Tuple[float, float]:
        """Calculate point on cubic Bezier curve."""
        x = (1-t)**3 * p0[0] + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]
        y = (1-t)**3 * p0[1] + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]
        return (x, y)


class HumanMouse:
    """
    Generates human-like mouse movements.

    Uses a combination of Bezier curves, Fitts's Law timing,
    and random perturbations to simulate natural human movement.
    """

    def __init__(
        self,
        config: MouseConfig = None,
        dry_run: bool = False
    ):
        """
        Initialize human mouse.

        Args:
            config: Mouse behavior configuration
            dry_run: If True, don't actually send commands
        """
        self.config = config or MouseConfig()
        self.dry_run = dry_run

        self._current_x = 960  # Assume 1920x1080 center
        self._current_y = 540
        self._sender = None

    def set_sender(self, sender) -> None:
        """Set the remote sender for actual mouse control."""
        self._sender = sender

    def set_position(self, x: int, y: int) -> None:
        """Set current mouse position (for tracking)."""
        self._current_x = x
        self._current_y = y

    @property
    def position(self) -> Tuple[int, int]:
        """Get current position."""
        return (self._current_x, self._current_y)

    def calculate_duration(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        target_width: int = 50
    ) -> float:
        """
        Calculate movement duration using Fitts's Law.

        Fitts's Law: MT = a + b * log2(D/W + 1)
        Where:
            MT = movement time
            D = distance to target
            W = width of target
            a, b = empirical constants

        Args:
            start: Starting position
            end: Target position
            target_width: Width of target element

        Returns:
            Duration in seconds
        """
        distance = math.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)

        if distance < 1:
            return 0.0

        # Fitts's Law calculation
        index_of_difficulty = math.log2(distance / target_width + 1)
        duration_ms = self.config.fitts_law_a + self.config.fitts_law_b * index_of_difficulty

        # Add random variation (±20%)
        duration_ms *= random.uniform(0.8, 1.2)

        # Clamp to configured range
        duration_ms = max(self.config.min_duration_ms,
                         min(self.config.max_duration_ms, duration_ms))

        return duration_ms / 1000.0

    def generate_control_points(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int]
    ) -> List[Tuple[float, float]]:
        """
        Generate Bezier control points for natural curve.

        The control points create an arc that simulates
        natural arm movement mechanics.

        Args:
            start: Starting position
            end: Target position

        Returns:
            List of control points [start, ctrl1, ctrl2, end]
        """
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = math.sqrt(dx**2 + dy**2)

        if distance < 10:
            # Very short movement, use simple path
            return [start, end]

        # Calculate perpendicular offset for curve
        # Movements tend to arc slightly based on arm mechanics
        perp_x = -dy / distance
        perp_y = dx / distance

        # Randomize curve direction and magnitude
        curve_magnitude = distance * random.uniform(0.1, 0.3)
        curve_direction = random.choice([-1, 1])

        # First control point (early in movement)
        ctrl1_t = random.uniform(0.2, 0.4)
        ctrl1_curve = curve_magnitude * random.uniform(0.5, 1.0) * curve_direction
        ctrl1 = (
            start[0] + dx * ctrl1_t + perp_x * ctrl1_curve,
            start[1] + dy * ctrl1_t + perp_y * ctrl1_curve
        )

        # Second control point (late in movement)
        ctrl2_t = random.uniform(0.6, 0.8)
        ctrl2_curve = curve_magnitude * random.uniform(0.3, 0.8) * curve_direction
        ctrl2 = (
            start[0] + dx * ctrl2_t + perp_x * ctrl2_curve,
            start[1] + dy * ctrl2_t + perp_y * ctrl2_curve
        )

        return [start, ctrl1, ctrl2, end]

    def generate_trajectory(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        duration: float = None
    ) -> List[Tuple[int, int, float]]:
        """
        Generate complete movement trajectory.

        Args:
            start: Starting position
            end: Target position
            duration: Movement duration (calculated if None)

        Returns:
            List of (x, y, timestamp) points
        """
        if duration is None:
            duration = self.calculate_duration(start, end)

        if duration <= 0:
            return [(end[0], end[1], 0.0)]

        control_points = self.generate_control_points(start, end)
        num_points = max(3, int(duration * self.config.points_per_second))

        trajectory = []
        start_time = 0.0

        for i in range(num_points):
            # Non-linear time interpolation (slow start, fast middle, slow end)
            t_linear = i / (num_points - 1)
            # Ease-in-out function
            t = self._ease_in_out(t_linear)

            # Calculate position on Bezier curve
            if len(control_points) == 2:
                # Linear interpolation
                x = start[0] + (end[0] - start[0]) * t
                y = start[1] + (end[1] - start[1]) * t
            else:
                # Cubic Bezier
                x, y = BezierCurve.cubic(
                    control_points[0],
                    control_points[1],
                    control_points[2],
                    control_points[3],
                    t
                )

            # Add micro-jitter (muscle tremor)
            if i > 0 and i < num_points - 1:  # Not at start/end
                jitter = self.config.jitter_pixels
                x += random.uniform(-jitter, jitter)
                y += random.uniform(-jitter, jitter)

            timestamp = start_time + t_linear * duration
            trajectory.append((int(x), int(y), timestamp))

        # Add overshoot and correction
        if random.random() < self.config.overshoot_probability:
            trajectory = self._add_overshoot(trajectory, end)

        return trajectory

    def _ease_in_out(self, t: float) -> float:
        """Ease-in-out interpolation function."""
        if t < 0.5:
            return 2 * t * t
        else:
            return 1 - (-2 * t + 2) ** 2 / 2

    def _add_overshoot(
        self,
        trajectory: List[Tuple[int, int, float]],
        target: Tuple[int, int]
    ) -> List[Tuple[int, int, float]]:
        """Add overshoot and correction to trajectory."""
        if len(trajectory) < 3:
            return trajectory

        # Get direction of movement
        last_point = trajectory[-1]
        second_last = trajectory[-2]
        dx = last_point[0] - second_last[0]
        dy = last_point[1] - second_last[1]

        # Normalize and scale for overshoot
        dist = math.sqrt(dx**2 + dy**2)
        if dist > 0:
            overshoot_dist = random.uniform(5, self.config.overshoot_distance)
            overshoot_x = int(target[0] + dx/dist * overshoot_dist)
            overshoot_y = int(target[1] + dy/dist * overshoot_dist)

            # Add overshoot point
            overshoot_time = trajectory[-1][2] + 0.05
            trajectory.append((overshoot_x, overshoot_y, overshoot_time))

            # Add correction back to target
            correction_time = overshoot_time + random.uniform(0.03, 0.08)
            trajectory.append((target[0], target[1], correction_time))

        return trajectory

    def move_to(
        self,
        x: int,
        y: int,
        duration: float = None,
        target_width: int = 50
    ) -> None:
        """
        Move mouse to target position.

        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration: Movement duration (calculated if None)
            target_width: Width of target element (for Fitts's Law)
        """
        start = (self._current_x, self._current_y)
        end = (x, y)

        if duration is None:
            duration = self.calculate_duration(start, end, target_width)

        trajectory = self.generate_trajectory(start, end, duration)

        if not self.dry_run and self._sender:
            start_time = time.time()
            for point_x, point_y, t in trajectory:
                # Wait until scheduled time
                elapsed = time.time() - start_time
                if t > elapsed:
                    time.sleep(t - elapsed)

                # Calculate relative movement
                rel_x = point_x - self._current_x
                rel_y = point_y - self._current_y

                if rel_x != 0 or rel_y != 0:
                    self._sender.send_mouse_move(rel_x, rel_y)

                self._current_x = point_x
                self._current_y = point_y

        else:
            # Dry run - just update position
            self._current_x = x
            self._current_y = y

    def click(
        self,
        button: str = 'left',
        clicks: int = 1,
        interval: float = None
    ) -> None:
        """
        Perform mouse click(s).

        Args:
            button: 'left', 'right', or 'middle'
            clicks: Number of clicks
            interval: Time between clicks (random if None)
        """
        for i in range(clicks):
            # Small jitter before click
            if random.random() < 0.3:
                jitter = random.randint(-2, 2)
                if not self.dry_run and self._sender:
                    self._sender.send_mouse_move(jitter, jitter)

            # Click press
            if not self.dry_run and self._sender:
                self._sender.send_mouse_button(button, 'down')

            # Random click duration
            click_duration = random.uniform(0.05, 0.15)
            time.sleep(click_duration)

            # Click release
            if not self.dry_run and self._sender:
                self._sender.send_mouse_button(button, 'up')

            # Interval between clicks
            if i < clicks - 1:
                if interval is None:
                    interval = random.uniform(0.1, 0.3)
                time.sleep(interval)

    def double_click(self, button: str = 'left') -> None:
        """Perform double-click."""
        self.click(button, clicks=2, interval=0.1)

    def scroll(
        self,
        amount: int,
        direction: str = 'down',
        smooth: bool = True
    ) -> None:
        """
        Scroll the mouse wheel.

        Args:
            amount: Scroll amount (pixels or lines)
            direction: 'up' or 'down'
            smooth: Use smooth scrolling with multiple steps
        """
        if direction == 'up':
            amount = -abs(amount)
        else:
            amount = abs(amount)

        if smooth:
            # Break into smaller steps
            steps = max(1, abs(amount) // 20)
            step_size = amount // steps

            for i in range(steps):
                if not self.dry_run and self._sender:
                    self._sender.send_mouse_wheel(step_size)

                # Random pause between scroll steps
                time.sleep(random.uniform(0.02, 0.05))
        else:
            if not self.dry_run and self._sender:
                self._sender.send_mouse_wheel(amount)

    def drag(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        button: str = 'left'
    ) -> None:
        """
        Perform drag operation.

        Args:
            start: Starting position
            end: Ending position
            button: Mouse button to hold during drag
        """
        # Move to start
        self.move_to(start[0], start[1])

        # Press button
        if not self.dry_run and self._sender:
            self._sender.send_mouse_button(button, 'down')

        time.sleep(random.uniform(0.05, 0.1))

        # Drag to end
        self.move_to(end[0], end[1])

        time.sleep(random.uniform(0.05, 0.1))

        # Release button
        if not self.dry_run and self._sender:
            self._sender.send_mouse_button(button, 'up')

    def plan_trajectory(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """
        Generate trajectory without executing (for testing/visualization).

        Args:
            start: Starting position
            end: Target position

        Returns:
            List of (x, y) points
        """
        trajectory = self.generate_trajectory(start, end)
        return [(p[0], p[1]) for p in trajectory]
