Document 1: OSP-PYTHON-SPEC.md
markdown# OSP (On-Screen Prompter) - Python Specification

## Overview

The OSP is a Python GUI application that appears on the right side of the screen. It coordinates with a Chrome extension to guide an AI agent through multi-step workflows like posting content to social media platforms.

The OSP and Chrome extension communicate via WebSocket. The AI agent only needs to understand one simple instruction: **click where you're told to click, paste when you're told to paste.**

---

## Architecture
```
+------------------+     WebSocket      +-------------------+
|   Python OSP     | <----------------> | Chrome Extension  |
|   (Right side)   |    localhost:8765  |   (Browser)       |
+------------------+                    +-------------------+
        |                                        |
        |            AI Agent Sees               |
        +-----> [Highlighted Button] <-----------+
                      |
                      v
                 Agent Clicks
```

---

## Dependencies
```
pip install websockets asyncio tkinter
```

---

## OSP Window Layout
```
+----------------------------------------+
|           ON-SCREEN PROMPTER           |
+----------------------------------------+
|                                        |
|  +----------------------------------+  |
|  |     STEP 1: CLICK HERE           |  | <- Large, color-coded button
|  +----------------------------------+  |
|                                        |
|  Current Step: Waiting to start...     |
|  Platform: (none)                      |
|  Post ID: (none)                       |
|                                        |
+----------------------------------------+
|           ACTION BUTTONS               |
+----------------------------------------+
|  +----------------------------------+  |
|  |         OPEN URL                 |  | <- Grayed out until active
|  +----------------------------------+  |
|  +----------------------------------+  |
|  |       COPY TITLE                 |  | <- Grayed out until active
|  +----------------------------------+  |
|  +----------------------------------+  |
|  |       COPY BODY                  |  | <- Grayed out until active
|  +----------------------------------+  |
|  +----------------------------------+  |
|  |       COPY HASHTAGS              |  | <- Grayed out until active
|  +----------------------------------+  |
|                                        |
+----------------------------------------+
|             STATUS                     |
+----------------------------------------+
|  Chrome Extension: [Connected]         |
|  Last Action: (none)                   |
|  Flow Progress: 0/7 steps              |
+----------------------------------------+
```

---

## State Machine
```
IDLE
  |
  v (Agent clicks "STEP 1: CLICK HERE")
OPEN_URL
  |
  v (URL opened, Chrome confirms page loaded)
WAITING_FOR_CHROME
  |
  v (Chrome says "highlight title field")
CHROME_HIGHLIGHT_ACTIVE
  |
  v (Agent clicks highlighted element on page)
COPY_TITLE_READY
  |
  v (Agent clicks "COPY TITLE" button)
TITLE_COPIED
  |
  v (Agent pastes in Chrome, Chrome confirms)
CHROME_HIGHLIGHT_BODY
  |
  v (Agent clicks highlighted element on page)
COPY_BODY_READY
  |
  ... continues through flow
  |
  v
FLOW_COMPLETE
```

---

## WebSocket Protocol

### Message Format

All messages are JSON with a `type` field:
```json
{
    "type": "message_type",
    "payload": { ... }
}
```

### Messages: Python -> Chrome

| Type | Payload | Description |
|------|---------|-------------|
| `open_url` | `{"url": "https://..."}` | Tell Chrome to navigate to URL |
| `highlight_element` | `{"selector": "#title", "label": "Click here for TITLE"}` | Highlight element on page |
| `clear_highlights` | `{}` | Remove all highlights |
| `request_page_info` | `{}` | Ask Chrome what page/platform we're on |
| `flow_complete` | `{}` | Signal flow is done |

### Messages: Chrome -> Python

| Type | Payload | Description |
|------|---------|-------------|
| `extension_ready` | `{"tab_url": "..."}` | Extension connected |
| `page_loaded` | `{"url": "...", "platform": "skool"}` | Page finished loading |
| `element_clicked` | `{"selector": "#title", "element_type": "input"}` | User clicked highlighted element |
| `element_focused` | `{"selector": "#title"}` | Element now has focus |
| `paste_detected` | `{"selector": "#title", "content_length": 45}` | Paste occurred in element |
| `request_copy` | `{"field": "title"}` | Chrome asking Python to light up copy button |

---

