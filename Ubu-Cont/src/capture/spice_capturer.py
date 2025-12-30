"""
Spice Protocol Screen Capturer

Alternative to VNC using the Spice protocol.
Spice typically offers better performance for VM screen capture.
"""

import time
import threading
import queue
import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Spice library availability
try:
    # PySpice or similar library
    HAS_SPICE = False  # Most Python spice bindings are limited
except ImportError:
    HAS_SPICE = False


class SpiceCapturer:
    """
    Spice-based screen capturer for Windows VM.

    Note: Full Spice support requires GTK-based libraries or
    connecting via spice-vdagent. This is a placeholder for
    potential Spice implementation.
    """

    def __init__(
        self,
        host: str = '192.168.100.100',
        port: int = 5930,
        password: str = '',
    ):
        """
        Initialize Spice capturer.

        Args:
            host: Spice server hostname/IP
            port: Spice server port (usually 5900 + display number)
            password: Spice password
        """
        self.host = host
        self.port = port
        self.password = password

        self._connected = False
        self._resolution = None
        self._frame_queue = queue.Queue(maxsize=2)
        self._running = False

    def connect(self) -> bool:
        """
        Connect to Spice server.

        Returns:
            True if connection successful
        """
        if not HAS_SPICE:
            logger.error(
                "Spice support not available. "
                "Consider using VNC or installing spice-gtk bindings."
            )
            return False

        try:
            logger.info(f"Connecting to Spice server at {self.host}:{self.port}")
            # Spice connection logic would go here
            self._connected = True
            return True
        except Exception as e:
            logger.error(f"Spice connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from Spice server."""
        self._running = False
        self._connected = False
        logger.info("Disconnected from Spice server")

    def start_capture(self, fps: int = 30) -> None:
        """Start continuous screen capture."""
        if not self._connected:
            logger.error("Not connected to Spice server")
            return

        self._running = True
        logger.info(f"Started Spice capture at {fps} FPS")

    def stop_capture(self) -> None:
        """Stop continuous screen capture."""
        self._running = False

    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Get the latest captured frame."""
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """Get screen resolution."""
        return self._resolution

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected


class SpiceViaCommand:
    """
    Capture Spice output via external command.

    Uses spicy or remote-viewer to capture frames.
    This is a workaround when native Python bindings aren't available.
    """

    def __init__(
        self,
        host: str = '192.168.100.100',
        port: int = 5930,
        capture_dir: str = '/tmp/spice_captures'
    ):
        import os
        self.host = host
        self.port = port
        self.capture_dir = capture_dir
        os.makedirs(capture_dir, exist_ok=True)

    def capture_single_frame(self, output_path: str) -> bool:
        """
        Capture a single frame using external tool.

        Args:
            output_path: Where to save the captured frame

        Returns:
            True if capture successful
        """
        import subprocess

        try:
            # Try using spicy (spice-gtk tool)
            cmd = [
                'spicy',
                '--uri', f'spice://{self.host}:{self.port}',
                '--capture', output_path,
                '--screenshot'
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=10)
            return result.returncode == 0
        except FileNotFoundError:
            logger.warning("spicy not found. Install spice-gtk.")
            return False
        except subprocess.TimeoutExpired:
            logger.error("Spice capture timed out")
            return False
        except Exception as e:
            logger.error(f"Spice capture failed: {e}")
            return False

    def capture_to_numpy(self) -> Optional[np.ndarray]:
        """
        Capture frame and return as numpy array.

        Returns:
            BGR numpy array or None on failure
        """
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            temp_path = f.name

        try:
            if self.capture_single_frame(temp_path):
                try:
                    import cv2
                    return cv2.imread(temp_path)
                except ImportError:
                    from PIL import Image
                    img = Image.open(temp_path)
                    return np.array(img)[:, :, ::-1]  # RGB to BGR
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        return None
