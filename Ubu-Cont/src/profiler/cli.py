"""
Profiler CLI

Command-line interface for the behavioral profiler system.
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_calibrate(args):
    """Run calibration exercises."""
    from .calibration import CalibrationSession

    print(f"\n{'='*60}")
    print("  BEHAVIORAL CALIBRATION SESSION")
    print(f"{'='*60}")
    print(f"\nUser: {args.user}")
    print(f"Output: {args.output}")
    print("\nThis session will capture your unique input patterns.")
    print("Please follow the on-screen instructions.\n")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize calibration
    session = CalibrationSession(
        user_id=args.user,
        output_dir=str(output_dir)
    )

    # Run exercises
    exercises = []
    if not args.skip_fitts:
        exercises.append('fitts')
    if not args.skip_typing:
        exercises.append('typing')
    if not args.skip_scroll:
        exercises.append('scroll')
    if args.include_free:
        exercises.append('free')

    if not exercises:
        print("No exercises selected. Use --include-free or remove skip flags.")
        return 1

    print(f"Exercises to run: {', '.join(exercises)}")
    print("\nPress Enter to begin...")
    input()

    try:
        results = session.run_calibration(exercises=exercises)

        # Save results
        results_file = output_dir / f"calibration_{args.user}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n{'='*60}")
        print("  CALIBRATION COMPLETE")
        print(f"{'='*60}")
        print(f"\nResults saved to: {results_file}")
        print(f"Quality score: {results.get('quality_score', 'N/A')}")

        return 0

    except KeyboardInterrupt:
        print("\n\nCalibration cancelled by user.")
        return 1
    except Exception as e:
        logger.error(f"Calibration failed: {e}")
        return 1


def cmd_record(args):
    """Start a recording session."""
    from .recorder import ProfilerRecorder

    print(f"\n{'='*60}")
    print("  RECORDING SESSION")
    print(f"{'='*60}")
    print(f"\nDescription: {args.description or 'General recording'}")
    print(f"Tags: {args.tags or 'none'}")
    print("\nRecording will start when you press Enter.")
    print("Press Ctrl+C to stop recording.\n")

    input("Press Enter to start...")

    recorder = ProfilerRecorder(
        session_dir=args.output,
        mouse_sample_rate=args.sample_rate,
        auto_save_interval=args.auto_save
    )

    try:
        session_id = recorder.start_recording(
            task_description=args.description or "",
            tags=args.tags.split(',') if args.tags else None
        )

        print(f"\nRecording started: {session_id}")
        print("Recording... (Ctrl+C to stop)")

        # Wait for interrupt
        import time
        while True:
            stats = recorder.get_current_stats()
            print(f"\rMouse: {stats['mouse_events']:,} | "
                  f"Keyboard: {stats['keyboard_events']:,} | "
                  f"Duration: {stats['duration']:.1f}s", end='', flush=True)
            time.sleep(0.5)

    except KeyboardInterrupt:
        print("\n\nStopping recording...")
        metadata = recorder.stop_recording(notes=args.notes or "")

        if metadata:
            print(f"\n{'='*60}")
            print("  RECORDING COMPLETE")
            print(f"{'='*60}")
            print(f"\nSession ID: {metadata['session_id']}")
            print(f"Duration: {metadata['duration_seconds']:.1f}s")
            print(f"Events: {metadata['event_counts']}")
            print(f"Quality: {metadata['quality_score']:.1f}/10")

        return 0


def cmd_passthrough(args):
    """Start VNC passthrough mode."""
    from .vnc_passthrough import PassthroughManager

    print(f"\n{'='*60}")
    print("  VNC PASSTHROUGH MODE")
    print(f"{'='*60}")
    print(f"\nVNC Host: {args.vnc_host}:{args.vnc_port}")
    print(f"HID Host: {args.hid_host}")
    print("\nThis mode displays the Windows VM screen and forwards")
    print("your input while recording everything for profiling.")
    print("\nPress Ctrl+Q or close the window to stop.\n")

    manager = PassthroughManager(
        vnc_host=args.vnc_host,
        vnc_port=args.vnc_port,
        vnc_password=args.vnc_password,
        hid_host=args.hid_host,
        session_dir=args.output
    )

    try:
        result = manager.run_interactive(
            task_description=args.description or "VNC Passthrough Session"
        )

        if result:
            print(f"\n{'='*60}")
            print("  SESSION COMPLETE")
            print(f"{'='*60}")
            print(f"\nSession saved: {result.get('session_id')}")

        return 0

    except Exception as e:
        logger.error(f"Passthrough failed: {e}")
        return 1


def cmd_analyze(args):
    """Analyze recording sessions."""
    from .analyzer import ProfileAnalyzer
    from .session_manager import SessionManager

    print(f"\n{'='*60}")
    print("  PROFILE ANALYSIS")
    print(f"{'='*60}")

    session_manager = SessionManager(args.session_dir)
    analyzer = ProfileAnalyzer()

    # Get sessions to analyze
    if args.session_id:
        sessions = [args.session_id]
    else:
        all_sessions = session_manager.list_sessions()
        if args.limit:
            all_sessions = all_sessions[:args.limit]
        sessions = [s.session_id for s in all_sessions]

    if not sessions:
        print("No sessions found to analyze.")
        return 1

    print(f"\nAnalyzing {len(sessions)} session(s)...")

    # Load and analyze
    all_mouse_events = []
    all_keyboard_events = []

    for session_id in sessions:
        session_dir = Path(args.session_dir) / session_id

        mouse_file = session_dir / "mouse_events.jsonl"
        if mouse_file.exists():
            with open(mouse_file, 'r') as f:
                for line in f:
                    all_mouse_events.append(json.loads(line))

        keyboard_file = session_dir / "keyboard_events.jsonl"
        if keyboard_file.exists():
            with open(keyboard_file, 'r') as f:
                for line in f:
                    all_keyboard_events.append(json.loads(line))

    print(f"Loaded {len(all_mouse_events):,} mouse events")
    print(f"Loaded {len(all_keyboard_events):,} keyboard events")

    # Analyze
    if all_mouse_events:
        mouse_profile = analyzer.analyze_mouse_data(all_mouse_events)
        print(f"\nMouse Profile:")
        print(f"  Fitts's Law: T = {mouse_profile.fitts_a:.3f} + "
              f"{mouse_profile.fitts_b:.3f} * log2(D/W + 1)")
        print(f"  Mean velocity: {mouse_profile.velocity_mean:.1f} px/s")
        print(f"  Overshoot rate: {mouse_profile.overshoot_rate:.1%}")

    if all_keyboard_events:
        keyboard_profile = analyzer.analyze_keyboard_data(all_keyboard_events)
        print(f"\nKeyboard Profile:")
        print(f"  Mean IKI: {keyboard_profile.mean_iki:.0f}ms")
        print(f"  Typing WPM: ~{60000 / (keyboard_profile.mean_iki * 5):.0f}")
        print(f"  Hold mean: {keyboard_profile.hold_mean:.0f}ms")

    # Save analysis
    if args.output:
        output_file = Path(args.output)
        analysis = {
            'sessions_analyzed': len(sessions),
            'mouse_events': len(all_mouse_events),
            'keyboard_events': len(all_keyboard_events),
        }
        if all_mouse_events:
            analysis['mouse_profile'] = mouse_profile.__dict__ if hasattr(mouse_profile, '__dict__') else {}
        if all_keyboard_events:
            analysis['keyboard_profile'] = keyboard_profile.__dict__ if hasattr(keyboard_profile, '__dict__') else {}

        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        print(f"\nAnalysis saved to: {output_file}")

    return 0


def cmd_generate(args):
    """Generate a behavioral profile."""
    from .profile_generator import ProfileGenerator
    from .session_manager import SessionManager

    print(f"\n{'='*60}")
    print("  PROFILE GENERATION")
    print(f"{'='*60}")

    session_manager = SessionManager(args.session_dir)
    generator = ProfileGenerator()

    # Get sessions
    if args.sessions:
        session_ids = args.sessions.split(',')
    else:
        all_sessions = session_manager.list_sessions()
        # Filter by quality if specified
        if args.min_quality:
            all_sessions = [s for s in all_sessions if s.quality_score >= args.min_quality]
        session_ids = [s.session_id for s in all_sessions]

    if not session_ids:
        print("No qualifying sessions found.")
        return 1

    print(f"\nUsing {len(session_ids)} session(s) for profile generation...")

    # Load sessions
    sessions_data = []
    for session_id in session_ids:
        session_dir = Path(args.session_dir) / session_id

        mouse_events = []
        keyboard_events = []

        mouse_file = session_dir / "mouse_events.jsonl"
        if mouse_file.exists():
            with open(mouse_file, 'r') as f:
                for line in f:
                    mouse_events.append(json.loads(line))

        keyboard_file = session_dir / "keyboard_events.jsonl"
        if keyboard_file.exists():
            with open(keyboard_file, 'r') as f:
                for line in f:
                    keyboard_events.append(json.loads(line))

        if mouse_events or keyboard_events:
            sessions_data.append({
                'session_id': session_id,
                'mouse_events': mouse_events,
                'keyboard_events': keyboard_events
            })

    # Generate profile
    profile = generator.generate_profile(
        sessions=sessions_data,
        user_id=args.user,
        profile_name=args.name or f"{args.user}_profile"
    )

    # Save profile
    output_file = Path(args.output) if args.output else Path(f"profiles/{args.user}.yaml")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    generator.save_profile(profile, str(output_file))

    print(f"\n{'='*60}")
    print("  PROFILE GENERATED")
    print(f"{'='*60}")
    print(f"\nProfile saved to: {output_file}")

    # Validate
    is_valid, score, issues = generator.validate_profile(profile)
    print(f"Validation: {'PASSED' if is_valid else 'FAILED'}")
    print(f"Completeness: {score:.0%}")

    if issues:
        print("Issues:")
        for issue in issues:
            print(f"  - {issue}")

    return 0


def cmd_replay(args):
    """Replay a recorded session."""
    from .replay_engine import ReplayEngine

    print(f"\n{'='*60}")
    print("  SESSION REPLAY")
    print(f"{'='*60}")

    session_dir = Path(args.session_dir) / args.session_id

    if not session_dir.exists():
        print(f"Session not found: {args.session_id}")
        return 1

    engine = ReplayEngine(
        hid_host=args.hid_host if not args.dry_run else None,
        mouse_port=args.mouse_port,
        keyboard_port=args.keyboard_port
    )

    # Load session
    mouse_file = session_dir / "mouse_events.jsonl"
    keyboard_file = session_dir / "keyboard_events.jsonl"

    if not mouse_file.exists() and not keyboard_file.exists():
        print("No event files found in session.")
        return 1

    print(f"\nSession: {args.session_id}")
    print(f"Speed: {args.speed}x")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")

    if not args.dry_run:
        print("\nWARNING: This will send actual input to the target system!")
        confirm = input("Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return 1

    try:
        if mouse_file.exists():
            engine.load_mouse_events(str(mouse_file))
        if keyboard_file.exists():
            engine.load_keyboard_events(str(keyboard_file))

        print("\nStarting replay... (Ctrl+C to stop)")

        engine.replay(
            speed=args.speed,
            include_mouse=not args.keyboard_only,
            include_keyboard=not args.mouse_only
        )

        print("\nReplay complete.")
        return 0

    except KeyboardInterrupt:
        print("\n\nReplay stopped.")
        return 1


def cmd_visualize(args):
    """Visualize recording data."""
    from .visualizer import ProfileVisualizer

    print(f"\n{'='*60}")
    print("  PROFILE VISUALIZATION")
    print(f"{'='*60}")

    visualizer = ProfileVisualizer()

    session_dir = Path(args.session_dir)
    if args.session_id:
        session_dir = session_dir / args.session_id

    # Load data
    mouse_events = []
    keyboard_events = []

    mouse_file = session_dir / "mouse_events.jsonl"
    if mouse_file.exists():
        with open(mouse_file, 'r') as f:
            for line in f:
                mouse_events.append(json.loads(line))
        print(f"Loaded {len(mouse_events):,} mouse events")

    keyboard_file = session_dir / "keyboard_events.jsonl"
    if keyboard_file.exists():
        with open(keyboard_file, 'r') as f:
            for line in f:
                keyboard_events.append(json.loads(line))
        print(f"Loaded {len(keyboard_events):,} keyboard events")

    if not mouse_events and not keyboard_events:
        print("No event data found.")
        return 1

    # Generate visualizations
    output_dir = Path(args.output) if args.output else session_dir / "visualizations"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating visualizations to: {output_dir}")

    if mouse_events:
        if 'trajectory' in args.plots or 'all' in args.plots:
            visualizer.plot_trajectories(mouse_events, str(output_dir / "trajectories.png"))
            print("  - Trajectory plot saved")

        if 'velocity' in args.plots or 'all' in args.plots:
            visualizer.plot_velocity_profile(mouse_events, str(output_dir / "velocity.png"))
            print("  - Velocity profile saved")

        if 'fitts' in args.plots or 'all' in args.plots:
            visualizer.plot_fitts_analysis(mouse_events, str(output_dir / "fitts.png"))
            print("  - Fitts's Law analysis saved")

    if keyboard_events:
        if 'typing' in args.plots or 'all' in args.plots:
            visualizer.plot_typing_rhythm(keyboard_events, str(output_dir / "typing.png"))
            print("  - Typing rhythm plot saved")

        if 'digraph' in args.plots or 'all' in args.plots:
            visualizer.plot_digraph_heatmap(keyboard_events, str(output_dir / "digraph.png"))
            print("  - Digraph heatmap saved")

    print("\nVisualization complete.")

    if args.show:
        import subprocess
        subprocess.run(['xdg-open', str(output_dir)], check=False)

    return 0


def cmd_list(args):
    """List recording sessions."""
    from .session_manager import SessionManager

    session_manager = SessionManager(args.session_dir)
    sessions = session_manager.list_sessions()

    if not sessions:
        print("No sessions found.")
        return 0

    print(f"\n{'ID':<36} {'Date':<20} {'Duration':<10} {'Quality':<8} {'Description'}")
    print("-" * 100)

    for session in sessions:
        duration = f"{session.duration_seconds:.0f}s" if session.duration_seconds else "N/A"
        quality = f"{session.quality_score:.1f}" if session.quality_score else "N/A"
        desc = (session.task_description[:30] + "...") if len(session.task_description) > 30 else session.task_description

        print(f"{session.session_id:<36} {session.start_time[:19]:<20} {duration:<10} {quality:<8} {desc}")

    print(f"\nTotal: {len(sessions)} session(s)")
    return 0


def cmd_delete(args):
    """Delete a recording session."""
    from .session_manager import SessionManager

    session_manager = SessionManager(args.session_dir)

    if not args.force:
        confirm = input(f"Delete session {args.session_id}? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return 1

    if session_manager.delete_session(args.session_id, confirm=True):
        print(f"Session {args.session_id} deleted.")
        return 0
    else:
        print(f"Failed to delete session {args.session_id}")
        return 1


def cmd_export(args):
    """Export session data."""
    from .session_manager import SessionManager

    session_manager = SessionManager(args.session_dir)

    output_file = args.output or f"{args.session_id}.zip"

    if session_manager.export_session(args.session_id, output_file):
        print(f"Session exported to: {output_file}")
        return 0
    else:
        print("Export failed.")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='profiler',
        description='Behavioral Biometrics Profiler - Capture and replay human input patterns'
    )
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Calibrate command
    cal_parser = subparsers.add_parser('calibrate', help='Run calibration exercises')
    cal_parser.add_argument('-u', '--user', required=True, help='User identifier')
    cal_parser.add_argument('-o', '--output', default='calibrations', help='Output directory')
    cal_parser.add_argument('--skip-fitts', action='store_true', help='Skip Fitts\'s Law test')
    cal_parser.add_argument('--skip-typing', action='store_true', help='Skip typing test')
    cal_parser.add_argument('--skip-scroll', action='store_true', help='Skip scroll test')
    cal_parser.add_argument('--include-free', action='store_true', help='Include free recording')
    cal_parser.set_defaults(func=cmd_calibrate)

    # Record command
    rec_parser = subparsers.add_parser('record', help='Start recording session')
    rec_parser.add_argument('-d', '--description', help='Session description')
    rec_parser.add_argument('-t', '--tags', help='Comma-separated tags')
    rec_parser.add_argument('-o', '--output', default='recordings/sessions', help='Output directory')
    rec_parser.add_argument('-n', '--notes', help='Session notes')
    rec_parser.add_argument('--sample-rate', type=int, default=1000, help='Mouse sample rate (Hz)')
    rec_parser.add_argument('--auto-save', type=float, default=30.0, help='Auto-save interval (seconds)')
    rec_parser.set_defaults(func=cmd_record)

    # Passthrough command
    pt_parser = subparsers.add_parser('passthrough', help='Start VNC passthrough mode')
    pt_parser.add_argument('--vnc-host', default='192.168.100.10', help='VNC host')
    pt_parser.add_argument('--vnc-port', type=int, default=5900, help='VNC port')
    pt_parser.add_argument('--vnc-password', help='VNC password')
    pt_parser.add_argument('--hid-host', default='192.168.100.1', help='HID controller host')
    pt_parser.add_argument('-d', '--description', help='Session description')
    pt_parser.add_argument('-o', '--output', default='recordings/sessions', help='Output directory')
    pt_parser.set_defaults(func=cmd_passthrough)

    # Analyze command
    ana_parser = subparsers.add_parser('analyze', help='Analyze recording sessions')
    ana_parser.add_argument('-s', '--session-id', help='Specific session to analyze')
    ana_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    ana_parser.add_argument('-l', '--limit', type=int, help='Limit number of sessions')
    ana_parser.add_argument('-o', '--output', help='Output file for analysis')
    ana_parser.set_defaults(func=cmd_analyze)

    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate behavioral profile')
    gen_parser.add_argument('-u', '--user', required=True, help='User identifier')
    gen_parser.add_argument('-n', '--name', help='Profile name')
    gen_parser.add_argument('--sessions', help='Comma-separated session IDs')
    gen_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    gen_parser.add_argument('--min-quality', type=float, help='Minimum quality score')
    gen_parser.add_argument('-o', '--output', help='Output file')
    gen_parser.set_defaults(func=cmd_generate)

    # Replay command
    rep_parser = subparsers.add_parser('replay', help='Replay recorded session')
    rep_parser.add_argument('session_id', help='Session ID to replay')
    rep_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    rep_parser.add_argument('--hid-host', default='192.168.100.1', help='HID controller host')
    rep_parser.add_argument('--mouse-port', type=int, default=8888, help='Mouse port')
    rep_parser.add_argument('--keyboard-port', type=int, default=8889, help='Keyboard port')
    rep_parser.add_argument('-s', '--speed', type=float, default=1.0, help='Playback speed')
    rep_parser.add_argument('--dry-run', action='store_true', help='Don\'t send actual input')
    rep_parser.add_argument('--mouse-only', action='store_true', help='Only replay mouse')
    rep_parser.add_argument('--keyboard-only', action='store_true', help='Only replay keyboard')
    rep_parser.set_defaults(func=cmd_replay)

    # Visualize command
    vis_parser = subparsers.add_parser('visualize', help='Visualize recording data')
    vis_parser.add_argument('--session-id', help='Session ID to visualize')
    vis_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    vis_parser.add_argument('-o', '--output', help='Output directory')
    vis_parser.add_argument('--plots', nargs='+', default=['all'],
                           choices=['all', 'trajectory', 'velocity', 'fitts', 'typing', 'digraph'],
                           help='Plots to generate')
    vis_parser.add_argument('--show', action='store_true', help='Open output directory')
    vis_parser.set_defaults(func=cmd_visualize)

    # List command
    list_parser = subparsers.add_parser('list', help='List recording sessions')
    list_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    list_parser.set_defaults(func=cmd_list)

    # Delete command
    del_parser = subparsers.add_parser('delete', help='Delete a session')
    del_parser.add_argument('session_id', help='Session ID to delete')
    del_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    del_parser.add_argument('-f', '--force', action='store_true', help='Skip confirmation')
    del_parser.set_defaults(func=cmd_delete)

    # Export command
    exp_parser = subparsers.add_parser('export', help='Export session data')
    exp_parser.add_argument('session_id', help='Session ID to export')
    exp_parser.add_argument('--session-dir', default='recordings/sessions', help='Sessions directory')
    exp_parser.add_argument('-o', '--output', help='Output file')
    exp_parser.set_defaults(func=cmd_export)

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
