#!/usr/bin/env python3
"""
USB HID Report Descriptors for Virtual Logitech Devices

These descriptors define how the virtual mouse and keyboard report their
input data to the host system. They match real Logitech hardware behavior.
"""

# Logitech USB Vendor and Product IDs
LOGITECH_VENDOR_ID = 0x046d

# Mouse product IDs (Logitech Unifying-compatible mice)
LOGITECH_M510_PRODUCT_ID = 0xc52b  # M510 Wireless Mouse
LOGITECH_M525_PRODUCT_ID = 0x402d  # M525 Wireless Mouse
LOGITECH_M705_PRODUCT_ID = 0x101b  # M705 Marathon Mouse

# Keyboard product IDs
LOGITECH_K350_PRODUCT_ID = 0xc534  # K350 Wireless Keyboard
LOGITECH_K400_PRODUCT_ID = 0x400e  # K400 Wireless Touch Keyboard
LOGITECH_K520_PRODUCT_ID = 0xc52e  # K520 Wireless Keyboard

# Default device selections
DEFAULT_MOUSE_PRODUCT_ID = LOGITECH_M510_PRODUCT_ID
DEFAULT_KEYBOARD_PRODUCT_ID = LOGITECH_K350_PRODUCT_ID

# USB HID Bus Types
BUS_USB = 0x03
BUS_BLUETOOTH = 0x05

# USB HID Report Descriptor for a standard 3-button mouse with wheel
MOUSE_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x02,  # Usage (Mouse)
    0xA1, 0x01,  # Collection (Application)
    0x09, 0x01,  #   Usage (Pointer)
    0xA1, 0x00,  #   Collection (Physical)

    # Buttons (3 buttons, 5 bits padding)
    0x05, 0x09,  #     Usage Page (Button)
    0x19, 0x01,  #     Usage Minimum (Button 1)
    0x29, 0x05,  #     Usage Maximum (Button 5) - 5 buttons for side buttons
    0x15, 0x00,  #     Logical Minimum (0)
    0x25, 0x01,  #     Logical Maximum (1)
    0x95, 0x05,  #     Report Count (5)
    0x75, 0x01,  #     Report Size (1)
    0x81, 0x02,  #     Input (Data, Variable, Absolute)

    # Padding (3 bits)
    0x95, 0x01,  #     Report Count (1)
    0x75, 0x03,  #     Report Size (3)
    0x81, 0x03,  #     Input (Constant, Variable, Absolute)

    # X, Y movement (relative)
    0x05, 0x01,  #     Usage Page (Generic Desktop)
    0x09, 0x30,  #     Usage (X)
    0x09, 0x31,  #     Usage (Y)
    0x15, 0x81,  #     Logical Minimum (-127)
    0x25, 0x7F,  #     Logical Maximum (127)
    0x75, 0x08,  #     Report Size (8)
    0x95, 0x02,  #     Report Count (2)
    0x81, 0x06,  #     Input (Data, Variable, Relative)

    # Wheel (vertical scroll)
    0x09, 0x38,  #     Usage (Wheel)
    0x15, 0x81,  #     Logical Minimum (-127)
    0x25, 0x7F,  #     Logical Maximum (127)
    0x75, 0x08,  #     Report Size (8)
    0x95, 0x01,  #     Report Count (1)
    0x81, 0x06,  #     Input (Data, Variable, Relative)

    # Horizontal wheel (tilt)
    0x05, 0x0C,  #     Usage Page (Consumer)
    0x0A, 0x38, 0x02,  # Usage (AC Pan)
    0x15, 0x81,  #     Logical Minimum (-127)
    0x25, 0x7F,  #     Logical Maximum (127)
    0x75, 0x08,  #     Report Size (8)
    0x95, 0x01,  #     Report Count (1)
    0x81, 0x06,  #     Input (Data, Variable, Relative)

    0xC0,        #   End Collection
    0xC0         # End Collection
])

# USB HID Report Descriptor for a standard keyboard
KEYBOARD_REPORT_DESCRIPTOR = bytes([
    0x05, 0x01,  # Usage Page (Generic Desktop)
    0x09, 0x06,  # Usage (Keyboard)
    0xA1, 0x01,  # Collection (Application)

    # Modifier keys (8 bits: Ctrl, Shift, Alt, GUI for left and right)
    0x05, 0x07,  #   Usage Page (Keyboard/Keypad)
    0x19, 0xE0,  #   Usage Minimum (Left Control)
    0x29, 0xE7,  #   Usage Maximum (Right GUI)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x01,  #   Logical Maximum (1)
    0x75, 0x01,  #   Report Size (1)
    0x95, 0x08,  #   Report Count (8)
    0x81, 0x02,  #   Input (Data, Variable, Absolute)

    # Reserved byte
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x08,  #   Report Size (8)
    0x81, 0x03,  #   Input (Constant, Variable, Absolute)

    # LED output report (5 LEDs: Num Lock, Caps Lock, Scroll Lock, Compose, Kana)
    0x95, 0x05,  #   Report Count (5)
    0x75, 0x01,  #   Report Size (1)
    0x05, 0x08,  #   Usage Page (LEDs)
    0x19, 0x01,  #   Usage Minimum (Num Lock)
    0x29, 0x05,  #   Usage Maximum (Kana)
    0x91, 0x02,  #   Output (Data, Variable, Absolute)

    # LED padding (3 bits)
    0x95, 0x01,  #   Report Count (1)
    0x75, 0x03,  #   Report Size (3)
    0x91, 0x03,  #   Output (Constant, Variable, Absolute)

    # Key array (6 keys)
    0x95, 0x06,  #   Report Count (6)
    0x75, 0x08,  #   Report Size (8)
    0x15, 0x00,  #   Logical Minimum (0)
    0x25, 0x65,  #   Logical Maximum (101)
    0x05, 0x07,  #   Usage Page (Keyboard/Keypad)
    0x19, 0x00,  #   Usage Minimum (0)
    0x29, 0x65,  #   Usage Maximum (101)
    0x81, 0x00,  #   Input (Data, Array, Absolute)

    0xC0         # End Collection
])

