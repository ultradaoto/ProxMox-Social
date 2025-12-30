#!/usr/bin/env python3
"""
Test suite for virtual HID device creation.

Run on: Proxmox Host
Requirements: pytest, root privileges for device tests
"""

import os
import sys
import time
import pytest
import struct
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'virtual-hid'))

from device_descriptors import (
    MOUSE_REPORT_DESCRIPTOR,
    KEYBOARD_REPORT_DESCRIPTOR,
    KEY_CODES,
    get_key_code,
    LOGITECH_VENDOR_ID,
)
from logitech_spoofing import (
    DeviceSpoofingConfig,
    get_device_profile,
    DEVICE_PROFILES,
    generate_udev_rules,
)


class TestDeviceDescriptors:
    """Tests for USB HID report descriptors."""

    def test_mouse_descriptor_structure(self):
        """Test that mouse descriptor has proper HID structure."""
        desc = MOUSE_REPORT_DESCRIPTOR

        # Should start with Usage Page (Generic Desktop)
        assert desc[0:2] == bytes([0x05, 0x01])

        # Should contain Usage (Mouse)
        assert bytes([0x09, 0x02]) in desc

        # Should end with End Collection
        assert desc[-1] == 0xC0

    def test_keyboard_descriptor_structure(self):
        """Test that keyboard descriptor has proper HID structure."""
        desc = KEYBOARD_REPORT_DESCRIPTOR

        # Should start with Usage Page (Generic Desktop)
        assert desc[0:2] == bytes([0x05, 0x01])

        # Should contain Usage (Keyboard)
        assert bytes([0x09, 0x06]) in desc

        # Should end with End Collection
        assert desc[-1] == 0xC0

    def test_mouse_descriptor_length(self):
        """Test that mouse descriptor is reasonable length."""
        assert 30 < len(MOUSE_REPORT_DESCRIPTOR) < 200

    def test_keyboard_descriptor_length(self):
        """Test that keyboard descriptor is reasonable length."""
        assert 30 < len(KEYBOARD_REPORT_DESCRIPTOR) < 200


class TestKeyCodes:
    """Tests for keyboard key code mappings."""

    def test_letter_keys(self):
        """Test that all letter keys are mapped."""
        for letter in 'abcdefghijklmnopqrstuvwxyz':
            assert letter in KEY_CODES
            assert KEY_CODES[letter] >= 0x04
            assert KEY_CODES[letter] <= 0x1d

    def test_number_keys(self):
        """Test that all number keys are mapped."""
        for num in '0123456789':
            assert num in KEY_CODES

    def test_special_keys(self):
        """Test that special keys are mapped."""
        special = ['enter', 'escape', 'backspace', 'tab', 'space']
        for key in special:
            assert key in KEY_CODES

    def test_get_key_code_lowercase(self):
        """Test getting key code for lowercase letter."""
        code, shift = get_key_code('a')
        assert code == KEY_CODES['a']
        assert shift is False

    def test_get_key_code_uppercase(self):
        """Test getting key code for uppercase letter."""
        code, shift = get_key_code('A')
        assert code == KEY_CODES['a']
        assert shift is True

    def test_get_key_code_special_char(self):
        """Test getting key code for special characters."""
        code, shift = get_key_code('!')
        assert code == KEY_CODES['1']
        assert shift is True


class TestLogitechSpoofing:
    """Tests for Logitech device spoofing configuration."""

    def test_vendor_id(self):
        """Test that Logitech vendor ID is correct."""
        assert LOGITECH_VENDOR_ID == 0x046d

    def test_device_profiles_exist(self):
        """Test that default device profiles exist."""
        assert 'mouse_m510' in DEVICE_PROFILES
        assert 'keyboard_k350' in DEVICE_PROFILES

    def test_get_device_profile(self):
        """Test getting a device profile."""
        profile = get_device_profile('mouse_m510')
        assert profile.vendor_id == LOGITECH_VENDOR_ID
        assert profile.product_id == 0xc52b

    def test_get_invalid_profile(self):
        """Test that invalid profile raises error."""
        with pytest.raises(ValueError):
            get_device_profile('nonexistent_device')

    def test_spoofing_config_uhid_params(self):
        """Test getting UHID creation parameters."""
        config = DeviceSpoofingConfig()
        params = config.get_uhid_create_params('mouse')

        assert params['bus'] == 0x03  # BUS_USB
        assert params['vendor'] == LOGITECH_VENDOR_ID
        assert 'name' in params

    def test_spoofing_config_evdev_params(self):
        """Test getting evdev creation parameters."""
        config = DeviceSpoofingConfig()
        params = config.get_evdev_create_params('keyboard')

        assert params['vendor'] == LOGITECH_VENDOR_ID
        assert 'name' in params

    def test_generate_udev_rules(self):
        """Test udev rules generation."""
        rules = generate_udev_rules()

        assert 'SUBSYSTEM=="input"' in rules
        assert LOGITECH_VENDOR_ID.to_bytes(2, 'little').hex() in rules.lower()

    def test_proxmox_conf_lines(self):
        """Test Proxmox configuration line generation."""
        config = DeviceSpoofingConfig()
        lines = config.get_proxmox_conf_lines(100)

        assert len(lines) >= 2
        assert any('usb0:' in line for line in lines)


class TestVirtualDeviceCreation:
    """Tests for actual virtual device creation.

    These tests require root privileges and may modify system state.
    Run with: sudo pytest -v test_virtual_device.py::TestVirtualDeviceCreation
    """

    @pytest.fixture
    def skip_if_not_root(self):
        """Skip test if not running as root."""
        if os.geteuid() != 0:
            pytest.skip("Test requires root privileges")

    @pytest.fixture
    def skip_if_no_uhid(self):
        """Skip test if /dev/uhid is not available."""
        if not os.path.exists('/dev/uhid'):
            pytest.skip("/dev/uhid not available")

    def test_uhid_device_exists(self, skip_if_not_root, skip_if_no_uhid):
        """Test that /dev/uhid is accessible."""
        assert os.path.exists('/dev/uhid')
        # Check we can open it
        fd = os.open('/dev/uhid', os.O_RDWR)
        os.close(fd)

    def test_create_virtual_mouse(self, skip_if_not_root, skip_if_no_uhid):
        """Test creating a virtual mouse device."""
        from create_virtual_hid import create_uhid_device, VirtualHIDDevice

        device = None
        try:
            device = create_uhid_device('mouse')
            assert isinstance(device, VirtualHIDDevice)
            assert device.device_type == 'mouse'
            assert device.fd >= 0

            # Give kernel time to register
            time.sleep(0.5)

            # Check device appears in input devices
            # Note: May not show up in /dev/input/by-id without udev rules
        finally:
            if device:
                device.close()


class TestDeviceReports:
    """Tests for HID report generation."""

    def test_mouse_report_size(self):
        """Test that mouse report is correct size."""
        # buttons(1) + x(1) + y(1) + wheel(1) + hwheel(1) = 5 bytes
        from create_virtual_hid import send_mouse_report
        # Note: Can't fully test without actual device

    def test_keyboard_report_size(self):
        """Test that keyboard report is correct size."""
        # modifiers(1) + reserved(1) + keys(6) = 8 bytes
        from create_virtual_hid import send_keyboard_report
        # Note: Can't fully test without actual device


if __name__ == '__main__':
    # Run with pytest
    pytest.main([__file__, '-v'])
