# WINDOWS10-OSP-PYTHON-FIX.md
# On-Screen Prompter (OSP) - Simplified Control Panel

## What the OSP Becomes

The OSP is no longer trying to be "smart." It's now a **dumb control panel** - a simple Python GUI that:

1. Fetches post data from the Social Dashboard API
2. Displays static buttons in predictable locations
3. Handles clipboard operations when buttons are clicked
4. Reports success/failure back to the API

**The Ubuntu controller uses vision to find and click these buttons.** The OSP doesn't make decisions - it just provides services (clipboard copy, URL opening, status reporting).

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   CHROME BROWSER (Social Media Platform)          │   OSP      │
│   ┌───────────────────────────────────────────┐   │  PANEL     │
│   │                                           │   │            │
│   │   Instagram / Facebook / TikTok / etc.    │   │  [Open URL]│
│   │                                           │   │            │
│   │   ┌─────────────────────────────────┐     │   │  [Copy     │
│   │   │  Title field                    │     │   │   Title]   │
│   │   └─────────────────────────────────┘     │   │            │
│   │                                           │   │  [Copy     │
│   │   ┌─────────────────────────────────┐     │   │   Body]    │
│   │   │  Body/Caption field             │     │   │            │
│   │   │                                 │     │   │  [Copy     │
│   │   │                                 │     │   │   Image]   │
│   │   └─────────────────────────────────┘     │   │            │
│   │                                           │   │  ─────────  │
│   │   ┌─────────────────────────────────┐     │   │  □ Email   │
│   │   │  Image/Media area               │     │   │   Toggle   │
│   │   │                                 │     │   │  ─────────  │
│   │   └─────────────────────────────────┘     │   │            │
│   │                                           │   │  [POST]    │
│   │                                           │   │            │
│   │                        [Share/Post btn]   │   │  ─────────  │
│   │                                           │   │  [SUCCESS] │
│   └───────────────────────────────────────────┘   │  [FAILED]  │
│                                                   │            │
└───────────────────────────────────────────────────┴────────────┘
```

---

## The Problem with the Old OSP

### What We Built (Too Complex)

```python
# OLD APPROACH - Don't do this
class OldOSP:
    def __init__(self):
        self.current_step = 0
        self.steps = ["copy_title", "copy_body", "copy_image", "post"]
    
    def on_button_click(self):
        # Execute current step
        if self.current_step == 0:
            self.copy_title()
            self.button.text = "Copy Body"  # Button changes!
            self.current_step = 1
        elif self.current_step == 1:
            self.copy_body()
            self.button.text = "Copy Image"  # Button changes again!
            self.current_step = 2
        # ... and so on
```

**Problems:**
- Button labels change dynamically - vision can't reliably find them
- State machine in the OSP - but intelligence should be in Ubuntu
- WebSocket to Chrome extension - unnecessary complexity
- Single button that morphs - confusing for automation

### What We Need (Simple)

```python
# NEW APPROACH - Static buttons, no state machine
class SimpleOSP:
    def __init__(self):
        # Buttons never change labels
        self.btn_open_url = Button("Open URL", self.open_url)
        self.btn_copy_title = Button("Copy Title", self.copy_title)
        self.btn_copy_body = Button("Copy Body", self.copy_body)
        self.btn_copy_image = Button("Copy Image", self.copy_image)
        self.btn_post = Button("POST", self.mark_ready)
        self.btn_success = Button("✓ SUCCESS", self.report_success, color="green")
        self.btn_failed = Button("✗ FAILED", self.report_failure, color="red")
    
    def copy_title(self):
        # Just copy to clipboard, nothing else
        pyperclip.copy(self.current_post.title)
    
    def copy_body(self):
        pyperclip.copy(self.current_post.body)
    
    # Each button does ONE thing
