"""
Profile Recorder

Main orchestrator for recording user behavior.
Combines mouse, keyboard, and screen recording into sessions.
"""

from typing import Optional, Dict, Any, List
from pathlib import Path
import time
import threading
import logging

from .mouse_recorder import MouseRecorder
from .keyboard_recorder import KeyboardRecorder
from .session_manager import SessionManager

logger = logging.getLogger(__name__)


class ProfilerRecorder:
    """
    Main recording orchestrator.

    Coordinates mouse, keyboard, and screen recording
    into cohesive sessions for profile generation.

    Features:
        - Synchronized multi-input recording
        - Session management
        - Real-time statistics
        - Automatic saving
        - Event callbacks
    """

    def __init__(
        self,
        session_dir: str = "recordings/sessions",
        mouse_sample_rate: int = 1000,
        auto_save_interval: float = 30.0
    ):
        """
        Initialize profiler recorder.

        Args:
            session_dir: Directory for session storage
            mouse_sample_rate: Mouse sampling rate in Hz
            auto_save_interval: Interval for auto-saving in seconds
        """
        self.session_manager = SessionManager(session_dir)
        self.mouse_recorder = MouseRecorder(sample_rate_hz=mouse_sample_rate)
        self.keyboard_recorder = KeyboardRecorder()

        self.auto_save_interval = auto_save_interval
        self._auto_save_thread: Optional[threading.Thread] = None
        self._recording = False

        # Statistics
        self.session_stats = {
            'start_time': None,
            'mouse_events': 0,
            'keyboard_events': 0,
            'duration': 0
        }

        # Set up event callbacks
        self.mouse_recorder.on_event = self._on_mouse_event
        self.keyboard_recorder.on_event = self._on_keyboard_event

        # External callbacks
        self.on_stats_update: Optional[callable] = None

    def start_recording(
        self,
        task_description: str = "",
        tags: Optional[List[str]] = None
    ) -> str:
        """
        Start a new recording session.

        Args:
            task_description: Description of recording session
            tags: Tags for categorization

        Returns:
            Session ID
        """
        if self._recording:
            logger.warning("Already recording, stopping current session first")
            self.stop_recording()

        # Start session
        session_id = self.session_manager.start_session(
            task_description=task_description,
            tags=tags,
            calibration_type='free'
        )

        # Reset stats
        self.session_stats = {
            'start_time': time.time(),
            'mouse_events': 0,
            'keyboard_events': 0,
            'duration': 0
        }

        # Start recorders
        self.mouse_recorder.start_recording()
        self.keyboard_recorder.start_recording()

        self._recording = True

        # Start auto-save thread
        self._auto_save_thread = threading.Thread(
            target=self._auto_save_loop,
            daemon=True
        )
        self._auto_save_thread.start()

        logger.info(f"Started recording session: {session_id}")

        return session_id

    def stop_recording(self, notes: str = "") -> Optional[Dict[str, Any]]:
        """
        Stop current recording session.

        Args:
            notes: Optional notes about the session

        Returns:
            Session metadata
        """
        if not self._recording:
            return None

        self._recording = False

        # Stop recorders
        mouse_events = self.mouse_recorder.stop_recording()
        keyboard_events = self.keyboard_recorder.stop_recording()

        # Save events
        session_dir = self.session_manager.get_session_dir()
        if session_dir:
            self.mouse_recorder.save_to_file(str(session_dir / "mouse_events.jsonl"))
            self.keyboard_recorder.save_to_file(str(session_dir / "keyboard_events.jsonl"))

            # Save segments
            self.mouse_recorder.save_segments_to_file(str(session_dir / "mouse_segments.json"))

            # Save digraph data
            self.keyboard_recorder.save_digraphs_to_file(str(session_dir / "digraph_timing.json"))

        # End session
        metadata = self.session_manager.end_session(notes=notes)

        logger.info(f"Stopped recording. {len(mouse_events)} mouse events, "
                   f"{len(keyboard_events)} keyboard events")

        return metadata.to_dict() if metadata else None

    def pause_recording(self) -> None:
        """Pause recording (not fully implemented - stops and caches)."""
        logger.info("Pausing recording")
        # For now, just log - full pause/resume requires more state management

    def resume_recording(self) -> None:
        """Resume paused recording."""
        logger.info("Resuming recording")

    def get_current_stats(self) -> Dict[str, Any]:
        """Get current recording statistics."""
        if self.session_stats['start_time']:
            self.session_stats['duration'] = time.time() - self.session_stats['start_time']

        return {
            **self.session_stats,
            'recording': self._recording,
            'session_id': self.session_manager.current_session
        }

    def get_live_mouse_stats(self) -> Dict[str, Any]:
        """Get live mouse statistics."""
        return self.mouse_recorder.get_statistics()

    def get_live_keyboard_stats(self) -> Dict[str, Any]:
        """Get live keyboard statistics."""
        return self.keyboard_recorder.get_statistics()

    def _on_mouse_event(self, event) -> None:
        """Handle mouse event from recorder."""
        self.session_stats['mouse_events'] += 1

        if self.on_stats_update and self.session_stats['mouse_events'] % 100 == 0:
            self.on_stats_update(self.get_current_stats())

    def _on_keyboard_event(self, event) -> None:
        """Handle keyboard event from recorder."""
        self.session_stats['keyboard_events'] += 1

        if self.on_stats_update and self.session_stats['keyboard_events'] % 10 == 0:
            self.on_stats_update(self.get_current_stats())

    def _auto_save_loop(self) -> None:
        """Auto-save loop running in background."""
        while self._recording:
            time.sleep(self.auto_save_interval)

            if not self._recording:
                break

            self._save_current_data()

    def _save_current_data(self) -> None:
        """Save current recording data."""
        session_dir = self.session_manager.get_session_dir()
        if not session_dir:
            return

        try:
            # Save mouse events (append mode would be better for large sessions)
            self.mouse_recorder.save_to_file(str(session_dir / "mouse_events.jsonl"))
            self.keyboard_recorder.save_to_file(str(session_dir / "keyboard_events.jsonl"))

            logger.debug(f"Auto-saved recording data ({self.session_stats['mouse_events']} mouse, "
                        f"{self.session_stats['keyboard_events']} keyboard events)")

        except Exception as e:
            logger.error(f"Auto-save failed: {e}")

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all recording sessions."""
        sessions = self.session_manager.list_sessions()
        return [s.to_dict() for s in sessions]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        return self.session_manager.delete_session(session_id, confirm=True)

    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get info about a specific session."""
        metadata = self.session_manager.get_session_metadata(session_id)
        return metadata.to_dict() if metadata else None


