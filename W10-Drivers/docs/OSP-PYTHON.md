# On-Screen Prompter - Social Media Post Queue GUI

## Overview

A Windows 10 desktop application that displays a persistent sidebar GUI on the right edge of the screen. It connects to the Social Dashboard API (social.sterlingcooley.com) to fetch queued social media posts and provides an interface for the Ubuntu poster agent (or human operator) to process them one-by-one.

Think of it like an **on-screen keyboard** but instead of ABCD keys, it has action buttons: Copy Title, Copy Body, Copy Picture, Next, Mark Complete, Mark Failed, etc.

---

## Core Concept

```
┌─────────────────────────────────────────┬──────────────────────┐
│                                         │  ON-SCREEN PROMPTER  │
│                                         │  ──────────────────  │
│                                         │  Platform: Instagram │
│                                         │  Status: Ready       │
│                                         │  Queue: 3 posts      │
│          MAIN DESKTOP                   │  ──────────────────  │
│          (Other apps)                   │                      │
│                                         │  [IMAGE PREVIEW]     │
│                                         │                      │
│                                         │  Title:              │
│                                         │  "New Product..."    │
│                                         │                      │
│                                         │  Caption:            │
│                                         │  "Check out our..."  │
│                                         │                      │
│                                         │  ──────────────────  │
│                                         │  [Copy Title]        │
│                                         │  [Copy Caption]      │
│                                         │  [Copy Image]        │
│                                         │  ──────────────────  │
│                                         │  [Mark Complete ✓]   │
│                                         │  [Mark Failed ✗]     │
│                                         │  [Skip / Next →]     │
│                                         │  ──────────────────  │
│                                         │  [Refresh Queue]     │
│                                         │  [Settings ⚙]        │
└─────────────────────────────────────────┴──────────────────────┘
                  85%                              15%
```

---

## Requirements

### Window Behavior
- **Always on top** - Stays visible above other windows
- **Docked right** - Snaps to right edge of screen
- **Fixed width** - 15% of screen width (240px on 1600px screen)
- **Full height** - Spans entire screen height (1200px)
- **No taskbar entry** (optional) - Minimal footprint
- **Frameless or minimal frame** - Maximum content area

### API Integration
- Connects to existing droplet API at `social.sterlingcooley.com`
- Polls for new posts in the `gui_post_queue`
- Sends completion/failure status back to API
- Handles authentication (API key or token)

### Post Queue Management
- Loads posts like "bullets in a magazine"
- Displays one post at a time
- Advances to next post on completion/skip
- Shows queue count and position

---

## Features

### 1. Post Display
- **Platform indicator** - Which platform this post is for (Facebook, Instagram, TikTok, Skool)
- **Image preview** - Thumbnail of media to be posted
- **Title/Headline** - If applicable
- **Caption/Body** - Full post text (scrollable if long)
- **Scheduled time** - When it should be posted
- **Character count** - For platforms with limits

### 2. Action Buttons

| Button | Action | Keyboard Shortcut |
|--------|--------|-------------------|
| Copy Title | Copy title to clipboard | `Ctrl+1` |
| Copy Caption | Copy caption/body to clipboard | `Ctrl+2` |
| Copy Image | Copy image to clipboard OR save to temp location | `Ctrl+3` |
| Copy All | Copy all text fields | `Ctrl+A` |
| Mark Complete | Tell API this post was successfully made | `Ctrl+Enter` |
| Mark Failed | Tell API this post failed (with optional reason) | `Ctrl+F` |
| Skip / Next | Move to next post without marking | `Ctrl+→` |
| Previous | Go back to previous post | `Ctrl+←` |
| Refresh | Re-fetch queue from API | `F5` |

### 3. Status Indicators
- **Connection status** - Green/Red dot showing API connectivity
- **Queue count** - "Post 2 of 5"
- **Last sync time** - "Updated 30s ago"
- **Current platform** - Icon + name