```

---

## Simplified OSP Specification

### GUI Layout

```
┌──────────────────────────────────┐
│         SOCIAL POSTER            │  ← Title bar
├──────────────────────────────────┤
│  Platform: Instagram             │  ← Current platform
│  Post ID: abc123                 │  ← Post identifier
├──────────────────────────────────┤
│                                  │
│  ┌────────────────────────────┐  │
│  │       OPEN URL             │  │  ← Button 1: Opens platform URL
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY TITLE           │  │  ← Button 2: Copies title to clipboard
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY BODY            │  │  ← Button 3: Copies body text to clipboard
│  └────────────────────────────┘  │
│                                  │
│  ┌────────────────────────────┐  │
│  │       COPY IMAGE           │  │  ← Button 4: Copies image to clipboard
│  └────────────────────────────┘  │
│                                  │
│  ──────────────────────────────  │
│                                  │
│  ☐ Send Email Notification       │  ← Checkbox (if applicable)
│                                  │
│  ──────────────────────────────  │
│                                  │
│  ┌────────────────────────────┐  │
│  │          POST              │  │  ← Button 5: Signals ready to post
│  └────────────────────────────┘  │
│                                  │
│  ──────────────────────────────  │
│                                  │
│  ┌────────────┐ ┌────────────┐   │
│  │  SUCCESS   │ │   FAILED   │   │  ← Status buttons (green/red)
│  │     ✓      │ │     ✗      │   │
│  └────────────┘ └────────────┘   │
│                                  │
├──────────────────────────────────┤
│  Status: Waiting for action...   │  ← Status message
└──────────────────────────────────┘
```

### Window Properties

| Property | Value |
|----------|-------|
| Width | 300px |
| Height | 500px |
| Position | Right edge of screen |
| Always on Top | Yes |
| Resizable | No |
| Background | Dark gray (#2d2d2d) |
| Button Height | 50px each |
| Button Font | Bold, 14pt, White |

### Button Specifications

| Button | Label (NEVER CHANGES) | Color | Action |
|--------|----------------------|-------|--------|
| Open URL | "OPEN URL" | Blue (#3498db) | Opens platform URL in Chrome |
| Copy Title | "COPY TITLE" | Blue (#3498db) | Copies title to clipboard |
| Copy Body | "COPY BODY" | Blue (#3498db) | Copies body text to clipboard |
| Copy Image | "COPY IMAGE" | Blue (#3498db) | Copies image to clipboard |
| Post | "POST" | Orange (#e67e22) | Signals workflow ready for posting |
| Success | "✓ SUCCESS" | Green (#27ae60) | Reports success to API |
| Failed | "✗ FAILED" | Red (#e74c3c) | Reports failure to API |

---

## Complete Python Implementation

### File: `osp_simple.py`

```python
"""
Simplified On-Screen Prompter (OSP) for Social Media Posting.

This is a DUMB control panel - it doesn't make decisions.
It provides clipboard services and status reporting.
The Ubuntu controller uses vision to click these buttons.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import requests
import webbrowser
import threading
import time
from PIL import Image, ImageTk
import io
import base64
from dataclasses import dataclass
from typing import Optional
import json


@dataclass
class PostData:
    """Data for a single post."""
    id: str
    platform: str
    url: str
    title: str
    body: str
    image_path: Optional[str]
    image_base64: Optional[str]
    send_email: bool


class SimpleOSP:
    """Simplified On-Screen Prompter - a dumb control panel."""
    
    # API Configuration
    API_BASE_URL = "https://social.sterlingcooley.com/api"
    POLL_INTERVAL = 10  # seconds
    
    # Window Configuration
    WINDOW_WIDTH = 300
    WINDOW_HEIGHT = 550
    BUTTON_HEIGHT = 50
    PADDING = 10
    
    # Colors
    COLOR_BG = "#2d2d2d"
    COLOR_BUTTON_BLUE = "#3498db"
    COLOR_BUTTON_ORANGE = "#e67e22"
    COLOR_BUTTON_GREEN = "#27ae60"
    COLOR_BUTTON_RED = "#e74c3c"
    COLOR_TEXT = "#ffffff"
    COLOR_TEXT_MUTED = "#95a5a6"
    
    def __init__(self):
        """Initialize the OSP window."""
        self.current_post: Optional[PostData] = None
        self.running = True
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("Social Poster")
        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.root.configure(bg=self.COLOR_BG)
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)
        
        # Position window on right edge of screen
        screen_width = self.root.winfo_screenwidth()
        x_position = screen_width - self.WINDOW_WIDTH - 10
        self.root.geometry(f"+{x_position}+100")
        
        # Build UI
        self._create_widgets()
        
        # Start polling for posts
        self._start_polling()
    
    def _create_widgets(self):
        """Create all UI widgets."""
        # Header frame
        header_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        header_frame.pack(fill=tk.X, padx=self.PADDING, pady=self.PADDING)
        
        self.platform_label = tk.Label(
            header_frame,
            text="Platform: --",
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT,
            font=("Arial", 12, "bold")
        )
        self.platform_label.pack(anchor=tk.W)
        
        self.post_id_label = tk.Label(
            header_frame,
            text="Post ID: --",
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT_MUTED,
            font=("Arial", 10)
        )
        self.post_id_label.pack(anchor=tk.W)
        
        # Separator
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=self.PADDING)
        
        # Button frame
        button_frame = tk.Frame(self.root, bg=self.COLOR_BG)
        button_frame.pack(fill=tk.BOTH, expand=True, padx=self.PADDING, pady=self.PADDING)
        
        # OPEN URL Button
        self.btn_open_url = tk.Button(
            button_frame,
            text="OPEN URL",
            bg=self.COLOR_BUTTON_BLUE,
            fg=self.COLOR_TEXT,
            font=("Arial", 12, "bold"),
            height=2,
            command=self._on_open_url,
            state=tk.DISABLED
        )
        self.btn_open_url.pack(fill=tk.X, pady=5)
        
        # COPY TITLE Button
        self.btn_copy_title = tk.Button(
            button_frame,
            text="COPY TITLE",
            bg=self.COLOR_BUTTON_BLUE,
            fg=self.COLOR_TEXT,
            font=("Arial", 12, "bold"),
            height=2,
            command=self._on_copy_title,
            state=tk.DISABLED
        )
        self.btn_copy_title.pack(fill=tk.X, pady=5)
        
        # COPY BODY Button
        self.btn_copy_body = tk.Button(
            button_frame,
            text="COPY BODY",
            bg=self.COLOR_BUTTON_BLUE,
            fg=self.COLOR_TEXT,
            font=("Arial", 12, "bold"),
            height=2,
            command=self._on_copy_body,
            state=tk.DISABLED
        )
        self.btn_copy_body.pack(fill=tk.X, pady=5)
        
        # COPY IMAGE Button
        self.btn_copy_image = tk.Button(
            button_frame,
            text="COPY IMAGE",
            bg=self.COLOR_BUTTON_BLUE,
            fg=self.COLOR_TEXT,
            font=("Arial", 12, "bold"),
            height=2,
            command=self._on_copy_image,
            state=tk.DISABLED
        )
        self.btn_copy_image.pack(fill=tk.X, pady=5)
        
        # Separator
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Email checkbox frame
        self.email_frame = tk.Frame(button_frame, bg=self.COLOR_BG)
        self.email_frame.pack(fill=tk.X, pady=5)
        
        self.email_var = tk.BooleanVar()
        self.email_checkbox = tk.Checkbutton(
            self.email_frame,
            text="Send Email Notification",
            variable=self.email_var,
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT,
            selectcolor=self.COLOR_BG,
            font=("Arial", 10),
            state=tk.DISABLED
        )
        self.email_checkbox.pack(anchor=tk.W)
        
        # Separator
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # POST Button
        self.btn_post = tk.Button(
            button_frame,
            text="POST",
            bg=self.COLOR_BUTTON_ORANGE,
            fg=self.COLOR_TEXT,
            font=("Arial", 14, "bold"),
            height=2,
            command=self._on_post,
            state=tk.DISABLED
        )
        self.btn_post.pack(fill=tk.X, pady=5)
        
        # Separator
        ttk.Separator(button_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # Success/Failed button frame
        result_frame = tk.Frame(button_frame, bg=self.COLOR_BG)
        result_frame.pack(fill=tk.X, pady=5)
        
        self.btn_success = tk.Button(
            result_frame,
            text="✓ SUCCESS",
            bg=self.COLOR_BUTTON_GREEN,
            fg=self.COLOR_TEXT,
            font=("Arial", 11, "bold"),
            height=2,
            width=12,
            command=self._on_success,
            state=tk.DISABLED
        )
        self.btn_success.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        
        self.btn_failed = tk.Button(
            result_frame,
            text="✗ FAILED",
            bg=self.COLOR_BUTTON_RED,
            fg=self.COLOR_TEXT,
            font=("Arial", 11, "bold"),
            height=2,
            width=12,
            command=self._on_failed,
            state=tk.DISABLED
        )
        self.btn_failed.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        
        # Status bar
        self.status_label = tk.Label(
            self.root,
            text="Status: Waiting for post...",
            bg=self.COLOR_BG,
            fg=self.COLOR_TEXT_MUTED,
            font=("Arial", 9)
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=self.PADDING, pady=self.PADDING)
    
    def _update_status(self, message: str):
        """Update the status bar message."""
        self.status_label.config(text=f"Status: {message}")
        self.root.update()
    
    def _enable_buttons(self, enable: bool = True):
        """Enable or disable all action buttons."""
        state = tk.NORMAL if enable else tk.DISABLED
        
        self.btn_open_url.config(state=state)
        self.btn_copy_title.config(state=state)
        self.btn_copy_body.config(state=state)
        self.btn_copy_image.config(state=state)
        self.btn_post.config(state=state)
        self.btn_success.config(state=state)
        self.btn_failed.config(state=state)
        self.email_checkbox.config(state=state)
    
    def _load_post(self, post_data: dict):
        """Load a post into the UI."""
        self.current_post = PostData(
            id=post_data.get("id", ""),
            platform=post_data.get("platform", ""),
            url=post_data.get("url", ""),
            title=post_data.get("title", ""),
            body=post_data.get("body", ""),
            image_path=post_data.get("image_path"),
            image_base64=post_data.get("image_base64"),
            send_email=post_data.get("send_email", False)
        )
        
        # Update labels
        self.platform_label.config(text=f"Platform: {self.current_post.platform}")
        self.post_id_label.config(text=f"Post ID: {self.current_post.id[:20]}...")
        
        # Set email checkbox
        self.email_var.set(self.current_post.send_email)
        
        # Enable buttons
        self._enable_buttons(True)
        self._update_status("Post loaded - ready for action")
    
    def _clear_post(self):
        """Clear current post and disable buttons."""
        self.current_post = None
        self.platform_label.config(text="Platform: --")
        self.post_id_label.config(text="Post ID: --")
        self.email_var.set(False)
        self._enable_buttons(False)
        self._update_status("Waiting for post...")
    
    # ==================== Button Actions ====================
    
    def _on_open_url(self):
        """Open the platform URL in Chrome."""
        if not self.current_post:
            return
        
        try:
            webbrowser.open(self.current_post.url)
            self._update_status("Opened URL in browser")
        except Exception as e:
            self._update_status(f"Error opening URL: {e}")
    
    def _on_copy_title(self):
        """Copy title to clipboard."""
        if not self.current_post:
            return
        
        try:
            pyperclip.copy(self.current_post.title)
            self._update_status("Title copied to clipboard")
        except Exception as e:
            self._update_status(f"Error copying title: {e}")
    
    def _on_copy_body(self):
        """Copy body text to clipboard."""
        if not self.current_post:
            return
        
        try:
            pyperclip.copy(self.current_post.body)
            self._update_status("Body copied to clipboard")
        except Exception as e:
            self._update_status(f"Error copying body: {e}")
    
    def _on_copy_image(self):
        """Copy image to clipboard."""
        if not self.current_post:
            return
        
        try:
            # If we have a file path, use that
            if self.current_post.image_path:
                self._copy_image_file(self.current_post.image_path)
            # If we have base64, decode and copy
            elif self.current_post.image_base64:
                self._copy_image_base64(self.current_post.image_base64)
            else:
                self._update_status("No image available")
                return
            
            self._update_status("Image copied to clipboard")
        except Exception as e:
            self._update_status(f"Error copying image: {e}")
    
    def _copy_image_file(self, path: str):
        """Copy image from file path to clipboard."""
        # Use PowerShell to copy image to clipboard
        import subprocess
        
        ps_script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $image = [System.Drawing.Image]::FromFile("{path}")
        [System.Windows.Forms.Clipboard]::SetImage($image)
        '''
        
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )
    
    def _copy_image_base64(self, base64_data: str):
        """Copy image from base64 to clipboard."""
        import subprocess
        
        # Decode base64 to temp file, then copy
        image_data = base64.b64decode(base64_data)
        temp_path = "C:\\PostQueue\\temp_image.png"
        
        with open(temp_path, "wb") as f:
            f.write(image_data)
        
        self._copy_image_file(temp_path)
    
    def _on_post(self):
        """Signal that content is ready to be posted."""
        if not self.current_post:
            return
        
        self._update_status("Ready to post - click platform's Post button")
        
        # Update API that we're about to post
        try:
            requests.post(
                f"{self.API_BASE_URL}/gui_post_queue/{self.current_post.id}/posting",
                json={"status": "posting"},
                timeout=5
            )
        except Exception:
            pass  # Non-critical
    
    def _on_success(self):
        """Report successful post to API."""
        if not self.current_post:
            return
        
        try:
            response = requests.post(
                f"{self.API_BASE_URL}/gui_post_queue/{self.current_post.id}/complete",
                json={
                    "status": "success",
                    "send_email": self.email_var.get()
                },
                timeout=10
            )
            
            if response.status_code == 200:
                self._update_status("Success reported!")
                self._clear_post()
            else:
                self._update_status(f"API error: {response.status_code}")
                
        except Exception as e:
            self._update_status(f"Error reporting success: {e}")
    
    def _on_failed(self):
        """Report failed post to API."""
        if not self.current_post:
            return
        
        try:
            response = requests.post(
                f"{self.API_BASE_URL}/gui_post_queue/{self.current_post.id}/failed",
                json={"status": "failed"},
                timeout=10
            )
            
            if response.status_code == 200:
                self._update_status("Failure reported")
                self._clear_post()
            else:
                self._update_status(f"API error: {response.status_code}")
                
        except Exception as e:
            self._update_status(f"Error reporting failure: {e}")
    
    # ==================== API Polling ====================
    
    def _start_polling(self):
        """Start background thread to poll for new posts."""
        def poll_loop():
            while self.running:
                if not self.current_post:
                    self._fetch_next_post()
                time.sleep(self.POLL_INTERVAL)
        
        thread = threading.Thread(target=poll_loop, daemon=True)
        thread.start()
    
    def _fetch_next_post(self):
        """Fetch the next pending post from API."""
        try:
            response = requests.get(
                f"{self.API_BASE_URL}/gui_post_queue/pending",
                timeout=10
            )
            
            if response.status_code == 200:
                posts = response.json()
                if posts and len(posts) > 0:
                    # Schedule UI update on main thread
                    self.root.after(0, lambda: self._load_post(posts[0]))
                    
        except Exception as e:
            print(f"Poll error: {e}")
    
    # ==================== Main Loop ====================
    
    def run(self):
        """Start the OSP main loop."""
        try:
            self.root.mainloop()
        finally:
            self.running = False
    
    def stop(self):
        """Stop the OSP."""
        self.running = False
        self.root.quit()


def main():
    """Entry point."""
    osp = SimpleOSP()
    osp.run()


if __name__ == "__main__":
    main()
```

---

## What Changed from the Old OSP

### Removed Features

| Old Feature | Why Removed |
|-------------|-------------|
| WebSocket to Chrome Extension | Unnecessary complexity - Ubuntu controls everything |
| Dynamic button labels | Buttons must be static for vision to find them |
| Step-by-step state machine | Intelligence moved to Ubuntu controller |
| Auto-advance to next step | Each button is independent now |
| Chrome extension communication | Not needed - OSP just does clipboard |

### Kept Features

| Feature | Why Kept |
|---------|----------|
| API polling for posts | OSP still needs to know what to post |
| Clipboard copy functions | Core utility that Ubuntu needs |
| Success/Failed reporting | Feedback loop to API |
| Always-on-top window | Must be visible for vision |
| Right-side positioning | Consistent location for automation |

### New Design Principles

1. **Static Labels** - Button text NEVER changes
2. **Independent Actions** - Each button does ONE thing
3. **No State Tracking** - OSP doesn't know what step we're on
4. **Dumb Panel** - Zero decision-making logic
5. **Vision-Friendly** - High contrast, predictable layout

---

## How Ubuntu Uses the OSP

The Ubuntu controller's workflow now interacts with the OSP:

```python
# Ubuntu controller workflow (simplified)
class PlatformWorkflow:
    
    def execute_post(self, post_id: str):
        # Step 1: Find and click "OPEN URL" on OSP
        osp_open = self.vision.find_element(screenshot, "OPEN URL blue button")
        self.input.click(osp_open.x, osp_open.y)
        time.sleep(3)  # Wait for browser
        
        # Step 2: Find and click "COPY TITLE" on OSP
        osp_title = self.vision.find_element(screenshot, "COPY TITLE blue button")
        self.input.click(osp_title.x, osp_title.y)
        time.sleep(0.5)
        
        # Step 3: Click on platform's title field
        title_field = self.vision.find_element(screenshot, "title input field on Instagram")
        self.input.click(title_field.x, title_field.y)
        self.input.paste()  # Ctrl+V
        
        # Step 4: Find and click "COPY BODY" on OSP
        osp_body = self.vision.find_element(screenshot, "COPY BODY blue button")
        self.input.click(osp_body.x, osp_body.y)
        time.sleep(0.5)
        
        # Step 5: Click on platform's body field
        body_field = self.vision.find_element(screenshot, "caption input field on Instagram")
        self.input.click(body_field.x, body_field.y)
        self.input.paste()  # Ctrl+V
        
        # Step 6: Find and click "COPY IMAGE" on OSP
        osp_image = self.vision.find_element(screenshot, "COPY IMAGE blue button")
        self.input.click(osp_image.x, osp_image.y)
        time.sleep(0.5)
        
        # Step 7: Click on platform's image upload area and paste
        upload_area = self.vision.find_element(screenshot, "image upload button on Instagram")
        self.input.click(upload_area.x, upload_area.y)
        self.input.paste()  # Ctrl+V
        
        # Step 8: Click POST on OSP to signal ready
        osp_post = self.vision.find_element(screenshot, "POST orange button")
        self.input.click(osp_post.x, osp_post.y)
        
        # Step 9: Click platform's actual Share/Post button
        share_btn = self.vision.find_element(screenshot, "Share button on Instagram")
        self.input.click(share_btn.x, share_btn.y)
        
        # Step 10: Verify success and click SUCCESS or FAILED
        time.sleep(5)
        if self.verify_post_success():
            success_btn = self.vision.find_element(screenshot, "SUCCESS green button")
            self.input.click(success_btn.x, success_btn.y)
        else:
            failed_btn = self.vision.find_element(screenshot, "FAILED red button")
            self.input.click(failed_btn.x, failed_btn.y)
```

---

## Dependencies

```
# requirements.txt for Windows 10 OSP
tkinter          # Built into Python
pyperclip>=1.8.0 # Clipboard operations
requests>=2.31.0 # API communication
Pillow>=10.0.0   # Image handling
```

Install:
```powershell
pip install pyperclip requests Pillow
```

---

## Running the OSP

### Manual Start
```powershell
cd C:\OSP
python osp_simple.py
```

### Auto-Start with Windows
```powershell
# Create shortcut in Startup folder
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\OSP.lnk")
$Shortcut.TargetPath = "pythonw.exe"
$Shortcut.Arguments = "C:\OSP\osp_simple.py"
$Shortcut.WorkingDirectory = "C:\OSP"
$Shortcut.Save()
```

---

## Testing the OSP

### Test 1: Window Appears Correctly
```powershell
python osp_simple.py
# Expected: Window appears on right side of screen with all buttons visible
```

### Test 2: Buttons Are Clickable
- Click each button manually
- Verify status bar updates
- Verify clipboard operations work

### Test 3: API Integration
```powershell
# Create a test post via API
curl -X POST "https://social.sterlingcooley.com/api/gui_post_queue" `
  -H "Content-Type: application/json" `
  -d '{"platform":"instagram","title":"Test","body":"Test body","url":"https://instagram.com"}'

# OSP should pick it up within 10 seconds
```

### Test 4: Vision Can Find Buttons
From Ubuntu:
```python
from vision_finder import VisionFinder
from vnc_capture import VNCCapture

capture = VNCCapture()
vision = VisionFinder()

screenshot = capture.capture()

# Try to find each button
buttons = ["OPEN URL", "COPY TITLE", "COPY BODY", "COPY IMAGE", "POST", "SUCCESS", "FAILED"]
for btn in buttons:
    element = vision.find_element(screenshot, f"{btn} button on the OSP panel")
    print(f"{btn}: {element}")
```

---

## Troubleshooting

### OSP Window Not Visible
```powershell
# Check if process is running
Get-Process python* | Select-Object Id, ProcessName, MainWindowTitle

# Kill and restart
Get-Process python* | Stop-Process -Force
python C:\OSP\osp_simple.py
```

### Clipboard Not Working
```powershell
# Test clipboard manually
python -c "import pyperclip; pyperclip.copy('test'); print(pyperclip.paste())"
# Expected: test
```

### Image Copy Failing
```powershell
# Test image clipboard with PowerShell
Add-Type -AssemblyName System.Windows.Forms
$image = [System.Drawing.Image]::FromFile("C:\PostQueue\test.jpg")
[System.Windows.Forms.Clipboard]::SetImage($image)
# Should not throw error
```

### API Connection Issues
```powershell
# Test API endpoint
curl "https://social.sterlingcooley.com/api/gui_post_queue/pending"
# Expected: JSON response (may be empty array)
```

---

## File Structure

```
C:\OSP\
├── osp_simple.py          # Main OSP application
├── requirements.txt       # Dependencies
└── logs\
    └── osp.log            # Log file (optional)

C:\PostQueue\
├── pending\               # Incoming content
├── processing\            # Currently posting
├── completed\             # Successfully posted
└── temp_image.png         # Temp file for clipboard operations
```

---

## Summary

The simplified OSP is now:
- **A dumb control panel** with static buttons
- **A clipboard helper** that copies content when clicked
- **A status reporter** that tells the API success/failure
- **Vision-friendly** with predictable button locations
- **Zero intelligence** - all decisions made by Ubuntu

Ubuntu's Python controller:
1. Uses vision to find OSP buttons
2. Clicks buttons to trigger clipboard copies
3. Pastes content into platform fields
4. Clicks SUCCESS or FAILED to complete the workflow