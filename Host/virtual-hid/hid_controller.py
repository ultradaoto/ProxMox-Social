#!/usr/bin/env python3
"""
HID Controller - QMP-based Input Injection for QEMU VMs

Listens on TCP sockets for mouse (8888) and keyboard (8889) commands
from the Ubuntu AI Controller VM and injects them via QMP into Windows VM.

IMPORTANT: QEMU's HID Tablet uses ABSOLUTE coordinates (0-32767 range).
This controller tracks mouse position and converts relative moves to absolute.
"""

import socket
import json
import threading
import time
import random
import logging
import signal
import sys
import os
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from datetime import datetime

# Configure logging - both to file and stdout
LOG_FILE = '/tmp/input-router-debug.log'

# Create file handler
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
))

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Configure root logger
logger = logging.getLogger('hid_controller')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


# QMP coordinate system: 0-32767 for both X and Y
QMP_MAX_COORD = 32767

# Windows VM screen resolution - MUST MATCH ACTUAL RESOLUTION
SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 1200


# QMP Key codes (QEMU qcodes)
QCODE_MAP = {
    # Letters
    'a': 'a', 'b': 'b', 'c': 'c', 'd': 'd', 'e': 'e', 'f': 'f', 'g': 'g',
    'h': 'h', 'i': 'i', 'j': 'j', 'k': 'k', 'l': 'l', 'm': 'm', 'n': 'n',
    'o': 'o', 'p': 'p', 'q': 'q', 'r': 'r', 's': 's', 't': 't', 'u': 'u',
    'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y', 'z': 'z',
    # Numbers
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4',
    '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    # Function keys
    'f1': 'f1', 'f2': 'f2', 'f3': 'f3', 'f4': 'f4', 'f5': 'f5', 'f6': 'f6',
    'f7': 'f7', 'f8': 'f8', 'f9': 'f9', 'f10': 'f10', 'f11': 'f11', 'f12': 'f12',
    # Modifiers
    'shift': 'shift', 'lshift': 'shift', 'rshift': 'shift_r',
    'ctrl': 'ctrl', 'lctrl': 'ctrl', 'rctrl': 'ctrl_r',
    'alt': 'alt', 'lalt': 'alt', 'ralt': 'alt_r',
    'meta': 'meta_l', 'lmeta': 'meta_l', 'rmeta': 'meta_r',
    'win': 'meta_l', 'super': 'meta_l',
    # Special keys
    'space': 'spc', ' ': 'spc',
    'enter': 'ret', 'return': 'ret', '\n': 'ret',
    'tab': 'tab', '\t': 'tab',
    'backspace': 'backspace', 'bs': 'backspace',
    'escape': 'esc', 'esc': 'esc',
    'insert': 'insert', 'ins': 'insert',
    'delete': 'delete', 'del': 'delete',
    'home': 'home', 'end': 'end',
    'pageup': 'pgup', 'pgup': 'pgup',
    'pagedown': 'pgdn', 'pgdn': 'pgdn',
    'up': 'up', 'down': 'down', 'left': 'left', 'right': 'right',
    'capslock': 'caps_lock', 'caps': 'caps_lock',
    'numlock': 'num_lock', 'scrolllock': 'scroll_lock',
    'printscreen': 'print', 'prtsc': 'print',
    'pause': 'pause',
    # Punctuation
    '-': 'minus', '=': 'equal', '[': 'bracket_left', ']': 'bracket_right',
    '\\': 'backslash', ';': 'semicolon', "'": 'apostrophe', '`': 'grave_accent',
    ',': 'comma', '.': 'dot', '/': 'slash',
    # Shifted symbols (need shift modifier)
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5',
    '^': '6', '&': '7', '*': '8', '(': '9', ')': '0',
    '_': 'minus', '+': 'equal', '{': 'bracket_left', '}': 'bracket_right',
    '|': 'backslash', ':': 'semicolon', '"': 'apostrophe', '~': 'grave_accent',
    '<': 'comma', '>': 'dot', '?': 'slash',
}

SHIFT_CHARS = set('!@#$%^&*()_+{}|:"<>?~ABCDEFGHIJKLMNOPQRSTUVWXYZ')


