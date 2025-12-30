#!/usr/bin/env python3
"""
Virtual HID Device Creation using python-evdev UInput

Creates virtual USB HID devices that appear as Logitech mouse and keyboard
to the system. Uses the simpler and more reliable UInput interface.
"""

import time
import threading
from typing import Optional
from dataclasses import dataclass
import evdev
from evdev import UInput, ecodes as e, AbsInfo

from device_descriptors import (
    LOGITECH_VENDOR_ID,
    DEFAULT_MOUSE_PRODUCT_ID,
    DEFAULT_KEYBOARD_PRODUCT_ID,
    BUS_USB,
)
from logitech_spoofing import DeviceSpoofingConfig, default_config


@dataclass
class VirtualHIDDevice:
    """Represents a created virtual HID device."""
    ui: UInput
    device_type: str
    name: str
    vendor_id: int
    product_id: int

    def close(self):
        """Close and destroy the virtual device."""
        if self.ui:
            try:
                self.ui.close()
            except Exception:
                pass


def create_virtual_mouse(config: DeviceSpoofingConfig = default_config) -> VirtualHIDDevice:
    """
    Create a virtual mouse device using UInput.

    Args:
        config: Device spoofing configuration

    Returns:
        VirtualHIDDevice instance
    """
    params = config.get_uhid_create_params('mouse')
    name = params['name'].decode('utf-8')

    # Define mouse capabilities
    cap = {
        e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE, e.BTN_SIDE, e.BTN_EXTRA],
        e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL],
    }

    ui = UInput(
        cap,
        name=name,
        vendor=params['vendor'],
        product=params['product'],
        version=params['version'],
        bustype=BUS_USB,
    )

    return VirtualHIDDevice(
        ui=ui,
        device_type='mouse',
        name=name,
        vendor_id=params['vendor'],
        product_id=params['product'],
    )


def create_virtual_keyboard(config: DeviceSpoofingConfig = default_config) -> VirtualHIDDevice:
    """
    Create a virtual keyboard device using UInput.

    Args:
        config: Device spoofing configuration

    Returns:
        VirtualHIDDevice instance
    """
    params = config.get_uhid_create_params('keyboard')
    name = params['name'].decode('utf-8')

    # Define keyboard capabilities - all standard keys
    keys = list(range(1, 256))  # All possible key codes

    cap = {
        e.EV_KEY: keys,
        e.EV_LED: [e.LED_NUML, e.LED_CAPSL, e.LED_SCROLLL],
    }

    ui = UInput(
        cap,
        name=name,
        vendor=params['vendor'],
        product=params['product'],
        version=params['version'],
        bustype=BUS_USB,
    )

    return VirtualHIDDevice(
        ui=ui,
        device_type='keyboard',
        name=name,
        vendor_id=params['vendor'],
        product_id=params['product'],
    )


def create_uhid_device(device_type: str,
                       config: DeviceSpoofingConfig = default_config) -> VirtualHIDDevice:
    """
    Create a virtual HID device using UInput.

    Args:
        device_type: 'mouse' or 'keyboard'
        config: Device spoofing configuration

    Returns:
        VirtualHIDDevice instance
    """
    if device_type == 'mouse':
        return create_virtual_mouse(config)
    elif device_type == 'keyboard':
        return create_virtual_keyboard(config)
    else:
        raise ValueError(f"Unknown device type: {device_type}")


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
        x: Relative X movement
        y: Relative Y movement
        wheel: Vertical scroll
        hwheel: Horizontal scroll
    """
    if device.device_type != 'mouse':
        raise ValueError("Device is not a mouse")

    ui = device.ui

    # Handle button states
    ui.write(e.EV_KEY, e.BTN_LEFT, 1 if buttons & 0x01 else 0)
    ui.write(e.EV_KEY, e.BTN_RIGHT, 1 if buttons & 0x02 else 0)
    ui.write(e.EV_KEY, e.BTN_MIDDLE, 1 if buttons & 0x04 else 0)
    ui.write(e.EV_KEY, e.BTN_SIDE, 1 if buttons & 0x08 else 0)
    ui.write(e.EV_KEY, e.BTN_EXTRA, 1 if buttons & 0x10 else 0)

    # Handle relative movement
    if x != 0:
        ui.write(e.EV_REL, e.REL_X, x)
    if y != 0:
        ui.write(e.EV_REL, e.REL_Y, y)
    if wheel != 0:
        ui.write(e.EV_REL, e.REL_WHEEL, wheel)
    if hwheel != 0:
        ui.write(e.EV_REL, e.REL_HWHEEL, hwheel)

    # Sync
    ui.syn()


def send_keyboard_report(device: VirtualHIDDevice,
                         modifiers: int = 0,
                         keys: list[int] = None) -> None:
    """
    Send a keyboard input report.

    Note: This uses evdev key codes, not HID key codes.
    The HID controller translates HID codes to evdev codes.

    Args:
        device: Virtual keyboard device
        modifiers: Modifier key state (bit mask)
        keys: List of evdev key codes currently pressed
    """
    if device.device_type != 'keyboard':
        raise ValueError("Device is not a keyboard")

    if keys is None:
        keys = []

    ui = device.ui

    # Handle modifier keys
    ui.write(e.EV_KEY, e.KEY_LEFTCTRL, 1 if modifiers & 0x01 else 0)
    ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1 if modifiers & 0x02 else 0)
    ui.write(e.EV_KEY, e.KEY_LEFTALT, 1 if modifiers & 0x04 else 0)
    ui.write(e.EV_KEY, e.KEY_LEFTMETA, 1 if modifiers & 0x08 else 0)
    ui.write(e.EV_KEY, e.KEY_RIGHTCTRL, 1 if modifiers & 0x10 else 0)
    ui.write(e.EV_KEY, e.KEY_RIGHTSHIFT, 1 if modifiers & 0x20 else 0)
    ui.write(e.EV_KEY, e.KEY_RIGHTALT, 1 if modifiers & 0x40 else 0)
    ui.write(e.EV_KEY, e.KEY_RIGHTMETA, 1 if modifiers & 0x80 else 0)

    # For now, just sync - the HID controller handles key state tracking
    ui.syn()


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