## Flow Definition
```python
FLOWS = {
    "skool_post": {
        "name": "Skool Post",
        "steps": [
            {
                "id": 1,
                "osp_button": "start",
                "osp_label": "STEP 1: CLICK HERE",
                "osp_color": "#00ff00",  # Green
                "action": "open_url",
                "next_trigger": "page_loaded"
            },
            {
                "id": 2,
                "osp_button": None,  # No OSP button, Chrome highlights
                "chrome_action": "highlight",
                "chrome_selector": "[data-placeholder='Title']",
                "chrome_label": "CLICK HERE - Title",
                "next_trigger": "element_focused"
            },
            {
                "id": 3,
                "osp_button": "copy_title",
                "osp_label": "COPY TITLE",
                "osp_color": "#00ff00",
                "action": "copy_to_clipboard",
                "copy_field": "title",
                "next_trigger": "button_clicked"
            },
            {
                "id": 4,
                "osp_button": None,
                "chrome_action": "highlight",
                "chrome_selector": "[data-placeholder='Title']",
                "chrome_label": "CLICK & PASTE (Ctrl+V)",
                "next_trigger": "paste_detected"
            },
            {
                "id": 5,
                "osp_button": None,
                "chrome_action": "highlight",
                "chrome_selector": "[data-placeholder='Write something...']",
                "chrome_label": "CLICK HERE - Body",
                "next_trigger": "element_focused"
            },
            {
                "id": 6,
                "osp_button": "copy_body",
                "osp_label": "COPY BODY",
                "osp_color": "#00ff00",
                "action": "copy_to_clipboard",
                "copy_field": "body",
                "next_trigger": "button_clicked"
            },
            {
                "id": 7,
                "osp_button": None,
                "chrome_action": "highlight",
                "chrome_selector": "[data-placeholder='Write something...']",
                "chrome_label": "CLICK & PASTE (Ctrl+V)",
                "next_trigger": "paste_detected"
            },
            {
                "id": 8,
                "osp_button": None,
                "chrome_action": "highlight",
                "chrome_selector": "button[type='submit'], .post-button",
                "chrome_label": "CLICK TO POST",
                "next_trigger": "element_clicked"
            },
            {
                "id": 9,
                "osp_button": "complete",
                "osp_label": "FLOW COMPLETE!",
                "osp_color": "#00ff00",
                "action": "finish",
                "next_trigger": None
            }
        ]
    }
}
```

---

