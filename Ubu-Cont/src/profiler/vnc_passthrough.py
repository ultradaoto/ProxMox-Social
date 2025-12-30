"""
VNC Passthrough Mode

Allows controlling Windows VM through Ubuntu while recording
all input for profile generation.
"""

from typing import Optional, Callable, Tuple, Dict, Any
import threading
import time
import logging

logger = logging.getLogger(__name__)

# Try to import display libraries
try:
    import pygame
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False

try:
    from pynput import mouse, keyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False


class VNCPassthrough:
    """
    Bidirectional VNC passthrough with input recording.

    Features:
        - Displays Windows VM screen locally
        - Captures local mouse/keyboard input
        - Records all input for profile generation
        - Forwards input to Windows via HID controller
    """

    def __init__(
        self,
        vnc_capturer: Any,
        hid_sender: Any,
        mouse_recorder: Any,
        keyboard_recorder: Any,
        window_title: str = "VNC Passthrough - Recording",
        window_size: Tuple[int, int] = (1920, 1080)
    ):
        """
        Initialize VNC passthrough.

        Args:
            vnc_capturer: VNC screen capturer
            hid_sender: HID command sender
            mouse_recorder: Mouse event recorder
            keyboard_recorder: Keyboard event recorder
            window_title: Display window title
            window_size: Window size (width, height)
        """
        self.vnc_capturer = vnc_capturer
        self.hid_sender = hid_sender
        self.mouse_recorder = mouse_recorder
        self.keyboard_recorder = keyboard_recorder
        self.window_title = window_title
        self.window_size = window_size

        self.running = False
        self._display_thread: Optional[threading.Thread] = None
        self._input_thread: Optional[threading.Thread] = None

        # State
        self.last_mouse_pos = (0, 0)
        self.mouse_in_window = False

        # Callbacks
        self.on_start: Optional[Callable[[], None]] = None
        self.on_stop: Optional[Callable[[], None]] = None
        self.on_frame: Optional[Callable[[Any], None]] = None

    def start(self) -> bool:
        """
        Start passthrough mode.

        Returns:
            True if started successfully
        """
        if not HAS_PYGAME:
            logger.error("pygame required for VNC passthrough display")
            return False

        if not HAS_PYNPUT:
            logger.error("pynput required for input capture")
            return False

        logger.info("Starting VNC passthrough mode")

        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode(self.window_size)
        pygame.display.set_caption(self.window_title)

        # Connect to VNC
        if hasattr(self.vnc_capturer, 'connect'):
            self.vnc_capturer.connect()

        # Start recorders
        self.mouse_recorder.start_recording()
        self.keyboard_recorder.start_recording()

        self.running = True

        # Start display thread
        self._display_thread = threading.Thread(target=self._display_loop, daemon=True)
        self._display_thread.start()

        # Set up input listeners
        self._setup_input_listeners()

        if self.on_start:
            self.on_start()

        logger.info("VNC passthrough started")

        return True

    def stop(self) -> None:
        """Stop passthrough mode."""
        logger.info("Stopping VNC passthrough")

        self.running = False

        # Stop input listeners
        self._stop_input_listeners()

        # Stop recorders
        self.mouse_recorder.stop_recording()
        self.keyboard_recorder.stop_recording()

        # Disconnect VNC
        if hasattr(self.vnc_capturer, 'disconnect'):
            self.vnc_capturer.disconnect()

        # Close pygame
        pygame.quit()

        if self.on_stop:
            self.on_stop()

        logger.info("VNC passthrough stopped")

    def _display_loop(self) -> None:
        """Main display loop."""
        clock = pygame.time.Clock()
        font = pygame.font.Font(None, 24)

        while self.running:
            # Handle pygame events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                        break

            if not self.running:
                break

            # Get VNC frame
            try:
                frame = self.vnc_capturer.capture_frame()

                if frame is not None:
                    # Convert frame to pygame surface
                    if hasattr(frame, 'shape'):
                        # numpy array
                        surface = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
                    else:
                        # PIL Image
                        import io
                        buffer = io.BytesIO()
                        frame.save(buffer, format='PNG')
                        buffer.seek(0)
                        surface = pygame.image.load(buffer)

                    # Scale if needed
                    if surface.get_size() != self.window_size:
                        surface = pygame.transform.scale(surface, self.window_size)

                    self.screen.blit(surface, (0, 0))

                    if self.on_frame:
                        self.on_frame(frame)

            except Exception as e:
                logger.debug(f"Frame capture error: {e}")
                # Show placeholder
                self.screen.fill((50, 50, 50))
                text = font.render("Waiting for VNC connection...", True, (255, 255, 255))
                self.screen.blit(text, (self.window_size[0]//2 - 100, self.window_size[1]//2))

            # Show recording indicator
            recording_text = font.render("RECORDING", True, (255, 0, 0))
            self.screen.blit(recording_text, (10, 10))

            pygame.display.flip()
            clock.tick(60)  # 60 FPS

    def _setup_input_listeners(self) -> None:
        """Set up mouse and keyboard input listeners."""
        # Mouse listener
        self.mouse_listener = mouse.Listener(
            on_move=self._on_mouse_move,
            on_click=self._on_mouse_click,
            on_scroll=self._on_mouse_scroll
        )
        self.mouse_listener.start()

        # Keyboard listener
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release
        )
        self.keyboard_listener.start()

    def _stop_input_listeners(self) -> None:
        """Stop input listeners."""
        if hasattr(self, 'mouse_listener'):
            self.mouse_listener.stop()
        if hasattr(self, 'keyboard_listener'):
            self.keyboard_listener.stop()

    def _on_mouse_move(self, x: int, y: int) -> None:
        """Handle mouse movement."""
        if not self.running:
            return

        # Check if mouse is in our window
        # This is approximate - pygame can help with precise detection
        self.last_mouse_pos = (x, y)

        # Forward to Windows
        if self.hid_sender:
            self.hid_sender.send_mouse({
                'type': 'mouse_move',
                'x': x,
                'y': y
            })

    def _on_mouse_click(self, x: int, y: int, button, pressed: bool) -> None:
        """Handle mouse click."""
        if not self.running:
            return

        button_name = button.name if hasattr(button, 'name') else str(button)
        action = 'down' if pressed else 'up'

        if self.hid_sender:
            self.hid_sender.send_mouse({
                'type': 'mouse_button',
                'button': button_name,
                'action': action
            })

    def _on_mouse_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        """Handle mouse scroll."""
        if not self.running:
            return

        if self.hid_sender:
            self.hid_sender.send_mouse({
                'type': 'mouse_wheel',
                'delta': dy
            })

    def _on_key_press(self, key) -> None:
        """Handle key press."""
        if not self.running:
            return

        key_str = self._key_to_string(key)

        # Check for exit hotkey (Ctrl+Q)
        if key_str == 'q' and hasattr(key, 'ctrl') and key.ctrl:
            self.running = False
            return

        if self.hid_sender:
            self.hid_sender.send_keyboard({
                'type': 'keyboard',
                'key': key_str,
                'action': 'down'
            })

    def _on_key_release(self, key) -> None:
        """Handle key release."""
        if not self.running:
            return

        key_str = self._key_to_string(key)

        if self.hid_sender:
            self.hid_sender.send_keyboard({
                'type': 'keyboard',
                'key': key_str,
                'action': 'up'
            })

    def _key_to_string(self, key) -> str:
        """Convert pynput key to string."""
        try:
            return key.char if key.char else str(key).replace('Key.', '')
        except AttributeError:
            return str(key).replace('Key.', '')


class PassthroughManager:
    """
    High-level manager for VNC passthrough sessions.

    Handles session creation, recording, and profile generation.
    """

    def __init__(
        self,
        vnc_host: str = "192.168.100.10",
        vnc_port: int = 5900,
        vnc_password: Optional[str] = None,
        hid_host: str = "192.168.100.1",
        hid_mouse_port: int = 8888,
        hid_keyboard_port: int = 8889,
        session_dir: str = "recordings/sessions"
    ):
        """
        Initialize passthrough manager.

        Args:
            vnc_host: VNC server host
            vnc_port: VNC server port
            vnc_password: VNC password
            hid_host: HID controller host
            hid_mouse_port: HID mouse port
            hid_keyboard_port: HID keyboard port
            session_dir: Directory for sessions
        """
        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self.vnc_password = vnc_password
        self.hid_host = hid_host
        self.hid_mouse_port = hid_mouse_port
        self.hid_keyboard_port = hid_keyboard_port
        self.session_dir = session_dir

        self.passthrough: Optional[VNCPassthrough] = None
        self.current_session: Optional[str] = None

    def start_recording_session(
        self,
        task_description: str = "VNC Passthrough Recording"
    ) -> Optional[str]:
        """
        Start a new recording session.

        Args:
            task_description: Description of the session

        Returns:
            Session ID if started
        """
        try:
            from ..capture.vnc_capturer import VNCCapturer
            from ..input.remote_sender import RemoteSender
            from .mouse_recorder import MouseRecorder
            from .keyboard_recorder import KeyboardRecorder
            from .session_manager import SessionManager

            # Create components
            vnc = VNCCapturer({
                'host': self.vnc_host,
                'port': self.vnc_port,
                'password': self.vnc_password
            })

            hid = RemoteSender(
                self.hid_host,
                self.hid_mouse_port,
                self.hid_keyboard_port
            )

            mouse_recorder = MouseRecorder()
            keyboard_recorder = KeyboardRecorder()

            # Start session
            session_manager = SessionManager(self.session_dir)
            session_id = session_manager.start_session(
                task_description=task_description,
                tags=['passthrough']
            )
            self.current_session = session_id

            # Create passthrough
            self.passthrough = VNCPassthrough(
                vnc_capturer=vnc,
                hid_sender=hid,
                mouse_recorder=mouse_recorder,
                keyboard_recorder=keyboard_recorder
            )

            # Store references for cleanup
            self._session_manager = session_manager
            self._mouse_recorder = mouse_recorder
            self._keyboard_recorder = keyboard_recorder

            # Start
            if self.passthrough.start():
                return session_id
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to start passthrough: {e}")
            return None

    def stop_recording_session(self) -> Optional[Dict[str, Any]]:
        """
        Stop current recording session.

        Returns:
            Session metadata if stopped
        """
        if not self.passthrough:
            return None

        # Stop passthrough
        self.passthrough.stop()

        # Save recordings
        if hasattr(self, '_session_manager') and self.current_session:
            session_dir = self._session_manager.get_session_dir()

            if session_dir:
                self._mouse_recorder.save_to_file(str(session_dir / "mouse_events.jsonl"))
                self._keyboard_recorder.save_to_file(str(session_dir / "keyboard_events.jsonl"))

            metadata = self._session_manager.end_session()
            return metadata.to_dict() if metadata else None

        return None

    def run_interactive(self, task_description: str = "") -> Optional[Dict[str, Any]]:
        """
        Run interactive passthrough session.

        Blocks until user presses Ctrl+Q or closes window.

        Args:
            task_description: Session description

        Returns:
            Session metadata
        """
        session_id = self.start_recording_session(task_description)

        if not session_id:
            logger.error("Failed to start session")
            return None

        logger.info("Passthrough running. Press Ctrl+Q or close window to stop.")

        # Wait for passthrough to stop
        while self.passthrough and self.passthrough.running:
            time.sleep(0.1)

        return self.stop_recording_session()
