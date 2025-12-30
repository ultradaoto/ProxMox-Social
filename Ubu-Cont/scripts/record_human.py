#!/usr/bin/env python3
"""
Record Human Input for Profile Learning

Records mouse movements and keyboard timing from a real human
to create a personalized behavior profile.

Note: This script should be run on a machine with actual input devices.
On the Ubuntu VM, you would need to capture input from a connected
display/input device or record remotely.
"""

import sys
import time
import argparse
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from input.personal_profile import ProfileRecorder

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def record_interactive(duration: int, output_path: str):
    """
    Record human input interactively.

    Args:
        duration: Recording duration in seconds
        output_path: Where to save the profile
    """
    try:
        from pynput import mouse, keyboard
    except ImportError:
        logger.error("pynput not installed. Install with: pip install pynput")
        logger.error("Note: pynput requires a display environment")
        sys.exit(1)

    recorder = ProfileRecorder(output_path)

    # Mouse movement tracking
    last_pos = None
    path_points = []

    def on_mouse_move(x, y):
        nonlocal last_pos, path_points
        if last_pos:
            path_points.append((x, y))
        last_pos = (x, y)

    def on_mouse_click(x, y, button, pressed):
        nonlocal path_points
        if pressed and path_points:
            recorder.record_mouse_move(x, y, path_points)
            path_points = []

    def on_key_press(key):
        try:
            key_str = key.char if hasattr(key, 'char') else str(key)
            recorder.record_keystroke(key_str)
        except AttributeError:
            pass

    # Start listeners
    mouse_listener = mouse.Listener(
        on_move=on_mouse_move,
        on_click=on_mouse_click
    )
    keyboard_listener = keyboard.Listener(on_press=on_key_press)

    logger.info(f"Recording for {duration} seconds...")
    logger.info("Use your mouse and keyboard normally.")
    logger.info("Press Ctrl+C to stop early.")

    recorder.start_recording()
    mouse_listener.start()
    keyboard_listener.start()

    try:
        start_time = time.time()
        while time.time() - start_time < duration:
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            print(f"\rRecording... {elapsed}/{duration}s", end='', flush=True)
    except KeyboardInterrupt:
        print("\nStopped early.")

    mouse_listener.stop()
    keyboard_listener.stop()
    recorder.stop_recording()

    # Save profile
    recorder.save(output_path)
    logger.info(f"Profile saved to {output_path}")

    # Print summary
    profile = recorder.profile
    print("\n=== Profile Summary ===")
    print(f"Mouse avg speed: {profile.mouse_avg_speed:.1f} px/s")
    print(f"Mouse overshoot rate: {profile.mouse_overshoot_rate:.1%}")
    print(f"Typing WPM: {profile.typing_wpm:.1f}")
    print(f"Fitts's Law a: {profile.fitts_law_a:.1f}")
    print(f"Fitts's Law b: {profile.fitts_law_b:.1f}")


def analyze_existing(profile_path: str):
    """Analyze an existing profile."""
    recorder = ProfileRecorder(profile_path)

    if not recorder.load(profile_path):
        logger.error(f"Could not load profile from {profile_path}")
        return

    profile = recorder.profile
    print("\n=== Profile Analysis ===")
    print(f"Name: {profile.name}")
    print(f"Created: {profile.created}")
    print(f"Updated: {profile.updated}")
    print()
    print("Mouse Parameters:")
    print(f"  Average speed: {profile.mouse_avg_speed:.1f} px/s")
    print(f"  Speed variance: {profile.mouse_speed_variance:.1f}")
    print(f"  Overshoot rate: {profile.mouse_overshoot_rate:.1%}")
    print(f"  Jitter amount: {profile.mouse_jitter_amount:.1f} px")
    print(f"  Fitts's Law a: {profile.fitts_law_a:.1f}")
    print(f"  Fitts's Law b: {profile.fitts_law_b:.1f}")
    print()
    print("Keyboard Parameters:")
    print(f"  Typing WPM: {profile.typing_wpm:.1f}")
    print(f"  WPM variance: {profile.typing_wpm_variance:.1f}")
    print(f"  Typo rate: {profile.typo_rate:.2%}")
    print(f"  Key hold duration: {profile.key_hold_duration_ms:.1f} ms")
    print(f"  Inter-key interval: {profile.inter_key_interval_ms:.1f} ms")
    print()
    print(f"Samples: {len(profile.mouse_samples)} mouse, {len(profile.keystroke_samples)} keystroke")


def main():
    parser = argparse.ArgumentParser(
        description='Record human input for profile learning'
    )
    subparsers = parser.add_subparsers(dest='command')

    # Record command
    record_parser = subparsers.add_parser('record', help='Record new profile')
    record_parser.add_argument(
        '--duration', '-d',
        type=int,
        default=60,
        help='Recording duration in seconds (default: 60)'
    )
    record_parser.add_argument(
        '--output', '-o',
        default='config/personal_profile.yaml',
        help='Output file path'
    )

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Analyze existing profile')
    analyze_parser.add_argument(
        'profile',
        help='Profile file to analyze'
    )

    args = parser.parse_args()

    if args.command == 'record':
        record_interactive(args.duration, args.output)
    elif args.command == 'analyze':
        analyze_existing(args.profile)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
