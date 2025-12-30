#!/usr/bin/env python3
"""
HID Controller - TCP Socket Interface for Virtual HID Devices

Listens on TCP sockets for mouse (8888) and keyboard (8889) commands
from the Ubuntu AI Controller VM and converts them to HID reports.

Includes configurable human-like timing jitter at the lowest level.
"""

import socket
import json
import threading
import time
import random
import logging
import signal
import sys
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime

from create_virtual_hid import VirtualHIDManager, send_mouse_report, send_keyboard_report
from device_descriptors import KEY_CODES, MODIFIER_MASKS, get_key_code
from logitech_spoofing import default_config


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('hid_controller')


@dataclass
class JitterConfig:
    """Configuration for human-like timing jitter."""
    enabled: bool = True
    min_delay_ms: float = 1.0   # Minimum random delay
    max_delay_ms: float = 5.0   # Maximum random delay
    movement_jitter_px: int = 2  # Random pixel offset on movements


class HIDController:
    """
    Main HID Controller that manages virtual devices and socket listeners.

    Receives JSON commands via TCP and injects them as HID events.
    """

    def __init__(self,
                 mouse_port: int = 8888,
                 keyboard_port: int = 8889,
                 bind_address: str = '0.0.0.0',
                 jitter_config: JitterConfig = None):
        self.mouse_port = mouse_port
        self.keyboard_port = keyboard_port
        self.bind_address = bind_address
        self.jitter = jitter_config or JitterConfig()

        self.hid_manager: Optional[VirtualHIDManager] = None
        self.mouse_socket: Optional[socket.socket] = None
        self.keyboard_socket: Optional[socket.socket] = None

        self._running = False
        self._threads: list[threading.Thread] = []

        # Track button states for proper press/release
        self._mouse_buttons = 0
        self._keyboard_modifiers = 0
        self._keyboard_keys: list[int] = []

        # Statistics
        self.stats = {
            'mouse_commands': 0,
            'keyboard_commands': 0,
            'errors': 0,
            'start_time': None,
        }

    def start(self) -> None:
        """Start the HID controller."""
        logger.info("Starting HID Controller...")

        # Create virtual HID devices
        self.hid_manager = VirtualHIDManager(default_config)
        self.hid_manager.create_devices()

        # Create and bind sockets
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

        logger.info("HID Controller started successfully")

    def stop(self) -> None:
        """Stop the HID controller."""
        logger.info("Stopping HID Controller...")
        self._running = False

        # Close sockets
        if self.mouse_socket:
            self.mouse_socket.close()
        if self.keyboard_socket:
            self.keyboard_socket.close()

        # Destroy virtual devices
        if self.hid_manager:
            self.hid_manager.destroy_devices()

        logger.info("HID Controller stopped")

    def _create_socket(self, port: int) -> socket.socket:
        """Create and configure a TCP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.bind_address, port))
        sock.listen(5)
        return sock

    def _accept_connections(self, server_socket: socket.socket,
                           handler: Callable[[Dict[str, Any]], None]) -> None:
        """Accept and handle client connections."""
        while self._running:
            try:
                server_socket.settimeout(1.0)
                try:
                    client, addr = server_socket.accept()
                except socket.timeout:
                    continue

                logger.info(f"Client connected from {addr}")

                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client, handler),
                    daemon=True
                )
                client_thread.start()

            except OSError:
                if self._running:
                    logger.error("Socket error")
                break

    def _handle_client(self, client: socket.socket,
                       handler: Callable[[Dict[str, Any]], None]) -> None:
        """Handle a single client connection."""
        buffer = ""
        client.settimeout(0.5)

        while self._running:
            try:
                data = client.recv(4096)
                if not data:
                    break

                buffer += data.decode('utf-8')

                # Process complete JSON messages (newline-delimited)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        try:
                            cmd = json.loads(line)
                            handler(cmd)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON: {line[:100]}")
                            self.stats['errors'] += 1

            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Client error: {e}")
                break

        client.close()
        logger.info("Client disconnected")

    def _apply_jitter(self) -> None:
        """Apply random timing jitter for human-like behavior."""
        if self.jitter.enabled:
            delay = random.uniform(
                self.jitter.min_delay_ms / 1000,
                self.jitter.max_delay_ms / 1000
            )
            time.sleep(delay)

    def _handle_mouse_command(self, cmd: Dict[str, Any]) -> None:
        """Handle a mouse command."""
        cmd_type = cmd.get('type')
        self.stats['mouse_commands'] += 1

        self._apply_jitter()

        try:
            if cmd_type == 'mouse_move':
                x = cmd.get('x', 0)
                y = cmd.get('y', 0)

                # Add movement jitter
                if self.jitter.enabled:
                    x += random.randint(-self.jitter.movement_jitter_px,
                                        self.jitter.movement_jitter_px)
                    y += random.randint(-self.jitter.movement_jitter_px,
                                        self.jitter.movement_jitter_px)

                send_mouse_report(
                    self.hid_manager.mouse,
                    buttons=self._mouse_buttons,
                    x=x,
                    y=y
                )

            elif cmd_type == 'mouse_button':
                button = cmd.get('button', 'left')
                action = cmd.get('action', 'down')

                button_bits = {
                    'left': 0x01,
                    'right': 0x02,
                    'middle': 0x04,
                    'button4': 0x08,
                    'button5': 0x10
                }

                bit = button_bits.get(button, 0x01)

                if action == 'down':
                    self._mouse_buttons |= bit
                elif action == 'up':
                    self._mouse_buttons &= ~bit

                send_mouse_report(
                    self.hid_manager.mouse,
                    buttons=self._mouse_buttons
                )

            elif cmd_type == 'mouse_wheel':
                delta = cmd.get('delta', 0)
                horizontal = cmd.get('horizontal', False)

                if horizontal:
                    send_mouse_report(
                        self.hid_manager.mouse,
                        buttons=self._mouse_buttons,
                        hwheel=delta
                    )
                else:
                    send_mouse_report(
                        self.hid_manager.mouse,
                        buttons=self._mouse_buttons,
                        wheel=delta
                    )

        except Exception as e:
            logger.error(f"Mouse command error: {e}")
            self.stats['errors'] += 1

    def _handle_keyboard_command(self, cmd: Dict[str, Any]) -> None:
        """Handle a keyboard command."""
        cmd_type = cmd.get('type')
        self.stats['keyboard_commands'] += 1

        self._apply_jitter()

        try:
            if cmd_type == 'keyboard':
                key = cmd.get('key', '')
                action = cmd.get('action', 'press')

                # Get key code
                key_code, needs_shift = get_key_code(key)

                if key_code == 0:
                    logger.warning(f"Unknown key: {key}")
                    return

                # Check if it's a modifier key
                if key.lower() in MODIFIER_MASKS:
                    mod_bit = MODIFIER_MASKS[key.lower()]

                    if action in ('down', 'press'):
                        self._keyboard_modifiers |= mod_bit
                    if action in ('up', 'press'):
                        if action == 'press':
                            # For press, we need to send down then up
                            send_keyboard_report(
                                self.hid_manager.keyboard,
                                modifiers=self._keyboard_modifiers,
                                keys=self._keyboard_keys
                            )
                            time.sleep(0.05)
                        self._keyboard_modifiers &= ~mod_bit

                    send_keyboard_report(
                        self.hid_manager.keyboard,
                        modifiers=self._keyboard_modifiers,
                        keys=self._keyboard_keys
                    )
                else:
                    # Regular key
                    if needs_shift:
                        self._keyboard_modifiers |= MODIFIER_MASKS['shift']

                    if action in ('down', 'press'):
                        if key_code not in self._keyboard_keys:
                            self._keyboard_keys.append(key_code)
                            if len(self._keyboard_keys) > 6:
                                self._keyboard_keys = self._keyboard_keys[-6:]

                        send_keyboard_report(
                            self.hid_manager.keyboard,
                            modifiers=self._keyboard_modifiers,
                            keys=self._keyboard_keys
                        )

                    if action in ('up', 'press'):
                        if action == 'press':
                            time.sleep(0.05)  # Brief press duration

                        if key_code in self._keyboard_keys:
                            self._keyboard_keys.remove(key_code)

                        if needs_shift:
                            self._keyboard_modifiers &= ~MODIFIER_MASKS['shift']

                        send_keyboard_report(
                            self.hid_manager.keyboard,
                            modifiers=self._keyboard_modifiers,
                            keys=self._keyboard_keys
                        )

        except Exception as e:
            logger.error(f"Keyboard command error: {e}")
            self.stats['errors'] += 1

    def get_status(self) -> Dict[str, Any]:
        """Get controller status and statistics."""
        uptime = None
        if self.stats['start_time']:
            uptime = str(datetime.now() - self.stats['start_time'])

        return {
            'running': self._running,
            'uptime': uptime,
            'mouse_port': self.mouse_port,
            'keyboard_port': self.keyboard_port,
            'stats': {
                'mouse_commands': self.stats['mouse_commands'],
                'keyboard_commands': self.stats['keyboard_commands'],
                'errors': self.stats['errors'],
            },
            'devices': {
                'mouse': bool(self.hid_manager and self.hid_manager.mouse),
                'keyboard': bool(self.hid_manager and self.hid_manager.keyboard),
            },
            'jitter': {
                'enabled': self.jitter.enabled,
                'min_delay_ms': self.jitter.min_delay_ms,
                'max_delay_ms': self.jitter.max_delay_ms,
            }
        }


def main():
    """Main entry point."""
    controller = HIDController(
        mouse_port=8888,
        keyboard_port=8889,
        bind_address='0.0.0.0',
        jitter_config=JitterConfig(
            enabled=True,
            min_delay_ms=1.0,
            max_delay_ms=5.0,
            movement_jitter_px=2
        )
    )

    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        controller.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    controller.start()

    print("\nHID Controller running. Press Ctrl+C to stop.")
    print(f"Mouse port: {controller.mouse_port}")
    print(f"Keyboard port: {controller.keyboard_port}")
    print("\nTest with:")
    print(f"  echo '{{\"type\":\"mouse_move\",\"x\":10,\"y\":0}}' | nc localhost {controller.mouse_port}")
    print(f"  echo '{{\"type\":\"keyboard\",\"key\":\"a\",\"action\":\"press\"}}' | nc localhost {controller.keyboard_port}")

    # Keep running
    try:
        while True:
            time.sleep(60)
            status = controller.get_status()
            logger.info(f"Status: {status['stats']}")
    except KeyboardInterrupt:
        pass

    controller.stop()


if __name__ == '__main__':
    main()
