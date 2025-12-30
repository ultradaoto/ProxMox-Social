"""
Trajectory Generation Utilities

Advanced trajectory generation with wind simulation
and natural movement patterns.
"""

import math
import random
from typing import List, Tuple, Callable
from dataclasses import dataclass


@dataclass
class TrajectoryConfig:
    """Configuration for trajectory generation."""
    gravity: float = 9.0  # Simulated "gravity" for curve
    wind: float = 3.0  # Wind variation
    target_area: float = 1.0  # Target size factor
    min_steps: int = 10
    max_steps: int = 100


def wind_mouse(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    gravity: float = 9.0,
    wind: float = 3.0,
    min_wait: float = 2.0,
    max_wait: float = 10.0,
    target_area: float = 10.0
) -> List[Tuple[int, int]]:
    """
    Generate mouse trajectory using WindMouse algorithm.

    This algorithm simulates natural mouse movement with:
    - Wind: Random force pushing the cursor off course
    - Gravity: Force pulling toward target

    Based on the classic WindMouse algorithm from game automation.

    Args:
        start_x, start_y: Starting position
        end_x, end_y: Target position
        gravity: Force toward target
        wind: Random deviation force
        min_wait, max_wait: Step timing range (unused, returns points only)
        target_area: Size of target area

    Returns:
        List of (x, y) points along the trajectory
    """
    sqrt3 = math.sqrt(3)
    sqrt5 = math.sqrt(5)

    current_x = float(start_x)
    current_y = float(end_y)
    wind_x = 0.0
    wind_y = 0.0
    velocity_x = 0.0
    velocity_y = 0.0

    points = [(int(start_x), int(start_y))]

    while True:
        dist = math.hypot(end_x - current_x, end_y - current_y)

        if dist < 1:
            break

        # Wind changes randomly
        wind_factor = min(wind, dist)
        if dist >= target_area:
            wind_x = wind_x / sqrt3 + random.uniform(-wind_factor, wind_factor) / sqrt5
            wind_y = wind_y / sqrt3 + random.uniform(-wind_factor, wind_factor) / sqrt5
        else:
            wind_x /= sqrt3
            wind_y /= sqrt3

        # Gravity pulls toward target
        gravity_factor = min(gravity, dist)
        velocity_x += wind_x + gravity_factor * (end_x - current_x) / dist
        velocity_y += wind_y + gravity_factor * (end_y - current_y) / dist

        # Limit velocity
        velocity_mag = math.hypot(velocity_x, velocity_y)
        if velocity_mag > dist:
            random_dist = dist / 2.0 + random.random() * dist / 2.0
            velocity_x = velocity_x / velocity_mag * random_dist
            velocity_y = velocity_y / velocity_mag * random_dist

        current_x += velocity_x
        current_y += velocity_y

        points.append((int(round(current_x)), int(round(current_y))))

    # Ensure we end exactly at target
    points.append((int(end_x), int(end_y)))

    return points


def catmull_rom_spline(
    points: List[Tuple[float, float]],
    num_points: int = 100
) -> List[Tuple[float, float]]:
    """
    Generate smooth curve through control points using Catmull-Rom spline.

    Args:
        points: Control points
        num_points: Number of output points

    Returns:
        Smooth curve through the control points
    """
    if len(points) < 2:
        return points

    # Add virtual points at start and end for smooth endpoints
    p0 = (2 * points[0][0] - points[1][0], 2 * points[0][1] - points[1][1])
    pn = (2 * points[-1][0] - points[-2][0], 2 * points[-1][1] - points[-2][1])

    extended = [p0] + list(points) + [pn]
    result = []

    segments = len(extended) - 3
    points_per_segment = num_points // segments

    for i in range(segments):
        p0 = extended[i]
        p1 = extended[i + 1]
        p2 = extended[i + 2]
        p3 = extended[i + 3]

        for j in range(points_per_segment):
            t = j / points_per_segment

            # Catmull-Rom spline formula
            tt = t * t
            ttt = tt * t

            q1 = -ttt + 2*tt - t
            q2 = 3*ttt - 5*tt + 2
            q3 = -3*ttt + 4*tt + t
            q4 = ttt - tt

            x = 0.5 * (p0[0]*q1 + p1[0]*q2 + p2[0]*q3 + p3[0]*q4)
            y = 0.5 * (p0[1]*q1 + p1[1]*q2 + p2[1]*q3 + p3[1]*q4)

            result.append((x, y))

    result.append(points[-1])
    return result