@dataclass
class JitterConfig:
    """Configuration for human-like timing jitter."""
    enabled: bool = True
    min_delay_ms: float = 1.0
    max_delay_ms: float = 5.0
    movement_jitter_px: int = 2


class QMPConnection:
    """Manages connection to QEMU Monitor Protocol socket."""

    def __init__(self, socket_path: str):
        self.socket_path = socket_path
        self.sock: Optional[socket.socket] = None
        self.lock = threading.Lock()
        self._initialized = False

    def connect(self) -> bool:
        """Connect to QMP socket and initialize."""
        try:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect(self.socket_path)

            # Read greeting
            greeting = self._recv_json()
            logger.debug(f"QMP greeting: {greeting}")
            if not greeting or 'QMP' not in greeting:
                logger.error(f"Invalid QMP greeting: {greeting}")
                return False

            # Send capabilities
            self._send_json({"execute": "qmp_capabilities"})
            response = self._recv_json()
            logger.debug(f"QMP capabilities response: {response}")

            if response and 'return' in response:
                self._initialized = True
                logger.info(f"QMP connected to {self.socket_path}")
                return True

            logger.error(f"QMP capabilities failed: {response}")
            return False

        except Exception as e:
            logger.error(f"QMP connection error: {e}")
            return False

    def disconnect(self):
        """Disconnect from QMP socket."""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
            self.sock = None
        self._initialized = False

    def _send_json(self, data: dict):
        """Send JSON command to QMP."""
        msg = json.dumps(data) + '\n'
        self.sock.sendall(msg.encode())
        logger.debug(f"QMP SEND: {msg.strip()}")

    def _recv_json(self) -> Optional[dict]:
        """Receive JSON response from QMP."""
        try:
            data = b''
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:
                    break

            if data:
                for line in data.decode().strip().split('\n'):
                    if line:
                        result = json.loads(line)
                        logger.debug(f"QMP RECV: {line}")
                        return result
            return None
        except socket.timeout:
            return None
        except json.JSONDecodeError as e:
            logger.error(f"QMP JSON decode error: {e}")
            return None

    def send_input_event(self, events: List[dict]) -> bool:
        """Send input events via QMP."""
        if not self._initialized:
            logger.warning("QMP not initialized, attempting reconnect...")
            if not self.connect():
                return False

        with self.lock:
            try:
                cmd = {
                    "execute": "input-send-event",
                    "arguments": {"events": events}
                }
                self._send_json(cmd)

                # Read response
                self.sock.settimeout(0.5)
                try:
                    response = self._recv_json()
                    if response and 'error' in response:
                        logger.error(f"QMP error: {response['error']}")
                        return False
                    logger.debug(f"QMP input-send-event success")
                    return True
                except socket.timeout:
                    # No response is often OK for input events
                    return True

            except BrokenPipeError:
                logger.warning("QMP connection lost, reconnecting...")
                self._initialized = False
                return False
            except Exception as e:
                logger.error(f"QMP send error: {e}")
                return False


class MousePositionTracker:
    """Tracks mouse position for relative-to-absolute conversion."""

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        # Start at center
        self.x = screen_width // 2
        self.y = screen_height // 2
        self.lock = threading.Lock()

    def move_relative(self, dx: int, dy: int) -> tuple:
        """Apply relative movement and return new absolute position."""
        with self.lock:
            self.x = max(0, min(self.screen_width - 1, self.x + dx))
            self.y = max(0, min(self.screen_height - 1, self.y + dy))
            return self.x, self.y

    def set_absolute(self, x: int, y: int):
        """Set absolute position (in screen coordinates)."""
        with self.lock:
            self.x = max(0, min(self.screen_width - 1, x))
            self.y = max(0, min(self.screen_height - 1, y))

    def get_position(self) -> tuple:
        """Get current position."""
        with self.lock:
            return self.x, self.y

    def to_qmp_coords(self, x: int, y: int) -> tuple:
        """Convert screen coordinates to QMP coordinates (0-32767)."""
        qmp_x = int((x / self.screen_width) * QMP_MAX_COORD)
        qmp_y = int((y / self.screen_height) * QMP_MAX_COORD)
        return qmp_x, qmp_y


