# Ubuntu Mouse Input Protocol

This document describes how the Ubuntu AI Controller VM should send mouse commands to the Proxmox host for injection into the Windows VM.

## Connection Details

| Parameter | Value |
|-----------|-------|
| Host | `192.168.100.1` (Proxmox vmbr1 interface) |
| Port | `8888` |
| Protocol | TCP |
| Format | JSON, newline-delimited |

## Important: Coordinate System

The Windows VM uses **absolute coordinates** via the QEMU HID Tablet device.

| Parameter | Value |
|-----------|-------|
| Screen Resolution | 1280 x 800 |
| Coordinate Range | 0-1279 (X), 0-799 (Y) |
| Origin | Top-left corner (0, 0) |

The host automatically converts screen coordinates to QMP absolute coordinates (0-32767 range).

## Command Types

### 1. Absolute Mouse Move

Move the cursor to an absolute screen position. **This is the recommended method.**

```json
{"type": "abs", "x": 640, "y": 400}\n
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"abs"` |
| `x` | integer | Screen X coordinate (0-1279) |
| `y` | integer | Screen Y coordinate (0-799) |

### 2. Relative Mouse Move

Move the cursor relative to its current position.

```json
{"type": "move", "x": 10, "y": -5}\n
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"move"` |
| `x` | integer | Relative X movement (positive = right) |
| `y` | integer | Relative Y movement (positive = down) |

**Note:** The host tracks the virtual cursor position internally, starting at screen center (640, 400).

### 3. Mouse Button

Press or release a mouse button.

```json
{"type": "click", "button": "left", "action": "down"}\n
{"type": "click", "button": "left", "action": "up"}\n
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"click"` |
| `button` | string | `"left"`, `"right"`, `"middle"`, `"button4"`, `"button5"` |
| `action` | string | `"down"`, `"up"`, or `"click"` (down+up) |

### 4. Mouse Scroll

Scroll the mouse wheel.

```json
{"type": "scroll", "delta": 3}\n
{"type": "scroll", "delta": -3, "horizontal": true}\n
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | Must be `"scroll"` |
| `delta` | integer | Scroll amount (positive = up/right, negative = down/left) |
| `horizontal` | boolean | Optional. If true, horizontal scroll (default: false) |

## Python Example

```python
import socket
import json
import time
import math

class MouseSender:
    def __init__(self, host='192.168.100.1', port=8888):
        self.host = host
        self.port = port
        self.sock = None
        self.screen_width = 1280
        self.screen_height = 800

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send(self, cmd: dict):
        """Send a mouse command."""
        self.sock.sendall((json.dumps(cmd) + '\n').encode('utf-8'))

    def move_to(self, x: int, y: int):
        """Move cursor to absolute position."""
        # Clamp to screen bounds
        x = max(0, min(x, self.screen_width - 1))
        y = max(0, min(y, self.screen_height - 1))
        self.send({'type': 'abs', 'x': x, 'y': y})

    def move_relative(self, dx: int, dy: int):
        """Move cursor relative to current position."""
        self.send({'type': 'move', 'x': dx, 'y': dy})

    def click(self, button: str = 'left'):
        """Click a mouse button (down + up)."""
        self.send({'type': 'click', 'button': button, 'action': 'down'})
        time.sleep(0.05)
        self.send({'type': 'click', 'button': button, 'action': 'up'})

    def double_click(self, button: str = 'left'):
        """Double-click a mouse button."""
        self.click(button)
        time.sleep(0.1)
        self.click(button)

    def right_click(self):
        """Right-click."""
        self.click('right')

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int,
             steps: int = 20, duration: float = 0.5):
        """Drag from start to end position."""
        # Move to start
        self.move_to(start_x, start_y)
        time.sleep(0.05)

        # Press button
        self.send({'type': 'click', 'button': 'left', 'action': 'down'})
        time.sleep(0.05)

        # Move in steps
        step_delay = duration / steps
        for i in range(1, steps + 1):
            t = i / steps
            x = int(start_x + (end_x - start_x) * t)
            y = int(start_y + (end_y - start_y) * t)
            self.move_to(x, y)
            time.sleep(step_delay)

        # Release button
        self.send({'type': 'click', 'button': 'left', 'action': 'up'})

    def scroll(self, delta: int, horizontal: bool = False):
        """Scroll the mouse wheel."""
        self.send({'type': 'scroll', 'delta': delta, 'horizontal': horizontal})

    def scroll_up(self, clicks: int = 3):
        """Scroll up."""
        self.scroll(clicks)

    def scroll_down(self, clicks: int = 3):
        """Scroll down."""
        self.scroll(-clicks)

    def click_at(self, x: int, y: int, button: str = 'left'):
        """Move to position and click."""
        self.move_to(x, y)
        time.sleep(0.05)
        self.click(button)