## Core Python Implementation
```python
#!/usr/bin/env python3
"""
OSP - On-Screen Prompter
Guides AI agents through multi-step workflows
"""

import asyncio
import json
import tkinter as tk
from tkinter import font as tkfont
import websockets
import threading
import pyperclip
from typing import Optional, Dict, Any, Set

# Configuration
WS_HOST = "localhost"
WS_PORT = 8765
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 600


class WebSocketServer:
    """Handles communication with Chrome extension."""
    
    def __init__(self, osp: 'OSPWindow'):
        self.osp = osp
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.server = None
    
    async def handler(self, websocket):
        """Handle incoming WebSocket connections."""
        self.clients.add(websocket)
        print(f"Chrome extension connected. Total clients: {len(self.clients)}")
        self.osp.update_connection_status(True)
        
        try:
            async for message in websocket:
                await self.handle_message(json.loads(message))
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            print(f"Chrome extension disconnected. Total clients: {len(self.clients)}")
            self.osp.update_connection_status(len(self.clients) > 0)
    
    async def handle_message(self, data: Dict[str, Any]):
        """Process messages from Chrome extension."""
        msg_type = data.get("type")
        payload = data.get("payload", {})
        
        print(f"Received from Chrome: {msg_type} - {payload}")
        
        if msg_type == "extension_ready":
            self.osp.on_extension_ready(payload)
        
        elif msg_type == "page_loaded":
            self.osp.on_page_loaded(payload)
        
        elif msg_type == "element_clicked":
            self.osp.on_element_clicked(payload)
        
        elif msg_type == "element_focused":
            self.osp.on_element_focused(payload)
        
        elif msg_type == "paste_detected":
            self.osp.on_paste_detected(payload)
        
        elif msg_type == "request_copy":
            self.osp.on_copy_requested(payload)
    
    async def send(self, msg_type: str, payload: Dict[str, Any] = None):
        """Send message to all connected Chrome extensions."""
        message = json.dumps({
            "type": msg_type,
            "payload": payload or {}
        })
        
        for client in self.clients:
            try:
                await client.send(message)
            except Exception as e:
                print(f"Error sending to client: {e}")
    
    async def start(self):
        """Start the WebSocket server."""
        self.server = await websockets.serve(
            self.handler, WS_HOST, WS_PORT
        )
        print(f"WebSocket server started on ws://{WS_HOST}:{WS_PORT}")
        await self.server.wait_closed()


class OSPWindow:
    """Main On-Screen Prompter window."""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("On-Screen Prompter")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+1500+100")
        self.root.attributes('-topmost', True)
        
        # State
        self.current_flow = None
        self.current_step = 0
        self.post_data = {}  # Title, body, hashtags, URL from API
        self.ws_server: Optional[WebSocketServer] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Build UI
        self._build_ui()
        
        # Start WebSocket in background thread
        self._start_websocket_thread()
    
    def _build_ui(self):
        """Create the UI elements."""
        # Fonts
        self.large_font = tkfont.Font(family="Arial", size=16, weight="bold")
        self.medium_font = tkfont.Font(family="Arial", size=12)
        self.small_font = tkfont.Font(family="Arial", size=10)
        
        # Main instruction button (top)
        self.main_button = tk.Button(
            self.root,
            text="STEP 1: CLICK HERE",
            font=self.large_font,
            bg="#444444",
            fg="white",
            height=3,
            command=self.on_main_button_click
        )
        self.main_button.pack(fill=tk.X, padx=10, pady=10)
        
        # Status frame
        status_frame = tk.LabelFrame(self.root, text="Status", font=self.small_font)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.step_label = tk.Label(status_frame, text="Current Step: Waiting...", font=self.small_font)
        self.step_label.pack(anchor=tk.W, padx=5)
        
        self.platform_label = tk.Label(status_frame, text="Platform: (none)", font=self.small_font)
        self.platform_label.pack(anchor=tk.W, padx=5)
        
        self.post_id_label = tk.Label(status_frame, text="Post ID: (none)", font=self.small_font)
        self.post_id_label.pack(anchor=tk.W, padx=5)
        
        # Action buttons frame
        actions_frame = tk.LabelFrame(self.root, text="Actions", font=self.small_font)
        actions_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.open_url_btn = tk.Button(
            actions_frame,
            text="OPEN URL",
            font=self.medium_font,
            bg="#333333",
            fg="#666666",
            state=tk.DISABLED,
            command=self.on_open_url_click
        )
        self.open_url_btn.pack(fill=tk.X, padx=5, pady=2)
        
        self.copy_title_btn = tk.Button(
            actions_frame,
            text="COPY TITLE",
            font=self.medium_font,
            bg="#333333",
            fg="#666666",
            state=tk.DISABLED,
            command=self.on_copy_title_click
        )
        self.copy_title_btn.pack(fill=tk.X, padx=5, pady=2)
        
        self.copy_body_btn = tk.Button(
            actions_frame,
            text="COPY BODY",
            font=self.medium_font,
            bg="#333333",
            fg="#666666",
            state=tk.DISABLED,
            command=self.on_copy_body_click
        )
        self.copy_body_btn.pack(fill=tk.X, padx=5, pady=2)
        
        self.copy_hashtags_btn = tk.Button(
            actions_frame,
            text="COPY HASHTAGS",
            font=self.medium_font,
            bg="#333333",
            fg="#666666",
            state=tk.DISABLED,
            command=self.on_copy_hashtags_click
        )
        self.copy_hashtags_btn.pack(fill=tk.X, padx=5, pady=2)
        
        # Connection status
        conn_frame = tk.LabelFrame(self.root, text="Connection", font=self.small_font)
        conn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.connection_label = tk.Label(
            conn_frame,
            text="Chrome Extension: Disconnected",
            font=self.small_font,
            fg="red"
        )
        self.connection_label.pack(anchor=tk.W, padx=5)
        
        self.last_action_label = tk.Label(conn_frame, text="Last Action: (none)", font=self.small_font)
        self.last_action_label.pack(anchor=tk.W, padx=5)
        
        self.progress_label = tk.Label(conn_frame, text="Flow Progress: 0/0 steps", font=self.small_font)
        self.progress_label.pack(anchor=tk.W, padx=5)
    
    def _start_websocket_thread(self):
        """Start WebSocket server in background thread."""
        def run_ws():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.ws_server = WebSocketServer(self)
            self.loop.run_until_complete(self.ws_server.start())
        
        thread = threading.Thread(target=run_ws, daemon=True)
        thread.start()
    
    def send_to_chrome(self, msg_type: str, payload: Dict[str, Any] = None):
        """Send message to Chrome extension."""
        if self.loop and self.ws_server:
            asyncio.run_coroutine_threadsafe(
                self.ws_server.send(msg_type, payload),
                self.loop
            )
    
    # === UI Update Methods ===
    
    def update_connection_status(self, connected: bool):
        """Update connection status display."""
        self.root.after(0, lambda: self._update_connection_ui(connected))
    
    def _update_connection_ui(self, connected: bool):
        if connected:
            self.connection_label.config(text="Chrome Extension: Connected", fg="green")
        else:
            self.connection_label.config(text="Chrome Extension: Disconnected", fg="red")
    
    def highlight_button(self, button: tk.Button, active: bool):
        """Highlight or dim a button."""
        if active:
            button.config(bg="#00ff00", fg="black", state=tk.NORMAL)
        else:
            button.config(bg="#333333", fg="#666666", state=tk.DISABLED)
    
    def update_main_button(self, text: str, color: str = "#00ff00"):
        """Update the main instruction button."""
        self.main_button.config(text=text, bg=color, fg="black" if color == "#00ff00" else "white")
    
    def update_step(self, step_text: str):
        """Update current step display."""
        self.step_label.config(text=f"Current Step: {step_text}")
    
    def update_last_action(self, action: str):
        """Update last action display."""
        self.last_action_label.config(text=f"Last Action: {action}")
    
    # === Event Handlers ===
    
    def on_main_button_click(self):
        """Handle main button click - starts the flow."""
        self.update_last_action("Main button clicked")
        self.highlight_button(self.open_url_btn, True)
        self.update_main_button("NOW CLICK 'OPEN URL'", "#ffff00")
        self.update_step("Step 1: Open the posting URL")
    
    def on_open_url_click(self):
        """Handle Open URL button click."""
        # In real implementation, get URL from your API
        url = self.post_data.get("url", "https://www.skool.com/your-community/post")
        self.send_to_chrome("open_url", {"url": url})
        self.highlight_button(self.open_url_btn, False)
        self.update_main_button("WAIT FOR PAGE...", "#ffff00")
        self.update_last_action(f"Opening URL: {url}")
    
    def on_copy_title_click(self):
        """Copy title to clipboard."""
        title = self.post_data.get("title", "Sample Title")
        pyperclip.copy(title)
        self.highlight_button(self.copy_title_btn, False)
        self.update_last_action(f"Copied title: {title[:30]}...")
        
        # Tell Chrome to highlight where to paste
        self.send_to_chrome("highlight_element", {
            "selector": "[data-placeholder='Title']",
            "label": "CLICK HERE & PASTE (Ctrl+V)"
        })
        self.update_main_button("CLICK HIGHLIGHTED AREA IN CHROME", "#00ffff")
    
    def on_copy_body_click(self):
        """Copy body to clipboard."""
        body = self.post_data.get("body", "Sample body content")
        pyperclip.copy(body)
        self.highlight_button(self.copy_body_btn, False)
        self.update_last_action(f"Copied body: {body[:30]}...")
        
        self.send_to_chrome("highlight_element", {
            "selector": "[data-placeholder='Write something...']",
            "label": "CLICK HERE & PASTE (Ctrl+V)"
        })
        self.update_main_button("CLICK HIGHLIGHTED AREA IN CHROME", "#00ffff")
    
    def on_copy_hashtags_click(self):
        """Copy hashtags to clipboard."""
        hashtags = self.post_data.get("hashtags", "#sample #hashtags")
        pyperclip.copy(hashtags)
        self.highlight_button(self.copy_hashtags_btn, False)
        self.update_last_action(f"Copied hashtags")
    
    # === Chrome Event Handlers ===
    
    def on_extension_ready(self, payload: Dict):
        """Chrome extension connected and ready."""
        self.root.after(0, lambda: self.update_main_button("STEP 1: CLICK HERE", "#00ff00"))
    
    def on_page_loaded(self, payload: Dict):
        """Page loaded in Chrome."""
        platform = payload.get("platform", "unknown")
        self.root.after(0, lambda: self._handle_page_loaded(platform))
    
    def _handle_page_loaded(self, platform: str):
        self.platform_label.config(text=f"Platform: {platform}")
        self.update_last_action(f"Page loaded: {platform}")
        
        # Tell Chrome to highlight the first field
        self.send_to_chrome("highlight_element", {
            "selector": "[data-placeholder='Title'], .title-input, #title",
            "label": "CLICK HERE - Title"
        })
        self.update_main_button("CLICK HIGHLIGHTED AREA IN CHROME", "#00ffff")
    
    def on_element_focused(self, payload: Dict):
        """Element was focused/clicked in Chrome."""
        selector = payload.get("selector", "")
        self.root.after(0, lambda: self._handle_element_focused(selector))
    
    def _handle_element_focused(self, selector: str):
        self.update_last_action(f"Element focused: {selector}")
        
        # Determine which copy button to light up
        if "title" in selector.lower():
            self.highlight_button(self.copy_title_btn, True)
            self.update_main_button("NOW CLICK 'COPY TITLE'", "#00ff00")
        elif "write" in selector.lower() or "body" in selector.lower():
            self.highlight_button(self.copy_body_btn, True)
            self.update_main_button("NOW CLICK 'COPY BODY'", "#00ff00")
    
    def on_element_clicked(self, payload: Dict):
        """Element was clicked in Chrome."""
        self.root.after(0, lambda: self.update_last_action(f"Clicked: {payload.get('selector')}"))
    
    def on_paste_detected(self, payload: Dict):
        """Paste was detected in Chrome."""
        selector = payload.get("selector", "")
        self.root.after(0, lambda: self._handle_paste_detected(selector))
    
    def _handle_paste_detected(self, selector: str):
        self.update_last_action(f"Paste detected in: {selector}")
        self.send_to_chrome("clear_highlights", {})
        
        # Move to next step based on what was pasted
        if "title" in selector.lower():
            # Now highlight body
            self.send_to_chrome("highlight_element", {
                "selector": "[data-placeholder='Write something...'], .body-input, #body",
                "label": "CLICK HERE - Body"
            })
            self.update_main_button("CLICK HIGHLIGHTED AREA IN CHROME", "#00ffff")
        else:
            # Done with text, highlight submit
            self.send_to_chrome("highlight_element", {
                "selector": "button[type='submit'], .post-btn, #submit",
                "label": "CLICK TO POST!"
            })
            self.update_main_button("CLICK 'POST' BUTTON IN CHROME", "#00ff00")
    
    def on_copy_requested(self, payload: Dict):
        """Chrome is requesting a copy action."""
        field = payload.get("field", "")
        self.root.after(0, lambda: self._handle_copy_request(field))
    
    def _handle_copy_request(self, field: str):
        if field == "title":
            self.highlight_button(self.copy_title_btn, True)
            self.update_main_button("NOW CLICK 'COPY TITLE'", "#00ff00")
        elif field == "body":
            self.highlight_button(self.copy_body_btn, True)
            self.update_main_button("NOW CLICK 'COPY BODY'", "#00ff00")
    
    def run(self):
        """Start the application."""
        self.root.mainloop()


def main():
    app = OSPWindow()
    
    # Example: Load post data from your API
    app.post_data = {
        "title": "My Amazing Post Title",
        "body": "This is the body of my post. It contains all the great content!",
        "hashtags": "#awesome #content #post",
        "url": "https://www.skool.com/your-community/post"
    }
    
    app.run()


if __name__ == "__main__":
    main()
```

---

## Key Features

1. **Single Clear Instruction**: Main button always shows exactly what the agent should do next
2. **Color Coding**:
   - Green (#00ff00) = Click this NOW
   - Yellow (#ffff00) = Waiting/transition
   - Cyan (#00ffff) = Action needed in Chrome
3. **WebSocket Coordination**: Real-time communication with Chrome extension
4. **Clipboard Management**: Copy buttons put content in clipboard for paste
5. **State Tracking**: Always knows what step we're on

---

## API Integration Point
```python
# Where to fetch post data from your Social Dashboard
def load_next_post():
    response = requests.get("https://social.sterlingcooley.com/api/gui_post_queue/next")
    data = response.json()
    return {
        "title": data["title"],
        "body": data["content"],
        "hashtags": data["hashtags"],
        "url": data["target_url"],
        "platform": data["platform"]
    }
```