class HIDController:
    """
    QMP-based HID Controller with absolute positioning support.

    QEMU's HID Tablet uses absolute coordinates (0-32767 range).
    This controller tracks mouse position and converts relative moves to absolute.
    """

    def __init__(self,
                 mouse_port: int = 8888,
                 keyboard_port: int = 8889,
                 bind_address: str = '0.0.0.0',
                 qmp_socket: str = '/var/run/qemu-server/101.qmp',
                 jitter_config: JitterConfig = None,
                 screen_width: int = 1920,
                 screen_height: int = 1080):
        self.mouse_port = mouse_port
        self.keyboard_port = keyboard_port
        self.bind_address = bind_address
        self.qmp_socket = qmp_socket
        self.jitter = jitter_config or JitterConfig()

        self.qmp: Optional[QMPConnection] = None
        self.mouse_socket: Optional[socket.socket] = None
        self.keyboard_socket: Optional[socket.socket] = None

        # Mouse position tracker for relative-to-absolute conversion
        self.mouse_tracker = MousePositionTracker(screen_width, screen_height)

        self._running = False
        self._threads: list[threading.Thread] = []
        self._client_addr: Optional[str] = None

        # Statistics
        self.stats = {
            'mouse_commands': 0,
            'keyboard_commands': 0,
            'errors': 0,
            'start_time': None,
        }

    def start(self) -> None:
        """Start the HID controller."""
        logger.info("=" * 60)
        logger.info("Starting QMP-based HID Controller")
        logger.info(f"Screen resolution: {self.mouse_tracker.screen_width}x{self.mouse_tracker.screen_height}")
        logger.info(f"QMP coordinate range: 0-{QMP_MAX_COORD}")
        logger.info("=" * 60)

        # Connect to QMP
        self.qmp = QMPConnection(self.qmp_socket)
        if not self.qmp.connect():
            raise RuntimeError(f"Failed to connect to QMP socket: {self.qmp_socket}")

        # Create and bind TCP sockets
        self.mouse_socket = self._create_socket(self.mouse_port)
        self.keyboard_socket = self._create_socket(self.keyboard_port)

        logger.info(f"Mouse listener on {self.bind_address}:{self.mouse_port}")
        logger.info(f"Keyboard listener on {self.bind_address}:{self.keyboard_port}")

        self._running = True
        self.stats['start_time'] = datetime.now()

        # Start listener threads
        mouse_thread = threading.Thread(
            target=self._accept_connections,
            args=(self.mouse_socket, self._handle_mouse_command),
            name='MouseListener'
        )
        keyboard_thread = threading.Thread(
            target=self._accept_connections,
            args=(self.keyboard_socket, self._handle_keyboard_command),
            name='KeyboardListener'
        )

        mouse_thread.daemon = True
        keyboard_thread.daemon = True

        mouse_thread.start()
        keyboard_thread.start()

        self._threads = [mouse_thread, keyboard_thread]

        logger.info("QMP HID Controller started successfully")
        logger.info(f"Injecting input into VM via {self.qmp_socket}")

    def stop(self) -> None:
        """Stop the HID controller."""
        logger.info("Stopping HID Controller...")
        self._running = False

        if self.mouse_socket:
            self.mouse_socket.close()
        if self.keyboard_socket:
            self.keyboard_socket.close()
        if self.qmp:
            self.qmp.disconnect()

        logger.info("HID Controller stopped")

    def _create_socket(self, port: int) -> socket.socket:
        """Create and configure a TCP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bind_address, port))
        sock.listen(5)
        return sock

    def _accept_connections(self, server_socket: socket.socket,
                           handler: Callable[[Dict[str, Any], str], None]) -> None:
        """Accept and handle client connections."""
        while self._running:
            try:
                server_socket.settimeout(1.0)
                try:
                    client, addr = server_socket.accept()
                except socket.timeout:
                    continue

                client_ip = addr[0]
                logger.info(f"Client connected from {client_ip}:{addr[1]}")

                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client, handler, client_ip),
                    daemon=True
                )
                client_thread.start()

            except OSError:
                if self._running:
                    logger.error("Socket error")
                break

    def _handle_client(self, client: socket.socket,
                       handler: Callable[[Dict[str, Any], str], None],
                       client_ip: str) -> None:
        """Handle a single client connection."""
        buffer = ""
        client.settimeout(0.5)

        while self._running:
            try:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')

                # Process complete JSON messages
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_json(line.strip(), handler, client_ip)

                # Handle non-newline terminated JSON
                if buffer.strip():
                    try:
                        json.loads(buffer.strip())
                        self._process_json(buffer.strip(), handler, client_ip)
                        buffer = ""
                    except json.JSONDecodeError:
                        pass

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Client error: {e}")
                break

        client.close()
        logger.info(f"Client {client_ip} disconnected")

    def _process_json(self, line: str, handler: Callable, client_ip: str):
        """Process a JSON command line."""
        try:
            cmd = json.loads(line)
            logger.info(f"RECV from {client_ip}: {line}")
            handler(cmd, client_ip)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON from {client_ip}: {line[:100]} - {e}")
            self.stats['errors'] += 1

    def _apply_jitter(self) -> None:
        """Apply random timing jitter for human-like behavior."""
        if self.jitter.enabled:
            delay = random.uniform(
                self.jitter.min_delay_ms / 1000,
                self.jitter.max_delay_ms / 1000
            )
            time.sleep(delay)

    def _handle_mouse_command(self, cmd: Dict[str, Any], client_ip: str) -> None:
        """Handle a mouse command via QMP."""
        cmd_type = cmd.get('type', '')
        self.stats['mouse_commands'] += 1
        self._apply_jitter()

        try:
            # Support multiple command formats for RELATIVE movement
            if cmd_type in ('mouse_move', 'move', 'rel'):
                dx = int(cmd.get('x', 0))
                dy = int(cmd.get('y', 0))

                if self.jitter.enabled and (dx != 0 or dy != 0):
                    dx += random.randint(-self.jitter.movement_jitter_px,
                                        self.jitter.movement_jitter_px)
                    dy += random.randint(-self.jitter.movement_jitter_px,
                                        self.jitter.movement_jitter_px)

                logger.info(f"PARSED: relative move dx={dx}, dy={dy}")

                # Convert relative to absolute
                new_x, new_y = self.mouse_tracker.move_relative(dx, dy)
                qmp_x, qmp_y = self.mouse_tracker.to_qmp_coords(new_x, new_y)

                logger.info(f"CONVERTED: screen({new_x},{new_y}) -> QMP({qmp_x},{qmp_y})")

                events = [
                    {"type": "abs", "data": {"axis": "x", "value": qmp_x}},
                    {"type": "abs", "data": {"axis": "y", "value": qmp_y}}
                ]

                success = self.qmp.send_input_event(events)
                logger.info(f"QMP RESULT: {'SUCCESS' if success else 'FAILED'}")

            # ABSOLUTE positioning (screen coordinates)
            elif cmd_type == 'abs':
                x = int(cmd.get('x', 0))
                y = int(cmd.get('y', 0))

                # Values > QMP_MAX are invalid, clamp them
                # Values in screen range (0-1920, 0-1080) are screen coordinates
                # Values > screen range but < QMP_MAX are treated as raw QMP
                if x > QMP_MAX_COORD:
                    x = QMP_MAX_COORD
                if y > QMP_MAX_COORD:
                    y = QMP_MAX_COORD

                if x <= self.mouse_tracker.screen_width and y <= self.mouse_tracker.screen_height:
                    # Treat as screen coordinates
                    self.mouse_tracker.set_absolute(x, y)
                    qmp_x, qmp_y = self.mouse_tracker.to_qmp_coords(x, y)
                    logger.info(f"PARSED: absolute screen ({x},{y}) -> QMP({qmp_x},{qmp_y})")
                else:
                    # Treat as raw QMP coordinates (0-32767 range)
                    qmp_x, qmp_y = x, y
                    logger.info(f"PARSED: absolute QMP ({qmp_x},{qmp_y})")

                events = [
                    {"type": "abs", "data": {"axis": "x", "value": qmp_x}},
                    {"type": "abs", "data": {"axis": "y", "value": qmp_y}}
                ]

                success = self.qmp.send_input_event(events)
                logger.info(f"QMP RESULT: {'SUCCESS' if success else 'FAILED'}")

            elif cmd_type in ('mouse_button', 'button', 'click'):
                button = cmd.get('button', 'left')
                action = cmd.get('action', 'click')

                logger.info(f"PARSED: button={button}, action={action}")

                button_map = {
                    'left': 'left',
                    'right': 'right',
                    'middle': 'middle',
                }
                qmp_button = button_map.get(button, 'left')

                if action == 'click':
                    self.qmp.send_input_event([
                        {"type": "btn", "data": {"button": qmp_button, "down": True}}
                    ])
                    time.sleep(0.05)
                    self.qmp.send_input_event([
                        {"type": "btn", "data": {"button": qmp_button, "down": False}}
                    ])
                    logger.info("QMP RESULT: click complete")
                elif action == 'down':
                    self.qmp.send_input_event([
                        {"type": "btn", "data": {"button": qmp_button, "down": True}}
                    ])
                elif action == 'up':
                    self.qmp.send_input_event([
                        {"type": "btn", "data": {"button": qmp_button, "down": False}}
                    ])

            elif cmd_type in ('mouse_wheel', 'wheel', 'scroll'):
                delta = int(cmd.get('delta', 0))
                logger.info(f"PARSED: scroll delta={delta}")

                if delta > 0:
                    for _ in range(abs(delta)):
                        self.qmp.send_input_event([
                            {"type": "btn", "data": {"button": "wheel-up", "down": True}},
                            {"type": "btn", "data": {"button": "wheel-up", "down": False}}
                        ])
                elif delta < 0:
                    for _ in range(abs(delta)):
                        self.qmp.send_input_event([
                            {"type": "btn", "data": {"button": "wheel-down", "down": True}},
                            {"type": "btn", "data": {"button": "wheel-down", "down": False}}
                        ])

            else:
                logger.warning(f"Unknown mouse command type: {cmd_type}")

        except Exception as e:
            logger.error(f"Mouse command error: {e}")
            self.stats['errors'] += 1

    def _handle_keyboard_command(self, cmd: Dict[str, Any], client_ip: str) -> None:
        """Handle a keyboard command via QMP."""
        cmd_type = cmd.get('type', '')
        self.stats['keyboard_commands'] += 1
        self._apply_jitter()

        try:
            if cmd_type in ('keyboard', 'key'):
                key = cmd.get('key', '')
                action = cmd.get('action', 'press')
                logger.info(f"PARSED: key={key}, action={action}")
                self._send_key(key, action)

            elif cmd_type == 'text':
                text = cmd.get('text', '')
                logger.info(f"PARSED: text=\"{text}\" ({len(text)} chars)")
                for char in text:
                    self._send_key(char, 'press')
                    time.sleep(0.02)

            else:
                logger.warning(f"Unknown keyboard command type: {cmd_type}")

        except Exception as e:
            logger.error(f"Keyboard command error: {e}")
            self.stats['errors'] += 1

    def _send_key(self, key: str, action: str) -> None:
        """Send a single key via QMP."""
        needs_shift = key in SHIFT_CHARS
        qcode = QCODE_MAP.get(key.lower(), key.lower())

        logger.debug(f"Key '{key}' -> qcode '{qcode}', needs_shift={needs_shift}")

        if action == 'press':
            if needs_shift:
                self.qmp.send_input_event([
                    {"type": "key", "data": {"key": {"type": "qcode", "data": "shift"}, "down": True}}
                ])

            self.qmp.send_input_event([
                {"type": "key", "data": {"key": {"type": "qcode", "data": qcode}, "down": True}}
            ])
            time.sleep(0.03)
            self.qmp.send_input_event([
                {"type": "key", "data": {"key": {"type": "qcode", "data": qcode}, "down": False}}
            ])

            if needs_shift:
                self.qmp.send_input_event([
                    {"type": "key", "data": {"key": {"type": "qcode", "data": "shift"}, "down": False}}
                ])

        elif action == 'down':
            if needs_shift:
                self.qmp.send_input_event([
                    {"type": "key", "data": {"key": {"type": "qcode", "data": "shift"}, "down": True}}
                ])
            self.qmp.send_input_event([
                {"type": "key", "data": {"key": {"type": "qcode", "data": qcode}, "down": True}}
            ])

        elif action == 'up':
            self.qmp.send_input_event([
                {"type": "key", "data": {"key": {"type": "qcode", "data": qcode}, "down": False}}
            ])
            if needs_shift:
                self.qmp.send_input_event([
                    {"type": "key", "data": {"key": {"type": "qcode", "data": "shift"}, "down": False}}
                ])

    def get_status(self) -> Dict[str, Any]:
        """Get controller status and statistics."""
        uptime = None
        if self.stats['start_time']:
            uptime = str(datetime.now() - self.stats['start_time'])

        mouse_pos = self.mouse_tracker.get_position()
        qmp_pos = self.mouse_tracker.to_qmp_coords(mouse_pos[0], mouse_pos[1])

        return {
            'running': self._running,
            'uptime': uptime,
            'mouse_port': self.mouse_port,
            'keyboard_port': self.keyboard_port,
            'qmp_socket': self.qmp_socket,
            'qmp_connected': self.qmp._initialized if self.qmp else False,
            'mouse_position': {'screen': mouse_pos, 'qmp': qmp_pos},
            'stats': self.stats.copy(),
            'jitter': {
                'enabled': self.jitter.enabled,
                'min_delay_ms': self.jitter.min_delay_ms,
                'max_delay_ms': self.jitter.max_delay_ms,
            }
        }


def main():
    """Main entry point."""
    qmp_socket = '/var/run/qemu-server/101.qmp'

    if not os.path.exists(qmp_socket):
        qmp_dir = '/var/run/qemu-server/'
        for f in os.listdir(qmp_dir):
            if f.endswith('.qmp'):
                qmp_socket = os.path.join(qmp_dir, f)
                break

    logger.info(f"Using QMP socket: {qmp_socket}")
    logger.info(f"Debug log: {LOG_FILE}")

    controller = HIDController(
        mouse_port=8888,
        keyboard_port=8889,
        bind_address='0.0.0.0',
        qmp_socket=qmp_socket,
        jitter_config=JitterConfig(
            enabled=True,
            min_delay_ms=1.0,
            max_delay_ms=5.0,
            movement_jitter_px=1
        ),
        screen_width=1600,
        screen_height=1200
    )

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    controller.start()

    print("\nQMP HID Controller running. Press Ctrl+C to stop.")
    print(f"Mouse port: {controller.mouse_port}")
    print(f"Keyboard port: {controller.keyboard_port}")
    print(f"QMP socket: {qmp_socket}")
    print(f"Debug log: {LOG_FILE}")
    print("\nTest commands:")
    print(f"  # Relative move (50px right)")
    print(f"  echo '{{\"type\":\"move\",\"x\":50,\"y\":0}}' | nc localhost {controller.mouse_port}")
    print(f"  # Absolute position (center of screen)")
    print(f"  echo '{{\"type\":\"abs\",\"x\":960,\"y\":540}}' | nc localhost {controller.mouse_port}")
    print(f"  # Click")
    print(f"  echo '{{\"type\":\"click\",\"button\":\"left\"}}' | nc localhost {controller.mouse_port}")
    print(f"  # Type text")
    print(f"  printf '{{\"type\":\"text\",\"text\":\"Hello\"}}\\n' | nc localhost {controller.keyboard_port}")

    try:
        while True:
            time.sleep(60)
            status = controller.get_status()
            logger.info(f"Status: mouse={status['stats']['mouse_commands']}, kbd={status['stats']['keyboard_commands']}, pos={status['mouse_position']}")
    except KeyboardInterrupt:
        pass

    controller.stop()


if __name__ == '__main__':
    main()