class VNCPassthroughRecorder(ProfilerRecorder):
    """
    Extended recorder with VNC passthrough capability.

    Allows controlling Windows VM through VNC while recording
    all input for profile generation.
    """

    def __init__(
        self,
        vnc_host: str = "192.168.100.10",
        vnc_port: int = 5900,
        vnc_password: Optional[str] = None,
        hid_host: str = "192.168.100.1",
        **kwargs
    ):
        """
        Initialize VNC passthrough recorder.

        Args:
            vnc_host: VNC server host
            vnc_port: VNC server port
            vnc_password: VNC password
            hid_host: HID controller host
            **kwargs: Arguments for ProfilerRecorder
        """
        super().__init__(**kwargs)

        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self.vnc_password = vnc_password
        self.hid_host = hid_host

        self.vnc_client = None
        self.hid_sender = None
        self.display_window = None

        self._passthrough_active = False

    def start_passthrough(
        self,
        task_description: str = "VNC Passthrough Recording"
    ) -> str:
        """
        Start passthrough mode.

        Opens window showing VNC stream, captures local input,
        forwards to Windows VM, and records everything.

        Args:
            task_description: Description for the session

        Returns:
            Session ID
        """
        # Import here to avoid dependency issues
        try:
            from ..capture.vnc_capturer import VNCCapturer
            from ..input.remote_sender import RemoteSender
        except ImportError:
            logger.error("VNC capturer or remote sender not available")
            raise

        # Start recording session
        session_id = self.start_recording(
            task_description=task_description,
            tags=['passthrough', 'vnc']
        )

        # Connect to VNC
        # self.vnc_client = VNCCapturer(...)
        # self.hid_sender = RemoteSender(...)

        # Create display window
        # self._create_display_window()

        self._passthrough_active = True

        logger.info(f"Started VNC passthrough: {session_id}")

        return session_id

    def stop_passthrough(self) -> Optional[Dict[str, Any]]:
        """Stop passthrough mode."""
        self._passthrough_active = False

        # Close display window
        # self._close_display_window()

        # Disconnect VNC
        # if self.vnc_client: self.vnc_client.disconnect()

        # Stop recording
        return self.stop_recording(notes="VNC passthrough session")

    def _create_display_window(self) -> None:
        """Create window to display VNC stream."""
        # Implementation depends on display framework (pygame, tkinter, etc.)
        pass

    def _close_display_window(self) -> None:
        """Close display window."""
        pass

    def _forward_input(self, event: Dict) -> None:
        """Forward input event to Windows VM."""
        if not self.hid_sender or not self._passthrough_active:
            return

        if event.get('source') == 'mouse':
            self.hid_sender.send_mouse(event)
        elif event.get('source') == 'keyboard':
            self.hid_sender.send_keyboard(event)
