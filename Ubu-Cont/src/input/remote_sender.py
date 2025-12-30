"""
Remote Command Sender

Sends mouse and keyboard commands to the Proxmox host's HID controller.
"""

import socket
import json
import logging
import threading
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SenderStats:
    """Statistics about command sending."""
    commands_sent: int = 0
    errors: int = 0
    reconnects: int = 0
    last_send_time: float = 0.0


class RemoteSender:
    """
    Sends HID commands to the Proxmox host controller.

    Maintains TCP connections to mouse and keyboard ports.
    """

    def __init__(
        self,
        host: str = '192.168.100.1',
        mouse_port: int = 8888,
        keyboard_port: int = 8889,
        timeout: float = 5.0,
        auto_reconnect: bool = True
    ):
        """
        Initialize remote sender.

        Args:
            host: HID controller host
            mouse_port: Mouse command port
            keyboard_port: Keyboard command port
            timeout: Socket timeout
            auto_reconnect: Automatically reconnect on failure
        """
        self.host = host
        self.mouse_port = mouse_port
        self.keyboard_port = keyboard_port
        self.timeout = timeout
        self.auto_reconnect = auto_reconnect

        self._mouse_socket: Optional[socket.socket] = None
        self._keyboard_socket: Optional[socket.socket] = None
        self._lock = threading.Lock()
        self._connected = False

        self.stats = SenderStats()

    def connect(self) -> bool:
        """
        Connect to HID controller.

        Returns:
            True if both connections successful
        """
        try:
            # Connect mouse socket
            self._mouse_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._mouse_socket.settimeout(self.timeout)
            self._mouse_socket.connect((self.host, self.mouse_port))
            logger.info(f"Connected to mouse port {self.host}:{self.mouse_port}")

            # Connect keyboard socket
            self._keyboard_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._keyboard_socket.settimeout(self.timeout)
            self._keyboard_socket.connect((self.host, self.keyboard_port))
            logger.info(f"Connected to keyboard port {self.host}:{self.keyboard_port}")

            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.disconnect()
            return False

    def disconnect(self) -> None:
        """Disconnect from HID controller."""
        self._connected = False

        if self._mouse_socket:
            try:
                self._mouse_socket.close()
            except Exception:
                pass
            self._mouse_socket = None

        if self._keyboard_socket:
            try:
                self._keyboard_socket.close()
            except Exception:
                pass
            self._keyboard_socket = None

        logger.info("Disconnected from HID controller")

    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    def _ensure_connected(self) -> bool:
        """Ensure connection is active, reconnect if needed."""
        if self._connected:
            return True

        if self.auto_reconnect:
            logger.info("Reconnecting to HID controller...")
            self.stats.reconnects += 1
            return self.connect()

        return False

    def _send(self, sock: socket.socket, command: Dict[str, Any]) -> bool:
        """
        Send a command over a socket.

        Args:
            sock: Socket to send on
            command: Command dictionary

        Returns:
            True if sent successfully
        """
        if not sock:
            return False

        with self._lock:
            try:
                # Add timestamp
                command['timestamp'] = datetime.now().isoformat()

                # Send as JSON with newline delimiter
                data = json.dumps(command) + '\n'
                sock.send(data.encode('utf-8'))

                self.stats.commands_sent += 1
                self.stats.last_send_time = time.time()
                return True

            except Exception as e:
                logger.error(f"Send failed: {e}")
                self.stats.errors += 1
                self._connected = False
                return False

    def send_mouse_move(self, x: int, y: int) -> bool:
        """
        Send mouse movement command.

        Args:
            x: Relative X movement
            y: Relative Y movement

        Returns:
            True if sent successfully
        """
        if not self._ensure_connected():
            return False

        command = {
            'type': 'mouse_move',
            'x': int(x),
            'y': int(y),
        }
        return self._send(self._mouse_socket, command)

    def send_mouse_button(self, button: str, action: str) -> bool:
        """
        Send mouse button command.

        Args:
            button: 'left', 'right', or 'middle'
            action: 'down' or 'up'

        Returns:
            True if sent successfully
        """
        if not self._ensure_connected():
            return False

        command = {
            'type': 'mouse_button',
            'button': button,
            'action': action,
        }
        return self._send(self._mouse_socket, command)

    def send_mouse_wheel(self, delta: int, horizontal: bool = False) -> bool:
        """
        Send mouse wheel command.

        Args:
            delta: Scroll amount (positive = down/right)
            horizontal: If True, horizontal scroll

        Returns:
            True if sent successfully
        """
        if not self._ensure_connected():
            return False

        command = {
            'type': 'mouse_wheel',
            'delta': int(delta),
            'horizontal': horizontal,
        }
        return self._send(self._mouse_socket, command)

    def send_key(self, key: str, action: str) -> bool:
        """
        Send keyboard key command.

        Args:
            key: Key name or character
            action: 'down', 'up', or 'press'

        Returns:
            True if sent successfully
        """
        if not self._ensure_connected():
            return False

        command = {
            'type': 'keyboard',
            'key': key,
            'action': action,
        }
        return self._send(self._keyboard_socket, command)

    def get_stats(self) -> Dict[str, Any]:
        """Get sender statistics."""
        return {
            'connected': self._connected,
            'commands_sent': self.stats.commands_sent,
            'errors': self.stats.errors,
            'reconnects': self.stats.reconnects,
            'last_send': self.stats.last_send_time,
        }

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False


class MockSender:
    """
    Mock sender for testing without actual connection.
    """

    def __init__(self):
        self.commands = []
        self._connected = True

    def connect(self) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return self._connected

    def send_mouse_move(self, x: int, y: int) -> bool:
        self.commands.append(('mouse_move', x, y))
        return True

    def send_mouse_button(self, button: str, action: str) -> bool:
        self.commands.append(('mouse_button', button, action))
        return True

    def send_mouse_wheel(self, delta: int, horizontal: bool = False) -> bool:
        self.commands.append(('mouse_wheel', delta, horizontal))
        return True

    def send_key(self, key: str, action: str) -> bool:
        self.commands.append(('key', key, action))
        return True

    def clear(self):
        self.commands.clear()


class BatchSender:
    """
    Batches commands for efficient sending.

    Useful when many small movements need to be sent.
    """

    def __init__(self, sender: RemoteSender, batch_size: int = 10):
        """
        Initialize batch sender.

        Args:
            sender: Underlying RemoteSender
            batch_size: Commands to batch before sending
        """
        self.sender = sender
        self.batch_size = batch_size
        self._batch = []
        self._lock = threading.Lock()

    def add_mouse_move(self, x: int, y: int) -> None:
        """Add mouse movement to batch."""
        with self._lock:
            self._batch.append(('mouse_move', x, y))
            if len(self._batch) >= self.batch_size:
                self.flush()

    def flush(self) -> None:
        """Send all batched commands."""
        with self._lock:
            for cmd_type, *args in self._batch:
                if cmd_type == 'mouse_move':
                    self.sender.send_mouse_move(args[0], args[1])
                elif cmd_type == 'mouse_button':
                    self.sender.send_mouse_button(args[0], args[1])
                elif cmd_type == 'key':
                    self.sender.send_key(args[0], args[1])
            self._batch.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
        return False
