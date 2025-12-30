#!/usr/bin/env python3
"""
Virtual HID Device Creation

Creates virtual USB HID devices that appear as Logitech mouse and keyboard
to the system (and subsequently to the Windows VM via USB passthrough).

Uses the Linux UHID interface to create userspace HID devices.
"""

import os
import struct
import fcntl
import select
import threading
import time
from typing import Optional, Callable
from dataclasses import dataclass
from enum import IntEnum

from device_descriptors import (
    MOUSE_REPORT_DESCRIPTOR,
    KEYBOARD_REPORT_DESCRIPTOR,
    BUS_USB,
)
from logitech_spoofing import DeviceSpoofingConfig, default_config


class UHIDEventType(IntEnum):
    """UHID event types from linux/uhid.h"""
    UHID_DESTROY = 0
    UHID_START = 1
    UHID_STOP = 2
    UHID_OPEN = 3
    UHID_CLOSE = 4
    UHID_OUTPUT = 5
    UHID_GET_REPORT = 6
    UHID_GET_REPORT_REPLY = 7
    UHID_CREATE2 = 8
    UHID_INPUT2 = 9
    UHID_SET_REPORT = 10
    UHID_SET_REPORT_REPLY = 11


# UHID ioctl command (from linux/uhid.h)
UHID_CREATE2_SIZE = 4380  # Size of uhid_create2_req structure


@dataclass
class VirtualHIDDevice:
    """Represents a created virtual HID device."""
    fd: int
    device_type: str
    name: str
    vendor_id: int
    product_id: int

    def close(self):
        """Close and destroy the virtual device."""
        if self.fd >= 0:
            try:
                # Send UHID_DESTROY
                event = struct.pack('I', UHIDEventType.UHID_DESTROY)
                event += b'\x00' * (4380 - 4)  # Pad to event size
                os.write(self.fd, event)
            except OSError:
                pass
            finally:
                os.close(self.fd)
                self.fd = -1


def create_uhid_device(device_type: str,
                       config: DeviceSpoofingConfig = default_config) -> VirtualHIDDevice:
    """
    Create a virtual HID device using the Linux UHID interface.

    Args:
        device_type: 'mouse' or 'keyboard'
        config: Device spoofing configuration

    Returns:
        VirtualHIDDevice instance

    Raises:
        OSError: If device creation fails
        PermissionError: If /dev/uhid is not accessible
    """
    # Open UHID device
    try:
        fd = os.open('/dev/uhid', os.O_RDWR | os.O_CLOEXEC)
    except PermissionError:
        raise PermissionError(
            "Cannot open /dev/uhid. Ensure you have permissions or run as root.\n"
            "Try: sudo chmod 666 /dev/uhid"
        )

    # Get device parameters
    params = config.get_uhid_create_params(device_type)

    # Select report descriptor
    if device_type == 'mouse':
        rd_data = MOUSE_REPORT_DESCRIPTOR
    else:
        rd_data = KEYBOARD_REPORT_DESCRIPTOR

    # Build UHID_CREATE2 event
    # struct uhid_create2_req {
    #     __u8 name[128];
    #     __u8 phys[64];
    #     __u8 uniq[64];
    #     __u16 rd_size;
    #     __u16 bus;
    #     __u32 vendor;
    #     __u32 product;
    #     __u32 version;
    #     __u32 country;
    #     __u8 rd_data[HID_MAX_DESCRIPTOR_SIZE];
    # };

    name = params['name'][:127] + b'\x00' * (128 - min(len(params['name']), 127))
    phys = b'virtual-hid' + b'\x00' * 53  # Physical path (64 bytes)
    uniq = b'\x00' * 64  # Unique identifier

    # Event type (4 bytes) + create2 structure
    event = struct.pack('I', UHIDEventType.UHID_CREATE2)
    event += name
    event += phys
    event += uniq
    event += struct.pack('<H', len(rd_data))  # rd_size
    event += struct.pack('<H', params['bus'])  # bus
    event += struct.pack('<I', params['vendor'])  # vendor
    event += struct.pack('<I', params['product'])  # product
    event += struct.pack('<I', params['version'])  # version
    event += struct.pack('<I', 0)  # country
    event += rd_data  # Report descriptor
    event += b'\x00' * (4096 - len(rd_data))  # Pad rd_data to max size

    # Pad to full event size
    event += b'\x00' * (UHID_CREATE2_SIZE - len(event))

    try:
        os.write(fd, event)
    except OSError as e:
        os.close(fd)
        raise OSError(f"Failed to create virtual HID device: {e}")

    # Wait for and handle UHID_START event
    time.sleep(0.1)  # Give kernel time to process

    return VirtualHIDDevice(
        fd=fd,
        device_type=device_type,
        name=params['name'].decode('utf-8'),
        vendor_id=params['vendor'],
        product_id=params['product'],
    )


