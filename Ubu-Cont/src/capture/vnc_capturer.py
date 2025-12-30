"""
VNC Screen Capturer

Captures screen frames from the Windows VM via VNC protocol.
"""

import time
import threading
import queue
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

import numpy as np

# VNC library - using vncdotool or similar
try:
    from vncdotool import api as vnc_api
    HAS_VNCDOTOOL = True
except ImportError:
    HAS_VNCDOTOOL = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

logger = logging.getLogger(__name__)


@dataclass
class CaptureStats:
    """Statistics about screen capture."""
    frames_captured: int = 0
    frames_dropped: int = 0
    last_capture_time: float = 0.0
    average_fps: float = 0.0


class VNCCapturer:
    """
    VNC-based screen capturer for Windows VM.

    Connects to a VNC server and continuously captures frames
    into a buffer for processing.
    """

    def __init__(
        self,
        host: str = '192.168.100.100',
        port: int = 5900,
        password: str = '',
        timeout: float = 10.0,
        buffer_size: int = 2,
    ):
        """
        Initialize VNC capturer.

        Args:
            host: VNC server hostname/IP
            port: VNC server port
            password: VNC password
            timeout: Connection timeout in seconds
            buffer_size: Number of frames to buffer
        """
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.buffer_size = buffer_size

        self._client = None
        self._frame_queue: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._resolution: Optional[Tuple[int, int]] = None

        self.stats = CaptureStats()
        self._start_time = 0.0

    def connect(self) -> bool:
        """
        Connect to VNC server.

        Returns:
            True if connection successful
        """
        if not HAS_VNCDOTOOL:
            logger.error("vncdotool not installed. Install with: pip install vncdotool")
            return False

        try:
            logger.info(f"Connecting to VNC server at {self.host}:{self.port}")

            self._client = vnc_api.connect(
                f'{self.host}::{self.port}',
                password=self.password
            )

            # Get initial screen size
            self._resolution = (self._client.screen.width, self._client.screen.height)
            logger.info(f"Connected. Resolution: {self._resolution[0]}x{self._resolution[1]}")

            return True

        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
            return False

    def disconnect(self) -> None:
        """Disconnect from VNC server."""
        self.stop_capture()

        if self._client:
            try:
                self._client.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting: {e}")
            self._client = None

        logger.info("Disconnected from VNC server")

    def start_capture(self, fps: int = 30) -> None:
        """
        Start continuous screen capture.

        Args:
            fps: Target frames per second
        """
        if self._running:
            logger.warning("Capture already running")
            return

        if not self._client:
            if not self.connect():
                return

        self._running = True
        self._start_time = time.time()
        self.stats = CaptureStats()

        self._capture_thread = threading.Thread(
            target=self._capture_loop,
            args=(fps,),
            daemon=True,
            name='VNCCapture'
        )
        self._capture_thread.start()
        logger.info(f"Started capture at {fps} FPS")

    def stop_capture(self) -> None:
        """Stop continuous screen capture."""
        self._running = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)

        # Clear queue
        while not self._frame_queue.empty():
            try:
                self._frame_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Stopped capture")

    def _capture_loop(self, fps: int) -> None:
        """Main capture loop."""
        frame_interval = 1.0 / fps

        while self._running:
            start_time = time.time()

            try:
                # Capture frame
                frame = self._capture_frame()

                if frame is not None:
                    # Try to add to queue (non-blocking)
                    try:
                        self._frame_queue.put_nowait(frame)
                        self.stats.frames_captured += 1
                    except queue.Full:
                        # Drop oldest frame and add new one
                        try:
                            self._frame_queue.get_nowait()
                            self._frame_queue.put_nowait(frame)
                            self.stats.frames_dropped += 1
                        except queue.Empty:
                            pass

                    self.stats.last_capture_time = time.time()

            except Exception as e:
                logger.error(f"Capture error: {e}")
                time.sleep(1.0)  # Back off on error
                continue

            # Maintain frame rate
            elapsed = time.time() - start_time
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Update average FPS
        total_time = time.time() - self._start_time
        if total_time > 0:
            self.stats.average_fps = self.stats.frames_captured / total_time

    def _capture_frame(self) -> Optional[np.ndarray]:
        """
        Capture a single frame from VNC.

        Returns:
            BGR numpy array or None on failure
        """
        if not self._client:
            return None

        try:
            # Refresh screen
            self._client.refreshScreen()

            # Get screen capture
            screen = self._client.screen

            # Convert to numpy array
            if hasattr(screen, 'getPixel'):
                # Build image from pixels (slow fallback)
                width, height = self._resolution
                img = np.zeros((height, width, 3), dtype=np.uint8)
                for y in range(height):
                    for x in range(width):
                        r, g, b = screen.getPixel(x, y)
                        img[y, x] = [b, g, r]  # BGR format
                return img
            else:
                # Try direct buffer access if available
                img_data = screen.image
                if hasattr(img_data, 'tobytes'):
                    arr = np.frombuffer(img_data.tobytes(), dtype=np.uint8)
                    arr = arr.reshape((self._resolution[1], self._resolution[0], 3))
                    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        except Exception as e:
            logger.warning(f"Frame capture failed: {e}")

        return None

    def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Get the latest captured frame.

        Args:
            timeout: How long to wait for a frame

        Returns:
            BGR numpy array or None if no frame available
        """
        try:
            return self._frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def get_frame_nowait(self) -> Optional[np.ndarray]:
        """
        Get the latest frame without waiting.

        Returns:
            BGR numpy array or None if no frame available
        """
        try:
            return self._frame_queue.get_nowait()
        except queue.Empty:
            return None

    def get_resolution(self) -> Optional[Tuple[int, int]]:
        """Get screen resolution (width, height)."""
        return self._resolution

    def is_connected(self) -> bool:
        """Check if connected to VNC server."""
        return self._client is not None

    def is_capturing(self) -> bool:
        """Check if capture is running."""
        return self._running

    def get_stats(self) -> CaptureStats:
        """Get capture statistics."""
        return self.stats

    def save_screenshot(self, path: str) -> bool:
        """
        Save current frame as image file.

        Args:
            path: Output file path

        Returns:
            True if saved successfully
        """
        frame = self.get_frame_nowait()
        if frame is None:
            logger.warning("No frame available for screenshot")
            return False

        try:
            if HAS_CV2:
                cv2.imwrite(path, frame)
            else:
                from PIL import Image
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                img.save(path)
            logger.info(f"Screenshot saved to {path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save screenshot: {e}")
            return False


# Alternative implementation using socket-based VNC
class SocketVNCCapturer:
    """
    Lower-level VNC capturer using direct socket communication.
    Fallback if vncdotool is not available.
    """

    def __init__(self, host: str, port: int = 5900, password: str = ''):
        self.host = host
        self.port = port
        self.password = password
        self._socket = None
        self._resolution = None

    def connect(self) -> bool:
        """Connect using raw socket protocol."""
        import socket
        import struct

        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(10)
            self._socket.connect((self.host, self.port))

            # RFB protocol version
            version = self._socket.recv(12)
            logger.debug(f"Server version: {version}")

            # Send our version
            self._socket.send(b'RFB 003.008\n')

            # Security handshake (simplified)
            # This would need full implementation for production

            return True

        except Exception as e:
            logger.error(f"Socket VNC connection failed: {e}")
            return False

    def disconnect(self):
        if self._socket:
            self._socket.close()
            self._socket = None