# Usage example
if __name__ == '__main__':
    mouse = MouseSender()
    mouse.connect()

    # Move to center of screen
    mouse.move_to(640, 400)

    # Click at specific location
    mouse.click_at(100, 200)

    # Double-click
    mouse.move_to(500, 300)
    mouse.double_click()

    # Right-click context menu
    mouse.right_click()

    # Scroll down
    mouse.scroll_down(5)

    # Drag operation (e.g., select text)
    mouse.drag(100, 100, 400, 100)

    mouse.disconnect()
```

## Bash/Netcat Examples

```bash
# Move to absolute position (center of screen)
echo '{"type":"abs","x":640,"y":400}' | nc 192.168.100.1 8888

# Move to top-left corner
echo '{"type":"abs","x":0,"y":0}' | nc 192.168.100.1 8888

# Relative move (10 pixels right, 5 pixels down)
echo '{"type":"move","x":10,"y":5}' | nc 192.168.100.1 8888

# Left click (must use persistent connection for down+up)
{
  echo '{"type":"click","button":"left","action":"down"}'
  sleep 0.05
  echo '{"type":"click","button":"left","action":"up"}'
} | nc 192.168.100.1 8888

# Right click
{
  echo '{"type":"click","button":"right","action":"down"}'
  sleep 0.05
  echo '{"type":"click","button":"right","action":"up"}'
} | nc 192.168.100.1 8888

# Scroll up
echo '{"type":"scroll","delta":3}' | nc 192.168.100.1 8888

# Scroll down
echo '{"type":"scroll","delta":-3}' | nc 192.168.100.1 8888

# Move and click (persistent connection)
{
  echo '{"type":"abs","x":500,"y":300}'
  sleep 0.1
  echo '{"type":"click","button":"left","action":"down"}'
  sleep 0.05
  echo '{"type":"click","button":"left","action":"up"}'
} | nc 192.168.100.1 8888
```

## Common Screen Locations (1280x800)

| Location | Coordinates | Description |
|----------|-------------|-------------|
| Center | (640, 400) | Screen center |
| Top-left | (0, 0) | Origin |
| Top-right | (1279, 0) | |
| Bottom-left | (0, 799) | |
| Bottom-right | (1279, 799) | |
| Taskbar (center) | (640, 780) | Windows taskbar |
| Start button | (20, 780) | Windows Start |
| System tray | (1200, 780) | Notification area |
| Close button | (1260, 10) | Window close (maximized) |
| Minimize button | (1200, 10) | Window minimize |
| Maximize button | (1230, 10) | Window maximize |

## Human-Like Movement

For realistic mouse movement, use Bezier curves with Fitts's Law timing:

```python
import math
import random

def bezier_point(t, p0, p1, p2, p3):
    """Calculate point on cubic Bezier curve."""
    u = 1 - t
    return (
        u**3 * p0[0] + 3*u**2*t * p1[0] + 3*u*t**2 * p2[0] + t**3 * p3[0],
        u**3 * p0[1] + 3*u**2*t * p1[1] + 3*u*t**2 * p2[1] + t**3 * p3[1]
    )

