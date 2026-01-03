# Ubuntu Keyboard Input Protocol

This document describes how the Ubuntu AI Controller VM should send keyboard commands to the Proxmox host for injection into the Windows VM.

## Connection Details

| Parameter | Value |
|-----------|-------|
| Host | `192.168.100.1` (Proxmox vmbr1 interface) |
| Port | `8889` |
| Protocol | TCP |
| Format | JSON, newline-delimited |

## Command Format

```json
{"type": "keyboard", "key": "<key>", "action": "<action>"}\n
```

**Important:** Each JSON command MUST be followed by a newline character (`\n`).

## Actions

| Action | Description |
|--------|-------------|
| `press` | Key down, 50ms hold, key up (most common for typing) |
| `down` | Key down only (use for holding modifier keys) |
| `up` | Key up only (use to release held keys) |

## Supported Keys

### Letters
Lowercase letters `a` through `z`. Uppercase letters (`A-Z`) automatically add the Shift modifier.

```json
{"type": "keyboard", "key": "a", "action": "press"}
{"type": "keyboard", "key": "A", "action": "press"}
```

### Numbers
`0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`

```json
{"type": "keyboard", "key": "5", "action": "press"}
```

### Special Keys

| Key Name | Aliases |
|----------|---------|
| `enter` | `return` |
| `escape` | `esc` |
| `backspace` | |
| `tab` | |
| `space` | ` ` (space character) |
| `capslock` | `caps` |

### Arrow Keys
`up`, `down`, `left`, `right`

### Navigation Keys
`insert`, `delete`, `home`, `end`, `pageup`, `pagedown`

### Function Keys
`f1`, `f2`, `f3`, `f4`, `f5`, `f6`, `f7`, `f8`, `f9`, `f10`, `f11`, `f12`

### Modifier Keys

| Key Name | Aliases | Bit Mask |
|----------|---------|----------|
| `lctrl` | `ctrl` | 0x01 |
| `lshift` | `shift` | 0x02 |
| `lalt` | `alt` | 0x04 |
| `lwin` | `win`, `super` | 0x08 |
| `rctrl` | | 0x10 |
| `rshift` | | 0x20 |
| `ralt` | | 0x40 |
| `rwin` | | 0x80 |

### Symbol Keys (Unshifted)

| Character | Key |
|-----------|-----|
| `-` | minus |
| `=` | equals |
| `[` | left bracket |
| `]` | right bracket |
| `\` | backslash |
| `;` | semicolon |
| `'` | apostrophe |
| `` ` `` | grave/backtick |
| `,` | comma |
| `.` | period |
| `/` | slash |

### Shifted Characters (Auto-Handled)

These characters automatically add the Shift modifier:

| Character | Base Key |
|-----------|----------|
| `!` | 1 |
| `@` | 2 |
| `#` | 3 |
| `$` | 4 |
| `%` | 5 |
| `^` | 6 |
| `&` | 7 |
| `*` | 8 |
| `(` | 9 |
| `)` | 0 |
| `_` | - |
| `+` | = |
| `{` | [ |
| `}` | ] |
| `|` | \ |
| `:` | ; |
| `"` | ' |
| `<` | , |
| `>` | . |
| `?` | / |
| `~` | ` |

## Python Example

```python
import socket
import json
import time

class KeyboardSender:
    def __init__(self, host='192.168.100.1', port=8889):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def send_key(self, key: str, action: str = 'press'):
        """Send a single key command."""
        cmd = {'type': 'keyboard', 'key': key, 'action': action}
        self.sock.sendall((json.dumps(cmd) + '\n').encode('utf-8'))

    def type_text(self, text: str, delay: float = 0.05):
        """Type a string of text with delays between keys."""
        for char in text:
            self.send_key(char, 'press')
            time.sleep(delay)

    def key_combo(self, *keys):
        """
        Press a key combination (e.g., Ctrl+C).
        Last key is pressed, others are held as modifiers.
        """
        # Hold all modifier keys
        for key in keys[:-1]:
            self.send_key(key, 'down')
            time.sleep(0.01)

        # Press the final key
        self.send_key(keys[-1], 'press')
        time.sleep(0.01)

        # Release modifier keys in reverse order
        for key in reversed(keys[:-1]):
            self.send_key(key, 'up')
            time.sleep(0.01)


