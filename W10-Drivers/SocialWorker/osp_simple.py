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
import os
from pathlib import Path


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
        
        # Ensure path exists
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")
        
        ps_script = f'''
        Add-Type -AssemblyName System.Windows.Forms
        $image = [System.Drawing.Image]::FromFile("{path}")
        [System.Windows.Forms.Clipboard]::SetImage($image)
        '''
        
        subprocess.run(
            ["powershell", "-Command", ps_script],
            capture_output=True,
            timeout=10,
            check=True
        )
    
    def _copy_image_base64(self, base64_data: str):
        """Copy image from base64 to clipboard."""
        # Decode base64 to temp file, then copy
        image_data = base64.b64decode(base64_data)
        
        # Create PostQueue directory if it doesn't exist
        queue_dir = Path("C:/PostQueue")
        queue_dir.mkdir(parents=True, exist_ok=True)
        
        temp_path = queue_dir / "temp_image.png"
        
        with open(temp_path, "wb") as f:
            f.write(image_data)
        
        self._copy_image_file(str(temp_path))
    
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
