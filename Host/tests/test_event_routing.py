#!/usr/bin/env python3
"""
Test suite for HID event routing via TCP sockets.

Run on: Proxmox Host
Requirements: pytest, HID controller running for integration tests
"""

import json
import socket
import time
import threading
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'virtual-hid'))


class TestCommandParsing:
    """Tests for JSON command parsing."""

    def test_mouse_move_command_structure(self):
        """Test mouse move command JSON structure."""
        cmd = {
            'type': 'mouse_move',
            'x': 100,
            'y': 50,
            'timestamp': '2024-01-01T12:00:00'
        }
        assert cmd['type'] == 'mouse_move'
        assert isinstance(cmd['x'], int)
        assert isinstance(cmd['y'], int)

    def test_mouse_button_command_structure(self):
        """Test mouse button command JSON structure."""
        cmd = {
            'type': 'mouse_button',
            'button': 'left',
            'action': 'down',
            'timestamp': '2024-01-01T12:00:00'
        }
        assert cmd['type'] == 'mouse_button'
        assert cmd['button'] in ['left', 'right', 'middle']
        assert cmd['action'] in ['down', 'up']

    def test_mouse_wheel_command_structure(self):
        """Test mouse wheel command JSON structure."""
        cmd = {
            'type': 'mouse_wheel',
            'delta': -120,
            'timestamp': '2024-01-01T12:00:00'
        }
        assert cmd['type'] == 'mouse_wheel'
        assert isinstance(cmd['delta'], int)

    def test_keyboard_command_structure(self):
        """Test keyboard command JSON structure."""
        cmd = {
            'type': 'keyboard',
            'key': 'a',
            'action': 'press',
            'timestamp': '2024-01-01T12:00:00'
        }
        assert cmd['type'] == 'keyboard'
        assert isinstance(cmd['key'], str)
        assert cmd['action'] in ['down', 'up', 'press']

    def test_json_serialization(self):
        """Test that commands serialize correctly."""
        cmd = {'type': 'mouse_move', 'x': 10, 'y': 20}
        serialized = json.dumps(cmd) + '\n'
        deserialized = json.loads(serialized.strip())
        assert deserialized == cmd


class TestJitterConfig:
    """Tests for timing jitter configuration."""

    def test_jitter_config_defaults(self):
        """Test default jitter configuration."""
        from hid_controller import JitterConfig

        config = JitterConfig()
        assert config.enabled is True
        assert config.min_delay_ms >= 0
        assert config.max_delay_ms >= config.min_delay_ms
        assert config.movement_jitter_px >= 0

    def test_jitter_config_disabled(self):
        """Test jitter can be disabled."""
        from hid_controller import JitterConfig

        config = JitterConfig(enabled=False)
        assert config.enabled is False

    def test_jitter_config_custom(self):
        """Test custom jitter configuration."""
        from hid_controller import JitterConfig

        config = JitterConfig(
            enabled=True,
            min_delay_ms=2.0,
            max_delay_ms=10.0,
            movement_jitter_px=5
        )
        assert config.min_delay_ms == 2.0
        assert config.max_delay_ms == 10.0
        assert config.movement_jitter_px == 5


class TestHIDControllerUnit:
    """Unit tests for HID controller (mocked dependencies)."""

    @pytest.fixture
    def mock_hid_manager(self):
        """Create mock HID manager."""
        with patch('hid_controller.VirtualHIDManager') as mock:
            manager = Mock()
            manager.mouse = Mock()
            manager.keyboard = Mock()
            mock.return_value = manager
            yield manager

    def test_controller_initialization(self, mock_hid_manager):
        """Test controller initializes with correct ports."""
        from hid_controller import HIDController

        controller = HIDController(
            mouse_port=8888,
            keyboard_port=8889,
            bind_address='127.0.0.1'
        )
        assert controller.mouse_port == 8888
        assert controller.keyboard_port == 8889
        assert controller.bind_address == '127.0.0.1'

    def test_controller_stats_initialized(self, mock_hid_manager):
        """Test controller statistics are initialized."""
        from hid_controller import HIDController

        controller = HIDController()
        assert controller.stats['mouse_commands'] == 0
        assert controller.stats['keyboard_commands'] == 0
        assert controller.stats['errors'] == 0


class TestSocketCommunication:
    """Tests for TCP socket communication."""

    @pytest.fixture
    def echo_server(self):
        """Create a simple echo server for testing."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))  # Random port
        server.listen(1)
        port = server.getsockname()[1]

        received = []

        def handle_client():
            conn, addr = server.accept()
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                received.append(data.decode())
                conn.send(b'OK\n')
            conn.close()

        thread = threading.Thread(target=handle_client, daemon=True)
        thread.start()

        yield {'server': server, 'port': port, 'received': received}

        server.close()

    def test_send_command(self, echo_server):
        """Test sending a command via socket."""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', echo_server['port']))

        cmd = json.dumps({'type': 'test', 'value': 123}) + '\n'
        client.send(cmd.encode())

        # Wait for response
        response = client.recv(1024)
        assert response == b'OK\n'

        client.close()
        time.sleep(0.1)  # Allow server to process

        # Check received data
        assert len(echo_server['received']) == 1
        received_cmd = json.loads(echo_server['received'][0].strip())
        assert received_cmd['type'] == 'test'

    def test_send_multiple_commands(self, echo_server):
        """Test sending multiple commands in sequence."""
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', echo_server['port']))

        commands = [
            {'type': 'cmd1'},
            {'type': 'cmd2'},
            {'type': 'cmd3'},
        ]

        for cmd in commands:
            client.send((json.dumps(cmd) + '\n').encode())
            client.recv(1024)  # Wait for response

        client.close()
        time.sleep(0.1)

        # All commands should be received
        assert len(echo_server['received']) == 3


class TestIntegration:
    """Integration tests (require running HID controller).

    Run with: pytest -v test_event_routing.py::TestIntegration -m integration
    """

    @pytest.fixture
    def skip_if_no_controller(self):
        """Skip if HID controller is not running."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 8888))
            sock.close()
            if result != 0:
                pytest.skip("HID controller not running on port 8888")
        except Exception:
            pytest.skip("Could not connect to HID controller")

    @pytest.mark.integration
    def test_send_mouse_move(self, skip_if_no_controller):
        """Test sending mouse move command to running controller."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 8888))

        cmd = {
            'type': 'mouse_move',
            'x': 10,
            'y': 5
        }
        sock.send((json.dumps(cmd) + '\n').encode())
        sock.close()

    @pytest.mark.integration
    def test_send_keyboard_press(self, skip_if_no_controller):
        """Test sending keyboard command to running controller."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('127.0.0.1', 8889))

        cmd = {
            'type': 'keyboard',
            'key': 'a',
            'action': 'press'
        }
        sock.send((json.dumps(cmd) + '\n').encode())
        sock.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'not integration'])