def send_mouse_report(device: VirtualHIDDevice,
                      buttons: int = 0,
                      x: int = 0,
                      y: int = 0,
                      wheel: int = 0,
                      hwheel: int = 0) -> None:
    """
    Send a mouse input report.

    Args:
        device: Virtual mouse device
        buttons: Button state (bit 0=left, bit 1=right, bit 2=middle, etc.)
        x: Relative X movement (-127 to 127)
        y: Relative Y movement (-127 to 127)
        wheel: Vertical scroll (-127 to 127)
        hwheel: Horizontal scroll (-127 to 127)
    """
    if device.device_type != 'mouse':
        raise ValueError("Device is not a mouse")

    # Clamp values to valid range
    x = max(-127, min(127, x))
    y = max(-127, min(127, y))
    wheel = max(-127, min(127, wheel))
    hwheel = max(-127, min(127, hwheel))

    # Build report: buttons(1) + x(1) + y(1) + wheel(1) + hwheel(1)
    report = struct.pack('Bbbbb', buttons, x, y, wheel, hwheel)

    # Build UHID_INPUT2 event
    event = struct.pack('I', UHIDEventType.UHID_INPUT2)
    event += struct.pack('<H', len(report))  # Size of report
    event += report
    event += b'\x00' * (UHID_CREATE2_SIZE - len(event))  # Pad to event size

    os.write(device.fd, event)


def send_keyboard_report(device: VirtualHIDDevice,
                         modifiers: int = 0,
                         keys: list[int] = None) -> None:
    """
    Send a keyboard input report.

    Args:
        device: Virtual keyboard device
        modifiers: Modifier key state (bit mask)
        keys: List of up to 6 key codes currently pressed
    """
    if device.device_type != 'keyboard':
        raise ValueError("Device is not a keyboard")

    if keys is None:
        keys = []

    # Pad keys to exactly 6 entries
    keys = (keys + [0] * 6)[:6]

    # Build report: modifiers(1) + reserved(1) + keys(6)
    report = struct.pack('BB6B', modifiers, 0, *keys)

    # Build UHID_INPUT2 event
    event = struct.pack('I', UHIDEventType.UHID_INPUT2)
    event += struct.pack('<H', len(report))  # Size of report
    event += report
    event += b'\x00' * (UHID_CREATE2_SIZE - len(event))  # Pad to event size

    os.write(device.fd, event)


class VirtualHIDManager:
    """
    Manages virtual HID devices lifecycle.

    Handles creation, input injection, and cleanup of virtual devices.
    """

    def __init__(self, config: DeviceSpoofingConfig = default_config):
        self.config = config
        self.mouse: Optional[VirtualHIDDevice] = None
        self.keyboard: Optional[VirtualHIDDevice] = None
        self._running = False
        self._event_thread: Optional[threading.Thread] = None

    def create_devices(self) -> None:
        """Create both mouse and keyboard virtual devices."""
        if self.mouse is None:
            self.mouse = create_uhid_device('mouse', self.config)
            print(f"Created virtual mouse: {self.mouse.name} "
                  f"(VID:{self.mouse.vendor_id:04x} PID:{self.mouse.product_id:04x})")

        if self.keyboard is None:
            self.keyboard = create_uhid_device('keyboard', self.config)
            print(f"Created virtual keyboard: {self.keyboard.name} "
                  f"(VID:{self.keyboard.vendor_id:04x} PID:{self.keyboard.product_id:04x})")

    def destroy_devices(self) -> None:
        """Destroy all virtual devices."""
        if self.mouse:
            self.mouse.close()
            self.mouse = None
            print("Destroyed virtual mouse")

        if self.keyboard:
            self.keyboard.close()
            self.keyboard = None
            print("Destroyed virtual keyboard")

    def move_mouse(self, dx: int, dy: int) -> None:
        """Send relative mouse movement."""
        if self.mouse:
            send_mouse_report(self.mouse, x=dx, y=dy)

    def click_mouse(self, button: str = 'left', pressed: bool = True) -> None:
        """Send mouse button press/release."""
        if not self.mouse:
            return

        button_bits = {'left': 0x01, 'right': 0x02, 'middle': 0x04,
                       'button4': 0x08, 'button5': 0x10}

        buttons = button_bits.get(button, 0) if pressed else 0
        send_mouse_report(self.mouse, buttons=buttons)

    def scroll_mouse(self, amount: int, horizontal: bool = False) -> None:
        """Send mouse scroll."""
        if not self.mouse:
            return

        if horizontal:
            send_mouse_report(self.mouse, hwheel=amount)
        else:
            send_mouse_report(self.mouse, wheel=amount)

    def press_key(self, key_code: int, modifiers: int = 0) -> None:
        """Press a key (send down event)."""
        if self.keyboard:
            send_keyboard_report(self.keyboard, modifiers=modifiers, keys=[key_code])

    def release_keys(self) -> None:
        """Release all keys."""
        if self.keyboard:
            send_keyboard_report(self.keyboard, modifiers=0, keys=[])

    def type_key(self, key_code: int, modifiers: int = 0,
                 duration: float = 0.05) -> None:
        """Type a key (press and release)."""
        self.press_key(key_code, modifiers)
        time.sleep(duration)
        self.release_keys()

    def __enter__(self):
        self.create_devices()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.destroy_devices()
        return False


if __name__ == '__main__':
    print("Virtual HID Device Creator")
    print("=" * 40)
    print("This script creates virtual Logitech HID devices")
    print("that can be passed through to a Windows VM.")
    print()

    # Create devices
    with VirtualHIDManager() as manager:
        print("\nDevices created. Press Ctrl+C to exit.")
        print("\nTo verify, check:")
        print("  ls -la /dev/input/by-id/ | grep -i logitech")
        print("  cat /proc/bus/input/devices | grep -A5 Logitech")

        try:
            # Keep running to maintain devices
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
