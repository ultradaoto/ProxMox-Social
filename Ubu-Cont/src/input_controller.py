import os
import sys
import json
import logging
import time

# Ensure proper path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# Add 'input' subdirectory to path if needed, though we can import as package if __init__.py exists
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'input'))

# Import existing controllers (handling potential import issues)
try:
    from virtual_mouse_controller import VirtualMouseController
    # VirtualKeyboardController is also in virtual_mouse_controller.py
    from virtual_mouse_controller import VirtualKeyboardController 
except ImportError:
    # Try importing with package prefix if run from different context
    try:
        from src.virtual_mouse_controller import VirtualMouseController, VirtualKeyboardController
    except ImportError:
        logging.error("Could not import VirtualMouseController. Check python path.")
        raise

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InputController")

class InputController:
    def __init__(self, config_path=None):
        """Initialize InputController with config."""
        if config_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(base_dir, '..', 'config.json')
        
        self.config = self._load_config(config_path)
        
        # Mouse Config
        mouse_host = self.config['mouse']['host']
        mouse_port = self.config['mouse']['port']
        
        # Keyboard Config
        kb_host = self.config['keyboard']['host']
        kb_port = self.config['keyboard']['port']
        
        logger.info(f"Initializing InputController. Mouse: {mouse_host}:{mouse_port}, KB: {kb_host}:{kb_port}")
        
        self.mouse = VirtualMouseController(host=mouse_host, port=mouse_port)
        self.keyboard = VirtualKeyboardController(host=kb_host, port=kb_port)
        
        # We need to monkey-patch or fix the import within virtual_mouse_controller if it fails
        # But assuming we set sys.path, it might work if 'human_mouse' is found.
        # virtual_mouse_controller.py imports 'human_mouse'.
        # We added 'src/input' to sys.path, so 'import human_mouse' should work there.

    def _load_config(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def connect(self):
        """Connect both devices."""
        self.mouse.connect()
        self.keyboard.connect()

    def move_to(self, x: int, y: int):
        """Move mouse to coordinates."""
        self.mouse.move_to(x, y)

    def click(self, button='left', count=1):
        """Click mouse button."""
        self.mouse.click(button, count)
    
    def type_text(self, text: str, wpm=None):
        """Type text."""
        # Config has behavior settings we could use
        if wpm is None:
             # Just use default or could calculate from config['behavior']
             pass
        self.keyboard.type_text(text)
    
    def hotkey(self, *keys):
        """Send hotkey combination."""
        # VirtualKeyboardController doesn't implement hotkey directly in the version we saw?
        # Wait, I need to check if VirtualKeyboardController has hotkey.
        # I saw 'human_keyboard.py' has hotkey, but VirtualKeyboardController seemed to implement 'type_text'.
        # Let's double check VirtualKeyboardController method in virtual_mouse_controller.py
        # It has type_text and _send_key.
        # It does NOT seem to have hotkey. I might need to implement it using _send_command directly or extending it.
        
        # Implementing hotkey manually using basic primitives if available
        # The protocol seems to be {'type': 'keyboard', 'key': key, 'action': 'down'/'up'}
        
        # Press all down
        for key in keys:
            self._send_key_action(key, 'down')
            time.sleep(0.05)
            
        time.sleep(0.1)
        
        # Release all up (reverse order)
        for key in reversed(keys):
            self._send_key_action(key, 'up')
            time.sleep(0.05)

    def _send_key_action(self, key, action):
        cmd = {
            'type': 'keyboard',
            'key': key,
            'action': action,
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        try:
            if self.keyboard.socket:
                self.keyboard.socket.send(json.dumps(cmd).encode() + b'\n')
            else:
                # auto-connect check
                if not self.keyboard.connected:
                     self.keyboard.connect()
                if self.keyboard.socket:
                     self.keyboard.socket.send(json.dumps(cmd).encode() + b'\n')
        except Exception as e:
            logger.error(f"Error sending key: {e}")

if __name__ == "__main__":
    ic = InputController()
    ic.connect()
    print("Moving mouse...")
    ic.move_to(500, 500)
    print("Clicking...")
    ic.click()
    print("Typing...")
    ic.type_text("Hello from InputController")