# HID Usage codes for keyboard keys
KEY_CODES = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0a, 'h': 0x0b, 'i': 0x0c, 'j': 0x0d, 'k': 0x0e, 'l': 0x0f,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1a, 'x': 0x1b,
    'y': 0x1c, 'z': 0x1d,
    '1': 0x1e, '2': 0x1f, '3': 0x20, '4': 0x21, '5': 0x22, '6': 0x23,
    '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    'enter': 0x28, 'return': 0x28, 'escape': 0x29, 'esc': 0x29,
    'backspace': 0x2a, 'tab': 0x2b, 'space': 0x2c, ' ': 0x2c,
    '-': 0x2d, '=': 0x2e, '[': 0x2f, ']': 0x30, '\\': 0x31,
    ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38,
    'capslock': 0x39, 'caps': 0x39,
    'f1': 0x3a, 'f2': 0x3b, 'f3': 0x3c, 'f4': 0x3d, 'f5': 0x3e, 'f6': 0x3f,
    'f7': 0x40, 'f8': 0x41, 'f9': 0x42, 'f10': 0x43, 'f11': 0x44, 'f12': 0x45,
    'printscreen': 0x46, 'scrolllock': 0x47, 'pause': 0x48,
    'insert': 0x49, 'home': 0x4a, 'pageup': 0x4b, 'delete': 0x4c,
    'end': 0x4d, 'pagedown': 0x4e, 'right': 0x4f, 'left': 0x50,
    'down': 0x51, 'up': 0x52, 'numlock': 0x53,
    # Modifiers
    'ctrl': 0xe0, 'lctrl': 0xe0, 'rctrl': 0xe4,
    'shift': 0xe1, 'lshift': 0xe1, 'rshift': 0xe5,
    'alt': 0xe2, 'lalt': 0xe2, 'ralt': 0xe6,
    'win': 0xe3, 'lwin': 0xe3, 'rwin': 0xe7, 'super': 0xe3,
}

# Modifier key bit masks
MODIFIER_MASKS = {
    'lctrl': 0x01, 'ctrl': 0x01,
    'lshift': 0x02, 'shift': 0x02,
    'lalt': 0x04, 'alt': 0x04,
    'lwin': 0x08, 'win': 0x08, 'super': 0x08,
    'rctrl': 0x10,
    'rshift': 0x20,
    'ralt': 0x40,
    'rwin': 0x80,
}

# Characters that require Shift modifier
SHIFT_CHARS = {
    '!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6',
    '&': '7', '*': '8', '(': '9', ')': '0', '_': '-', '+': '=',
    '{': '[', '}': ']', '|': '\\', ':': ';', '"': "'", '<': ',',
    '>': '.', '?': '/', '~': '`',
    'A': 'a', 'B': 'b', 'C': 'c', 'D': 'd', 'E': 'e', 'F': 'f',
    'G': 'g', 'H': 'h', 'I': 'i', 'J': 'j', 'K': 'k', 'L': 'l',
    'M': 'm', 'N': 'n', 'O': 'o', 'P': 'p', 'Q': 'q', 'R': 'r',
    'S': 's', 'T': 't', 'U': 'u', 'V': 'v', 'W': 'w', 'X': 'x',
    'Y': 'y', 'Z': 'z',
}


def get_key_code(char: str) -> tuple[int, bool]:
    """
    Get the HID key code for a character and whether Shift is needed.

    Args:
        char: Single character or key name

    Returns:
        Tuple of (key_code, needs_shift)
    """
    char_lower = char.lower()

    # Check if it needs shift
    if char in SHIFT_CHARS:
        base_char = SHIFT_CHARS[char]
        return KEY_CODES.get(base_char, 0), True

    return KEY_CODES.get(char_lower, 0), False


def get_device_name(device_type: str) -> str:
    """Get a realistic device name for the virtual device."""
    if device_type == 'mouse':
        return 'Logitech M510 Wireless Mouse'
    elif device_type == 'keyboard':
        return 'Logitech K350 Wireless Keyboard'
    else:
        return f'Logitech Virtual {device_type.title()}'