### 4. Optional Color Coding
- Color-coded borders/backgrounds per platform:
  - Facebook: Blue (#1877F2)
  - Instagram: Gradient/Purple (#E4405F)
  - TikTok: Black/Cyan (#00F2EA)
  - Skool: Green
- Helps vision model identify context quickly

---

## Technical Implementation

### Dependencies

```
requirements.txt
-----------------
PyQt6>=6.5.0           # GUI framework (or tkinter if preferred)
requests>=2.31.0       # API calls
Pillow>=10.0.0         # Image handling
pyperclip>=1.8.2       # Clipboard operations
pyyaml>=6.0.0          # Configuration
keyboard>=0.13.5       # Global hotkeys (optional)
```

### Project Structure

```
onscreen-prompter/
├── main.py                    # Entry point
├── requirements.txt
├── config.yaml                # API endpoint, credentials, settings
├── src/
│   ├── __init__.py
│   ├── app.py                 # Main application class
│   ├── api_client.py          # API communication
│   ├── post_queue.py          # Queue management logic
│   ├── clipboard_manager.py   # Clipboard operations
│   └── ui/
│       ├── __init__.py
│       ├── main_window.py     # Prompter window
│       ├── post_card.py       # Single post display widget
│       ├── action_buttons.py  # Button panel
│       └── status_bar.py      # Connection/queue status
└── assets/
    └── icons/                 # Platform icons
```

---

## Core Components

### config.yaml

```yaml
# On-Screen Prompter Configuration

api:
  base_url: "https://social.sterlingcooley.com/api"
  # Authentication - agent will fill in actual values
  api_key: "${API_KEY}"  # Or loaded from environment
  
  endpoints:
    queue: "/gui-post-queue"
    complete: "/gui-post-queue/{id}/complete"
    failed: "/gui-post-queue/{id}/failed"
    
  poll_interval_seconds: 30

window:
  width_percent: 15          # 15% of screen width
  position: "right"          # Dock to right edge
  always_on_top: true
  opacity: 1.0               # 0.0-1.0 for transparency
  
display:
  show_image_preview: true
  max_caption_lines: 10      # Before scrolling
  
platforms:
  facebook:
    color: "#1877F2"
    char_limit: 63206
  instagram:
    color: "#E4405F"
    char_limit: 2200
  tiktok:
    color: "#00F2EA"
    char_limit: 4000
  skool:
    color: "#22C55E"
    char_limit: null

hotkeys:
  copy_title: "ctrl+1"
  copy_caption: "ctrl+2"
  copy_image: "ctrl+3"
  mark_complete: "ctrl+return"
  mark_failed: "ctrl+f"
  next_post: "ctrl+right"
  prev_post: "ctrl+left"
  refresh: "f5"
```

### api_client.py

```python
"""
API Client for Social Dashboard
Handles all communication with social.sterlingcooley.com
"""
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Platform(Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    SKOOL = "skool"


@dataclass
class QueuedPost:
    """Represents a post in the queue."""
    id: str
    platform: Platform
    title: Optional[str]
    caption: str
    image_url: Optional[str]
    scheduled_at: Optional[str]
    status: str
    metadata: Dict[str, Any]
    
    @classmethod
    def from_api_response(cls, data: dict) -> 'QueuedPost':
        """Create from API JSON response."""
        return cls(
            id=data['id'],
            platform=Platform(data['platform'].lower()),
            title=data.get('title'),
            caption=data.get('caption', data.get('body', '')),
            image_url=data.get('image_url', data.get('media_url')),
            scheduled_at=data.get('scheduled_at'),
            status=data.get('status', 'pending'),
            metadata=data.get('metadata', {})
        )


class APIClient:
    """Client for Social Dashboard API."""
    
    def __init__(self, base_url: str, api_key: str):
        """
        Initialize API client.
        
        Args:
            base_url: API base URL (e.g., https://social.sterlingcooley.com/api)
            api_key: Authentication key
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make API request with error handling."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise
    
    def get_queue(self) -> List[QueuedPost]:
        """
        Fetch all pending posts from the queue.
        
        Returns:
            List of QueuedPost objects
        """
        data = self._request('GET', '/gui-post-queue')
        posts = data.get('posts', data.get('data', []))
        return [QueuedPost.from_api_response(p) for p in posts]
    
    def mark_complete(self, post_id: str) -> bool:
        """
        Mark a post as successfully completed.
        
        Args:
            post_id: The post ID to mark complete
            
        Returns:
            True if successful
        """
        try:
            self._request('POST', f'/gui-post-queue/{post_id}/complete')
            return True
        except Exception as e:
            logger.error(f"Failed to mark complete: {e}")
            return False
    
    def mark_failed(self, post_id: str, reason: str = "") -> bool:
        """
        Mark a post as failed.
        
        Args:
            post_id: The post ID to mark failed
            reason: Optional failure reason
            
        Returns:
            True if successful
        """
        try:
            self._request(
                'POST', 
                f'/gui-post-queue/{post_id}/failed',
                json={'reason': reason}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to mark failed: {e}")
            return False
    
    def download_image(self, url: str) -> bytes:
        """
        Download image from URL.
        
        Args:
            url: Image URL
            
        Returns:
            Image bytes
        """
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        return response.content
    
    def health_check(self) -> bool:
        """Check if API is reachable."""
        try:
            self._request('GET', '/health')
            return True
        except Exception:
            return False
```

### post_queue.py

```python
"""
Post Queue Manager
Handles the "magazine" of posts to process
"""
from typing import List, Optional
from dataclasses import dataclass
import logging

from .api_client import APIClient, QueuedPost

logger = logging.getLogger(__name__)


class PostQueue:
    """Manages the queue of posts like bullets in a magazine."""
    
    def __init__(self, api_client: APIClient):
        """
        Initialize queue manager.
        
        Args:
            api_client: API client instance
        """
        self.api = api_client
        self.posts: List[QueuedPost] = []
        self.current_index: int = 0
    
    def refresh(self) -> int:
        """
        Fetch fresh queue from API.
        
        Returns:
            Number of posts in queue
        """
        try:
            self.posts = self.api.get_queue()
            # Reset index if it's out of bounds
            if self.current_index >= len(self.posts):
                self.current_index = max(0, len(self.posts) - 1)
            logger.info(f"Refreshed queue: {len(self.posts)} posts")
            return len(self.posts)
        except Exception as e:
            logger.error(f"Failed to refresh queue: {e}")
            return len(self.posts)
    
    @property
    def current_post(self) -> Optional[QueuedPost]:
        """Get the currently displayed post."""
        if not self.posts or self.current_index >= len(self.posts):
            return None
        return self.posts[self.current_index]
    
    @property
    def count(self) -> int:
        """Total posts in queue."""
        return len(self.posts)
    
    @property
    def position(self) -> int:
        """Current position (1-indexed for display)."""
        return self.current_index + 1
    
    def next(self) -> Optional[QueuedPost]:
        """
        Advance to next post.
        
        Returns:
            Next post or None if at end
        """
        if self.current_index < len(self.posts) - 1:
            self.current_index += 1
            return self.current_post
        return None
    
    def previous(self) -> Optional[QueuedPost]:
        """
        Go back to previous post.
        
        Returns:
            Previous post or None if at start
        """
        if self.current_index > 0:
            self.current_index -= 1
            return self.current_post
        return None
    
    def complete_current(self) -> bool:
        """
        Mark current post as complete and advance.
        
        Returns:
            True if successful
        """
        post = self.current_post
        if not post:
            return False
        
        success = self.api.mark_complete(post.id)
        if success:
            # Remove from local queue and stay at same index
            # (which now points to next post)
            self.posts.pop(self.current_index)
            if self.current_index >= len(self.posts):
                self.current_index = max(0, len(self.posts) - 1)
        
        return success
    
    def fail_current(self, reason: str = "") -> bool:
        """
        Mark current post as failed and advance.
        
        Args:
            reason: Failure reason
            
        Returns:
            True if successful
        """
        post = self.current_post
        if not post:
            return False
        
        success = self.api.mark_failed(post.id, reason)
        if success:
            self.posts.pop(self.current_index)
            if self.current_index >= len(self.posts):
                self.current_index = max(0, len(self.posts) - 1)
        
        return success
    
    def skip_current(self) -> Optional[QueuedPost]:
        """
        Skip current post without marking (just advance).
        
        Returns:
            Next post
        """
        return self.next()
```

### main_window.py (UI)

```python
"""
Main Prompter Window
Docked sidebar displaying the current post and action buttons
"""
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QFrame, QTextEdit,
    QMessageBox, QInputDialog
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QPixmap, QImage, QFont, QShortcut, QKeySequence, QScreen
import pyperclip
from io import BytesIO
from PIL import Image

from ..api_client import APIClient, Platform
from ..post_queue import PostQueue


# Platform colors
PLATFORM_COLORS = {
    Platform.FACEBOOK: "#1877F2",
    Platform.INSTAGRAM: "#E4405F",
    Platform.TIKTOK: "#00F2EA",
    Platform.SKOOL: "#22C55E",
}


class PrompterWindow(QMainWindow):
    """Main on-screen prompter window."""
    
    def __init__(self, api_client: APIClient, config: dict):
        super().__init__()
        
        self.api = api_client
        self.config = config
        self.queue = PostQueue(api_client)
        
        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        self._setup_polling()
        
        # Initial load
        self.refresh_queue()
    
    def _setup_window(self):
        """Configure window properties."""
        # Get screen dimensions
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # Calculate window size (15% of screen width)
        width_percent = self.config.get('window', {}).get('width_percent', 15)
        window_width = int(screen_width * width_percent / 100)
        
        # Position on right edge
        x_pos = screen_width - window_width
        
        self.setGeometry(x_pos, 0, window_width, screen_height)
        self.setWindowTitle("Post Queue")
        
        # Window flags
        flags = Qt.WindowType.Window
        
        if self.config.get('window', {}).get('always_on_top', True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        
        # Frameless for cleaner look (optional)
        # flags |= Qt.WindowType.FramelessWindowHint
        
        self.setWindowFlags(flags)
        
        # Prevent resizing
        self.setFixedWidth(window_width)
    
    def _setup_ui(self):
        """Build the UI components."""
        central = QWidget()
        self.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # --- Header / Status ---
        header = QFrame()
        header.setStyleSheet("background: #1a1a2e; border-radius: 8px; padding: 8px;")
        header_layout = QVBoxLayout(header)
        
        # Connection status
        self.status_label = QLabel("● Connecting...")
        self.status_label.setStyleSheet("color: #ffa500; font-size: 12px;")
        header_layout.addWidget(self.status_label)
        
        # Platform indicator
        self.platform_label = QLabel("Platform: --")
        self.platform_label.setStyleSheet("color: white; font-size: 14px; font-weight: bold;")
        header_layout.addWidget(self.platform_label)
        
        # Queue position
        self.queue_label = QLabel("Queue: 0 / 0")
        self.queue_label.setStyleSheet("color: #888; font-size: 12px;")
        header_layout.addWidget(self.queue_label)
        
        layout.addWidget(header)
        
        # --- Post Content ---
        content_frame = QFrame()
        content_frame.setStyleSheet("background: #16213e; border-radius: 8px;")
        self.content_layout = QVBoxLayout(content_frame)
        
        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumHeight(150)
        self.image_label.setStyleSheet("background: #0f0f23; border-radius: 4px;")
        self.content_layout.addWidget(self.image_label)
        
        # Title
        self.title_label = QLabel("Title")
        self.title_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 8px;")
        self.content_layout.addWidget(self.title_label)
        
        self.title_text = QLabel("--")
        self.title_text.setStyleSheet("color: white; font-size: 13px; font-weight: bold;")
        self.title_text.setWordWrap(True)
        self.content_layout.addWidget(self.title_text)
        
        # Caption
        self.caption_label = QLabel("Caption")
        self.caption_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 8px;")
        self.content_layout.addWidget(self.caption_label)
        
        # Scrollable caption area
        self.caption_scroll = QScrollArea()
        self.caption_scroll.setWidgetResizable(True)
        self.caption_scroll.setMaximumHeight(200)
        self.caption_scroll.setStyleSheet("border: none;")
        
        self.caption_text = QLabel("--")
        self.caption_text.setStyleSheet("color: white; font-size: 12px;")
        self.caption_text.setWordWrap(True)
        self.caption_text.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.caption_scroll.setWidget(self.caption_text)
        
        self.content_layout.addWidget(self.caption_scroll)
        
        # Character count
        self.char_count = QLabel("0 chars")
        self.char_count.setStyleSheet("color: #666; font-size: 10px;")
        self.content_layout.addWidget(self.char_count)
        
        layout.addWidget(content_frame, 1)
        
        # --- Copy Buttons ---
        copy_frame = QFrame()
        copy_layout = QVBoxLayout(copy_frame)
        copy_layout.setSpacing(4)
        
        self.copy_title_btn = self._create_button("📋 Copy Title", "#3b82f6")
        self.copy_title_btn.clicked.connect(self.copy_title)
        copy_layout.addWidget(self.copy_title_btn)
        
        self.copy_caption_btn = self._create_button("📋 Copy Caption", "#3b82f6")
        self.copy_caption_btn.clicked.connect(self.copy_caption)
        copy_layout.addWidget(self.copy_caption_btn)
        
        self.copy_image_btn = self._create_button("🖼️ Copy Image", "#3b82f6")
        self.copy_image_btn.clicked.connect(self.copy_image)
        copy_layout.addWidget(self.copy_image_btn)
        
        layout.addWidget(copy_frame)
        
        # --- Action Buttons ---
        action_frame = QFrame()
        action_layout = QVBoxLayout(action_frame)
        action_layout.setSpacing(4)
        
        self.complete_btn = self._create_button("✓ Mark Complete", "#22c55e")
        self.complete_btn.clicked.connect(self.mark_complete)
        action_layout.addWidget(self.complete_btn)
        
        self.failed_btn = self._create_button("✗ Mark Failed", "#ef4444")
        self.failed_btn.clicked.connect(self.mark_failed)
        action_layout.addWidget(self.failed_btn)
        
        # Navigation row
        nav_layout = QHBoxLayout()
        
        self.prev_btn = self._create_button("←", "#6b7280", small=True)
        self.prev_btn.clicked.connect(self.go_previous)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = self._create_button("Skip →", "#6b7280")
        self.next_btn.clicked.connect(self.go_next)
        nav_layout.addWidget(self.next_btn)
        
        action_layout.addLayout(nav_layout)
        
        layout.addWidget(action_frame)
        
        # --- Footer ---
        footer_layout = QHBoxLayout()
        
        self.refresh_btn = self._create_button("🔄", "#4b5563", small=True)
        self.refresh_btn.clicked.connect(self.refresh_queue)
        footer_layout.addWidget(self.refresh_btn)
        
        self.last_sync = QLabel("Never synced")
        self.last_sync.setStyleSheet("color: #666; font-size: 10px;")
        footer_layout.addWidget(self.last_sync, 1)
        
        layout.addLayout(footer_layout)
        
        # Set dark theme for whole window
        self.setStyleSheet("""
            QMainWindow {
                background: #0f0f23;
            }
        """)
    
    def _create_button(self, text: str, color: str, small: bool = False) -> QPushButton:
        """Create a styled button."""
        btn = QPushButton(text)
        height = 32 if small else 40
        btn.setFixedHeight(height)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {color}dd;
            }}
            QPushButton:pressed {{
                background: {color}bb;
            }}
        """)
        return btn
    
    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        shortcuts = [
            ("Ctrl+1", self.copy_title),
            ("Ctrl+2", self.copy_caption),
            ("Ctrl+3", self.copy_image),
            ("Ctrl+Return", self.mark_complete),
            ("Ctrl+F", self.mark_failed),
            ("Ctrl+Right", self.go_next),
            ("Ctrl+Left", self.go_previous),
            ("F5", self.refresh_queue),
        ]
        
        for key, callback in shortcuts:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(callback)
    
    def _setup_polling(self):
        """Set up automatic queue polling."""
        interval = self.config.get('api', {}).get('poll_interval_seconds', 30) * 1000
        
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.refresh_queue)
        self.poll_timer.start(interval)
    
    def refresh_queue(self):
        """Fetch fresh queue from API."""
        try:
            count = self.queue.refresh()
            self.status_label.setText("● Connected")
            self.status_label.setStyleSheet("color: #22c55e; font-size: 12px;")
            self.update_display()
            
            from datetime import datetime
            self.last_sync.setText(f"Synced {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            self.status_label.setText("● Disconnected")
            self.status_label.setStyleSheet("color: #ef4444; font-size: 12px;")
    
    def update_display(self):
        """Update UI with current post."""
        post = self.queue.current_post
        
        # Update queue label
        self.queue_label.setText(f"Queue: {self.queue.position} / {self.queue.count}")
        
        if not post:
            self.platform_label.setText("Platform: --")
            self.title_text.setText("No posts in queue")
            self.caption_text.setText("--")
            self.image_label.clear()
            self.char_count.setText("0 chars")
            return
        
        # Platform
        platform_color = PLATFORM_COLORS.get(post.platform, "#888")
        self.platform_label.setText(f"Platform: {post.platform.value.title()}")
        self.platform_label.setStyleSheet(f"color: {platform_color}; font-size: 14px; font-weight: bold;")
        
        # Title
        self.title_text.setText(post.title or "(No title)")
        
        # Caption
        self.caption_text.setText(post.caption or "(No caption)")
        self.char_count.setText(f"{len(post.caption or '')} chars")
        
        # Image
        if post.image_url:
            self._load_image(post.image_url)
        else:
            self.image_label.setText("No image")
            self.image_label.setStyleSheet("color: #666; background: #0f0f23; border-radius: 4px;")
    
    def _load_image(self, url: str):
        """Load and display image from URL."""
        try:
            image_data = self.api.download_image(url)
            
            # Convert to QPixmap
            img = Image.open(BytesIO(image_data))
            img = img.convert('RGB')
            
            # Resize to fit
            max_width = self.width() - 32
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, min(new_height, 200)), Image.Resampling.LANCZOS)
            
            # Convert to QPixmap
            qimg = QImage(img.tobytes(), img.width, img.height, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            
            self.image_label.setPixmap(pixmap)
            self.image_label.setStyleSheet("background: #0f0f23; border-radius: 4px;")
            
        except Exception as e:
            self.image_label.setText(f"Failed to load image")
            self.image_label.setStyleSheet("color: #ef4444; background: #0f0f23; border-radius: 4px;")
    
    # --- Actions ---
    
    def copy_title(self):
        """Copy title to clipboard."""
        post = self.queue.current_post
        if post and post.title:
            pyperclip.copy(post.title)
            self._flash_button(self.copy_title_btn)
    
    def copy_caption(self):
        """Copy caption to clipboard."""
        post = self.queue.current_post
        if post and post.caption:
            pyperclip.copy(post.caption)
            self._flash_button(self.copy_caption_btn)
    
    def copy_image(self):
        """Copy image to clipboard or save to temp file."""
        post = self.queue.current_post
        if not post or not post.image_url:
            return
        
        try:
            image_data = self.api.download_image(post.image_url)
            
            # Save to temp file (easier for pasting into apps)
            import tempfile
            import os
            
            temp_path = os.path.join(tempfile.gettempdir(), "prompter_image.png")
            
            img = Image.open(BytesIO(image_data))
            img.save(temp_path, "PNG")
            
            # Copy file path to clipboard
            pyperclip.copy(temp_path)
            self._flash_button(self.copy_image_btn)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to copy image: {e}")
    
    def mark_complete(self):
        """Mark current post as complete."""
        if self.queue.complete_current():
            self.update_display()
    
    def mark_failed(self):
        """Mark current post as failed."""
        reason, ok = QInputDialog.getText(
            self, "Failure Reason", "Why did this post fail? (optional)"
        )
        
        if ok:  # User clicked OK (even if empty)
            if self.queue.fail_current(reason):
                self.update_display()
    
    def go_next(self):
        """Skip to next post."""
        self.queue.next()
        self.update_display()
    
    def go_previous(self):
        """Go to previous post."""
        self.queue.previous()
        self.update_display()
    
    def _flash_button(self, button: QPushButton):
        """Visual feedback for button press."""
        original = button.styleSheet()
        button.setStyleSheet(original.replace("background:", "background: #22c55e; /* "))
        QTimer.singleShot(200, lambda: button.setStyleSheet(original))
```

### main.py (Entry Point)

```python
"""
On-Screen Prompter - Entry Point
Social Media Post Queue GUI for Windows 10
"""
import sys
import os
import yaml
import logging
from PyQt6.QtWidgets import QApplication

from src.api_client import APIClient
from src.ui.main_window import PrompterWindow


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('prompter.log'),
            logging.StreamHandler()
        ]
    )


def load_config() -> dict:
    """Load configuration from yaml file."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    
    if os.path.exists(config_path):
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    # Default config
    return {
        'api': {
            'base_url': 'https://social.sterlingcooley.com/api',
            'api_key': os.environ.get('SOCIAL_API_KEY', ''),
            'poll_interval_seconds': 30
        },
        'window': {
            'width_percent': 15,
            'always_on_top': True
        }
    }


def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger('prompter')
    
    # Load config
    config = load_config()
    
    # Get API key from config or environment
    api_key = config['api'].get('api_key') or os.environ.get('SOCIAL_API_KEY')
    
    if not api_key:
        logger.error("No API key configured. Set SOCIAL_API_KEY environment variable or add to config.yaml")
        sys.exit(1)
    
    # Initialize API client
    api_client = APIClient(
        base_url=config['api']['base_url'],
        api_key=api_key
    )
    
    # Start Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("On-Screen Prompter")
    
    # Create and show window
    window = PrompterWindow(api_client, config)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

---

## Installation & Running

```powershell
# Create project directory
mkdir C:\onscreen-prompter
cd C:\onscreen-prompter

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Set API key (or add to config.yaml)
$env:SOCIAL_API_KEY = "your-api-key-here"

# Run
python main.py
```

---

## API Contract

The prompter expects these API endpoints:

### GET /gui-post-queue
Returns pending posts:
```json
{
  "posts": [
    {
      "id": "post_123",
      "platform": "instagram",
      "title": "New Product Launch",
      "caption": "Check out our latest...",
      "image_url": "https://...",
      "scheduled_at": "2024-01-15T10:00:00Z",
      "status": "pending"
    }
  ]
}
```

### POST /gui-post-queue/{id}/complete
Marks post as successfully posted.

### POST /gui-post-queue/{id}/failed
Marks post as failed:
```json
{
  "reason": "Instagram login expired"
}
```

---

## Usage

1. **Launch** - Window appears docked to right edge of screen
2. **View post** - Current post displays with image, title, caption
3. **Copy content** - Click Copy buttons or use `Ctrl+1/2/3`
4. **Mark complete** - After posting, click "Mark Complete" (`Ctrl+Enter`)
5. **Mark failed** - If posting fails, click "Mark Failed" (`Ctrl+F`)
6. **Navigate** - Use Skip/Previous buttons or `Ctrl+Arrow` keys
7. **Refresh** - Press `F5` to manually refresh queue

---

## Integration with Ubuntu Poster

The Ubuntu poster agent can:
1. Read the prompter window via VNC screen capture
2. Use Qwen2.5-VL to understand the current post content
3. Click the Copy buttons using QMP input injection
4. Perform the posting action on the target platform
5. Click Mark Complete when done

The color-coded platform indicators help the vision model quickly identify which platform workflow to execute.