# Usage example
if __name__ == '__main__':
    kb = KeyboardSender()
    kb.connect()

    # Type "Hello World"
    kb.type_text("Hello World")

    # Press Enter
    kb.send_key('enter')

    # Ctrl+A (select all)
    kb.key_combo('ctrl', 'a')

    # Ctrl+C (copy)
    kb.key_combo('ctrl', 'c')

    # Alt+Tab (switch window)
    kb.key_combo('alt', 'tab')

    # Ctrl+Shift+Escape (task manager)
    kb.key_combo('ctrl', 'shift', 'escape')

    # Win+R (run dialog)
    kb.key_combo('win', 'r')

    kb.disconnect()
```

## Bash/Netcat Examples

```bash
# Single key press
echo '{"type":"keyboard","key":"a","action":"press"}' | nc 192.168.100.1 8889

# Press Enter
echo '{"type":"keyboard","key":"enter","action":"press"}' | nc 192.168.100.1 8889

# Type capital letter
echo '{"type":"keyboard","key":"A","action":"press"}' | nc 192.168.100.1 8889

# Ctrl+C (must use persistent connection)
{
  echo '{"type":"keyboard","key":"ctrl","action":"down"}'
  sleep 0.05
  echo '{"type":"keyboard","key":"c","action":"press"}'
  sleep 0.05
  echo '{"type":"keyboard","key":"ctrl","action":"up"}'
} | nc 192.168.100.1 8889

# Type "hello" (persistent connection)
{
  echo '{"type":"keyboard","key":"h","action":"press"}'
  echo '{"type":"keyboard","key":"e","action":"press"}'
  echo '{"type":"keyboard","key":"l","action":"press"}'
  echo '{"type":"keyboard","key":"l","action":"press"}'
  echo '{"type":"keyboard","key":"o","action":"press"}'
} | nc 192.168.100.1 8889
```

## Common Key Combinations

| Combination | Keys | Description |
|-------------|------|-------------|
| Ctrl+C | `ctrl` + `c` | Copy |
| Ctrl+V | `ctrl` + `v` | Paste |
| Ctrl+X | `ctrl` + `x` | Cut |
| Ctrl+A | `ctrl` + `a` | Select all |
| Ctrl+Z | `ctrl` + `z` | Undo |
| Ctrl+S | `ctrl` + `s` | Save |
| Alt+Tab | `alt` + `tab` | Switch window |
| Alt+F4 | `alt` + `f4` | Close window |
| Win+D | `win` + `d` | Show desktop |
| Win+R | `win` + `r` | Run dialog |
| Win+E | `win` + `e` | File Explorer |
| Ctrl+Shift+Esc | `ctrl` + `shift` + `escape` | Task Manager |

## Timing Considerations

The HID controller applies human-like jitter (1-5ms random delay) to each command. When typing text, add your own delays between keys:

| Use Case | Recommended Delay |
|----------|-------------------|
| Normal typing | 30-80ms between keys |
| Fast typing | 20-40ms between keys |
| Modifier combos | 10-20ms between down/press/up |
| After Enter/Tab | 100-200ms (wait for UI response) |

## Error Handling

The host logs errors to systemd journal. Check logs with:

```bash
journalctl -u input-router -f
```

Common issues:

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown key: X` | Key not in KEY_CODES | Use supported key name |
| `Invalid JSON` | Malformed command | Check JSON syntax |
| Connection refused | Service not running | `systemctl start input-router` |
| No response | Missing newline | Ensure `\n` after each command |

## HID Report Structure

For reference, the keyboard HID report sent to QEMU consists of:

| Byte | Description |
|------|-------------|
| 0 | Modifier flags (Ctrl, Shift, Alt, Win) |
| 1 | Reserved (always 0) |
| 2-7 | Up to 6 simultaneous key codes |

Maximum 6 non-modifier keys can be held simultaneously (standard USB HID limitation).

## Integration with Human-Like Typing

For realistic typing behavior, use the `human_keyboard.py` module which implements:

- Variable WPM (30-60 words per minute)
- 2% typo rate with backspace corrections
- Burst patterns for common words
- Inter-key timing variation

See `Ubu-Cont/src/input/human_keyboard.py` for implementation details.
