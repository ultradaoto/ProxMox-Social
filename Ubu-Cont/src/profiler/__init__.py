"""
Personal Behavioral Biometrics Profiler

This package captures YOUR unique computer usage patterns and replays them
when the AI controls the Windows VM. The goal: make AI-generated input
indistinguishable from your personal behavior.

Three-Phase System:
    1. RECORDING - Capture your mouse, keyboard, and interaction patterns
    2. ANALYSIS - Extract statistical signatures from recordings
    3. REPLAY - Apply your patterns to AI-generated actions

Modules:
    - recorder: Main recording orchestrator
    - mouse_recorder: High-precision mouse capture
    - keyboard_recorder: Keystroke timing capture
    - session_manager: Recording session management
    - analyzer: Statistical analysis of recordings
    - profile_generator: Generate personal profile YAML
    - profile_applier: Apply profile to AI output
    - replay_engine: Replay recordings for testing
    - calibration: Guided calibration exercises
    - visualizer: Visualize your patterns
    - vnc_passthrough: VNC display with input capture
    - config_loader: Configuration management
    - cli: Command-line interface

Usage:
    # Command line
    python -m src.profiler calibrate --user sterling
    python -m src.profiler record -d "Web browsing session"
    python -m src.profiler generate --user sterling
    python -m src.profiler replay <session_id>

    # Python API
    from src.profiler import ProfilerRecorder, ProfileGenerator

    recorder = ProfilerRecorder()
    session_id = recorder.start_recording(task_description="Test")
    # ... do activities ...
    recorder.stop_recording()

    generator = ProfileGenerator()
    profile = generator.generate_from_sessions([session_id])
"""

from .mouse_recorder import MouseRecorder, MouseEvent
from .keyboard_recorder import KeyboardRecorder, KeyEvent
from .session_manager import SessionManager, SessionMetadata
from .analyzer import ProfileAnalyzer, MouseProfile, KeyboardProfile
from .profile_generator import ProfileGenerator
from .profile_applier import ProfileApplier
from .replay_engine import ReplayEngine, ProfileTester
from .calibration import CalibrationExercises, CalibrationTarget, CalibrationSession
from .recorder import ProfilerRecorder, VNCPassthroughRecorder
from .visualizer import ProfileVisualizer
from .vnc_passthrough import VNCPassthrough, PassthroughManager
from .config_loader import ProfilerConfig, get_config, load_config

__version__ = "1.0.0"
__author__ = "Sterling"
__all__ = [
    # Core recorders
    "MouseRecorder",
    "MouseEvent",
    "KeyboardRecorder",
    "KeyEvent",
    # Session management
    "SessionManager",
    "SessionMetadata",
    # Analysis
    "ProfileAnalyzer",
    "MouseProfile",
    "KeyboardProfile",
    # Profile generation and application
    "ProfileGenerator",
    "ProfileApplier",
    # Replay
    "ReplayEngine",
    "ProfileTester",
    # Calibration
    "CalibrationExercises",
    "CalibrationTarget",
    "CalibrationSession",
    # Orchestration
    "ProfilerRecorder",
    "VNCPassthroughRecorder",
    # Visualization
    "ProfileVisualizer",
    # VNC
    "VNCPassthrough",
    "PassthroughManager",
    # Configuration
    "ProfilerConfig",
    "get_config",
    "load_config",
]