def fitts_law_duration(distance, target_width, a=50, b=150):
    """Calculate movement duration using Fitts's Law (milliseconds)."""
    if distance <= 0:
        return a
    return a + b * math.log2(distance / target_width + 1)

def human_move(mouse, start_x, start_y, end_x, end_y, target_width=20):
    """Move mouse with human-like Bezier curve trajectory."""
    distance = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
    duration_ms = fitts_law_duration(distance, target_width)

    # Generate control points for Bezier curve
    mid_x = (start_x + end_x) / 2
    mid_y = (start_y + end_y) / 2

    # Add randomness to control points
    ctrl1 = (
        start_x + (mid_x - start_x) * random.uniform(0.2, 0.4) + random.randint(-20, 20),
        start_y + (mid_y - start_y) * random.uniform(0.2, 0.4) + random.randint(-20, 20)
    )
    ctrl2 = (
        mid_x + (end_x - mid_x) * random.uniform(0.6, 0.8) + random.randint(-20, 20),
        mid_y + (end_y - mid_y) * random.uniform(0.6, 0.8) + random.randint(-20, 20)
    )

    # Number of steps based on distance
    steps = max(10, int(distance / 10))
    step_delay = (duration_ms / 1000) / steps

    for i in range(steps + 1):
        t = i / steps
        x, y = bezier_point(t, (start_x, start_y), ctrl1, ctrl2, (end_x, end_y))

        # Add micro-jitter
        x += random.randint(-2, 2)
        y += random.randint(-2, 2)

        mouse.move_to(int(x), int(y))
        time.sleep(step_delay)
```

## Timing Recommendations

| Operation | Recommended Delay |
|-----------|-------------------|
| Before click after move | 50-100ms |
| Between double-click | 80-150ms |
| Drag step interval | 20-50ms |
| After click (wait for UI) | 100-300ms |
| Scroll between steps | 50-100ms |

## Button State Tracking

The host tracks button states internally. Multiple buttons can be held simultaneously:

| Button | Bit |
|--------|-----|
| left | 0x01 |
| right | 0x02 |
| middle | 0x04 |
| button4 | 0x08 |
| button5 | 0x10 |

Example: Hold left while clicking right (for some games):

```python
mouse.send({'type': 'click', 'button': 'left', 'action': 'down'})
time.sleep(0.1)
mouse.click('right')  # Right click while left is held
time.sleep(0.1)
mouse.send({'type': 'click', 'button': 'left', 'action': 'up'})
```

## Error Handling

Check logs with:

```bash
journalctl -u input-router -f
```

Common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| Cursor jumps to corner | Wrong coordinates | Check 0-1279/0-799 range |
| Click at wrong position | Resolution mismatch | Verify 1280x800 |
| No movement | Connection lost | Reconnect socket |
| Laggy movement | Too many steps | Reduce step count |

## Coordinate Conversion Reference

The host converts screen coordinates to QMP absolute coordinates:

```
qmp_x = (screen_x / 1280) * 32767
qmp_y = (screen_y / 800) * 32767
```

| Screen Position | QMP Coordinates |
|-----------------|-----------------|
| (0, 0) | (0, 0) |
| (640, 400) | (16383, 16383) |
| (1280, 800) | (32767, 32767) |
| (100, 200) | (2559, 8191) |

## Integration with Vision AI

When clicking UI elements detected by OmniParser:

1. Get bounding box from vision: `(x1, y1, x2, y2)`
2. Calculate center: `cx = (x1 + x2) / 2`, `cy = (y1 + y2) / 2`
3. Add small random offset: `±5 pixels` (avoid exact center)
4. Use human-like movement to target
5. Click with realistic timing

See `Ubu-Cont/src/input/human_mouse.py` for full implementation.