def apply_jitter(
    points: List[Tuple[int, int]],
    amount: float = 2.0,
    skip_endpoints: bool = True
) -> List[Tuple[int, int]]:
    """
    Add random jitter to trajectory points.

    Args:
        points: Input trajectory
        amount: Maximum jitter in pixels
        skip_endpoints: Don't jitter first/last points

    Returns:
        Jittered trajectory
    """
    result = []
    for i, (x, y) in enumerate(points):
        if skip_endpoints and (i == 0 or i == len(points) - 1):
            result.append((x, y))
        else:
            jx = x + random.uniform(-amount, amount)
            jy = y + random.uniform(-amount, amount)
            result.append((int(jx), int(jy)))
    return result


def apply_acceleration(
    points: List[Tuple[int, int]],
    profile: str = 'ease_in_out'
) -> List[Tuple[float, int, int]]:
    """
    Apply timing based on acceleration profile.

    Args:
        points: Trajectory points
        profile: 'linear', 'ease_in', 'ease_out', 'ease_in_out'

    Returns:
        List of (time, x, y) with timing applied
    """
    if not points:
        return []

    # Calculate total distance
    total_dist = 0.0
    distances = [0.0]
    for i in range(1, len(points)):
        d = math.hypot(
            points[i][0] - points[i-1][0],
            points[i][1] - points[i-1][1]
        )
        total_dist += d
        distances.append(total_dist)

    # Normalize to 0-1
    if total_dist > 0:
        distances = [d / total_dist for d in distances]

    # Apply acceleration profile
    ease_funcs = {
        'linear': lambda t: t,
        'ease_in': lambda t: t * t,
        'ease_out': lambda t: 1 - (1 - t) ** 2,
        'ease_in_out': lambda t: 2*t*t if t < 0.5 else 1 - (-2*t + 2)**2 / 2,
    }
    ease_func = ease_funcs.get(profile, ease_funcs['ease_in_out'])

    result = []
    for i, (x, y) in enumerate(points):
        t = ease_func(distances[i])
        result.append((t, x, y))

    return result


def generate_human_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    curvature: float = 0.3,
    points: int = 50
) -> List[Tuple[int, int]]:
    """
    Generate a human-like path between two points.

    Combines multiple techniques for realistic movement.

    Args:
        start: Starting position
        end: Target position
        curvature: How curved the path should be (0-1)
        points: Number of points in trajectory

    Returns:
        Human-like trajectory
    """
    distance = math.hypot(end[0] - start[0], end[1] - start[1])

    if distance < 5:
        # Very short distance, direct path
        return [start, end]

    # Use WindMouse for base trajectory
    base_path = wind_mouse(
        start[0], start[1],
        end[0], end[1],
        gravity=9.0 * (1 - curvature * 0.5),
        wind=3.0 * (1 + curvature),
        target_area=max(1, distance * 0.1)
    )

    # Smooth with Catmull-Rom if we have enough points
    if len(base_path) >= 4:
        smooth_path = catmull_rom_spline(
            [(float(p[0]), float(p[1])) for p in base_path],
            num_points=points
        )
        base_path = [(int(p[0]), int(p[1])) for p in smooth_path]

    # Add subtle jitter
    jittered = apply_jitter(base_path, amount=1.5)

    return jittered
