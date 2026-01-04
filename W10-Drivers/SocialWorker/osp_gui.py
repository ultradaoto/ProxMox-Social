"""
One-Click Social Poster (OSP) GUI
Windows 10 Desktop Application

Reads queued posts from C:/PostQueue/pending (fetched by fetcher.py)
and displays them in a side-docked window for manual posting.

Auto-docks to right 15% of screen and resizes Chrome to left 85%.
"""
import sys
import os
import json
import time
import shutil
import logging
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import threading

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence, QIcon, QAction, QDesktopServices
import pyperclip
from PIL import Image

try:
    import pygetwindow as gw
except ImportError:
    gw = None

# =============================================================================
# CONFIGURATION
# =============================================================================

QUEUE_DIR = Path(os.getenv('QUEUE_DIR', 'C:/PostQueue'))
PENDING_DIR = QUEUE_DIR / 'pending'
COMPLETED_DIR = QUEUE_DIR / 'completed'
FAILED_DIR = QUEUE_DIR / 'failed'

# Ensure directories exist
for d in [PENDING_DIR, COMPLETED_DIR, FAILED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Platform colors
class Platform(Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    SKOOL = "skool"
    UNKNOWN = "unknown"

PLATFORM_COLORS = {
    Platform.FACEBOOK: "#1877F2",
    Platform.INSTAGRAM: "#E4405F",
    Platform.TIKTOK: "#00F2EA",
    Platform.SKOOL: "#22C55E",
    Platform.UNKNOWN: "#888888",
}

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('OSP_GUI')


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class LocalJob:
    """Represents a locally stored job."""
    job_id: str
    path: Path
    data: Dict[str, Any]
    
    @property
    def title(self) -> str:
        # 1. Try explicit title
        t = self.data.get('title')
        if t: return t
        
        # 2. Try first line of caption
        caption = self.caption
        if caption:
            first_line = caption.split('\n')[0].strip()
            # If first line is short-ish, use it as title
            if len(first_line) < 100:
                return first_line
        
        return ""
        
    @property
    def caption(self) -> str:
        return self.data.get('caption') or self.data.get('body') or ""
        
    @property
    def platform(self) -> Platform:
        raw = self.data.get('platform', 'unknown').lower()
        
        # Fuzzy matching
        if 'facebook' in raw: return Platform.FACEBOOK
        if 'instagram' in raw: return Platform.INSTAGRAM
        if 'tiktok' in raw: return Platform.TIKTOK
        if 'skool' in raw: return Platform.SKOOL
        
        try:
            return Platform(raw)
        except ValueError:
            return Platform.UNKNOWN

    @property
    def image_path(self) -> Optional[str]:
        media = self.data.get('media', [])
        if not media:
            return None
        # Return first media file path
        local_name = media[0].get('local_path')
        if local_name:
            return str(self.path / local_name)
        return None

    @property
    def link(self) -> Optional[str]:
        # 1. Try explicit link fields in order of preference
        # 'platform_url' seems to be the specific target for Skool/etc
        if self.data.get('platform_url'):
            return self.data.get('platform_url')
            
        # Check distinct 'options' dictionary if present
        options = self.data.get('options', {})
        if isinstance(options, dict) and options.get('target_url'):
            return options.get('target_url')
            
        # Standard link field
        if self.data.get('link'):
            return self.data.get('link')
        
        # User requested NO fallback to caption scanning.
        # If no explicit link is provided in the JSON, return None.
        return None


class JobQueue:
    """Manages local job folders."""
    
    def __init__(self):
        self.jobs: List[LocalJob] = []
        self.current_index: int = 0
        
    def refresh(self) -> int:
        """Scan pending directory for jobs."""
        new_jobs = []
        try:
            # Find all job_* directories
            if PENDING_DIR.exists():
                dirs = sorted([d for d in PENDING_DIR.iterdir() if d.is_dir() and d.name.startswith('job_')])
                for d in dirs:
                    json_path = d / 'job.json'
                    if json_path.exists():
                        try:
                            with open(json_path, 'r', encoding='utf-8') as f:
                                data = json.load(f)
                            new_jobs.append(LocalJob(d.name, d, data))
                        except Exception as e:
                            logger.error(f"Error reading job {d.name}: {e}")
            
            self.jobs = new_jobs
            # Keep index in bounds
            if self.current_index >= len(self.jobs):
                self.current_index = max(0, len(self.jobs) - 1)
                
            return len(self.jobs)
        except Exception as e:
            logger.error(f"Failed to refresh queue: {e}")
            return 0

    @property
    def current_job(self) -> Optional[LocalJob]:
        if not self.jobs or self.current_index >= len(self.jobs):
            return None
        return self.jobs[self.current_index]

    def next(self):
        if self.current_index < len(self.jobs) - 1:
            self.current_index += 1

    def prev(self):
        if self.current_index > 0:
            self.current_index -= 1

    def complete_current(self) -> bool:
        job = self.current_job
        if not job:
            return False
            
        try:
            # Move folder to completed
            dest = COMPLETED_DIR / job.job_id
            if dest.exists():
                shutil.rmtree(dest) # Overwrite if exists
            shutil.move(str(job.path), str(dest))
            
            # Update local list
            self.jobs.pop(self.current_index)
            if self.current_index >= len(self.jobs):
                self.current_index = max(0, len(self.jobs) - 1)
            return True
        except Exception as e:
            logger.error(f"Failed to complete job {job.job_id}: {e}")
            return False

    def fail_current(self, reason: str = "") -> bool:
        job = self.current_job
        if not job:
            return False
            
        try:
            # Move folder to failed
            dest = FAILED_DIR / job.job_id
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(job.path), str(dest))
            
            # Add failure reason file
            with open(dest / 'failure_reason.txt', 'w') as f:
                f.write(reason)
                
            self.jobs.pop(self.current_index)
            if self.current_index >= len(self.jobs):
                self.current_index = max(0, len(self.jobs) - 1)
            return True
        except Exception as e:
            logger.error(f"Failed to fail job {job.job_id}: {e}")
            return False


# =============================================================================
# GUI
# =============================================================================

class PrompterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.queue = JobQueue()
        self.queue.refresh()
        
        self.target_width = 300 # Initial fallback
        
        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        
        # Polling for new files
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.refresh_queue)
        self.poll_timer.start(5000) # Check every 5 seconds
        
        # Window management timer (keep on top/right)
        self.dock_timer = QTimer()
        self.dock_timer.timeout.connect(self.enforce_docking)
        self.dock_timer.start(2000)
        
        self.update_display()
        
        # Initial dock enforcement
        QTimer.singleShot(100, self.enforce_docking)

    def _setup_window(self):
        self.setWindowTitle("OSP Queue")
        
        # Always on top, Tool window style
        self.setWindowFlags(
            Qt.WindowType.Window | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        self.enforce_docking()

    def enforce_docking(self):
        """Force window to right 15% and Chrome to left 85%."""
        screen = QApplication.primaryScreen().availableGeometry()
        width = screen.width()
        height = screen.height()
        x_offset = screen.x()
        y_offset = screen.y()
        
        osp_width = int(width * 0.15)
        self.target_width = osp_width
        chrome_width = width - osp_width
        
        # 1. Position OSP (Self)
        self.setGeometry(x_offset + width - osp_width, y_offset, osp_width, height)
        # Force max width to prevent bloom
        self.setMaximumWidth(osp_width)
        
        # 2. Position Chrome
        if gw:
            try:
                # Find windows with "Chrome" or "Google Chrome" in title
                chrome_windows = [w for w in gw.getAllWindows() if 'Chrome' in w.title or 'Google Chrome' in w.title]
                for w in chrome_windows:
                    if w.visible:
                        # Only resize if it's not already correct (avoid fighting use too much)
                        if abs(w.width - chrome_width) > 50 or abs(w.left - x_offset) > 50:
                            w.restore() # Ensure not maximized
                            w.resizeTo(chrome_width, height)
                            w.moveTo(x_offset, y_offset)
            except Exception as e:
                logger.debug(f"Chrome resizing failed: {e}")

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # --- HEADER ---
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #252525; border-radius: 6px;")
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 8, 8, 8)
        
        self.header_label = QLabel("OSP: Ready")
        self.header_label.setStyleSheet("font-weight: bold; color: white; font-size: 14px;")
        self.header_label.setWordWrap(True)
        header_layout.addWidget(self.header_label)
        
        # Open Link Button
        self.btn_open_link = QPushButton("↗ Open Post URL")
        self.btn_open_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_open_link.clicked.connect(self.open_link)
        self.btn_open_link.setStyleSheet("""
            QPushButton {
                background-color: #444; color: white; border: none; 
                border-radius: 4px; padding: 4px; font-size: 11px;
            }
            QPushButton:hover { background-color: #666; }
        """)
        header_layout.addWidget(self.btn_open_link)
        
        # Count
        self.count_label = QLabel("Queue: 0")
        self.count_label.setStyleSheet("color: #aaa; font-size: 11px;")
        header_layout.addWidget(self.count_label)
        
        layout.addWidget(header_frame)
        
        # --- CONTENT ---
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("background: #2d2d2d; border-radius: 5px;")
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setSpacing(5)
        
        # Image Preview
        self.image_label = QLabel()
        self.image_label.setMinimumHeight(120)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #000; border-radius: 3px;")
        content_layout.addWidget(self.image_label)
        
        # Title
        self.title_label = QLabel("No Job Selected")
        self.title_label.setWordWrap(True)
        # Limit title width logic (handled by WordWrap, but ensure layout respects it)
        self.title_label.setStyleSheet("font-weight: bold; color: white; margin-top: 5px;")
        content_layout.addWidget(self.title_label)
        
        # Caption
        self.caption_area = QScrollArea()
        self.caption_text = QLabel()
        self.caption_text.setWordWrap(True)
        self.caption_text.setStyleSheet("color: #ddd;")
        self.caption_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Selectable text
        self.caption_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.caption_area.setWidget(self.caption_text)
        self.caption_area.setWidgetResizable(True)
        content_layout.addWidget(self.caption_area)
        
        layout.addWidget(self.content_frame)
        
        # --- ACTION BUTTONS ---
        
        # Copy Buttons
        self.btn_copy_title = self._make_btn("Copy Title (Ctrl+1)", self.copy_title, "#3b82f6")
        layout.addWidget(self.btn_copy_title)
        
        self.btn_copy_caption = self._make_btn("Copy Caption (Ctrl+2)", self.copy_caption, "#3b82f6")
        layout.addWidget(self.btn_copy_caption)
        
        # Two Image Buttons Row
        img_btns_layout = QHBoxLayout()
        self.btn_copy_img_path = self._make_btn("Copy Path", self.copy_image_path, "#3b82f6")
        self.btn_copy_img_data = self._make_btn("Copy Image", self.copy_image_data, "#8b5cf6") # Purple
        img_btns_layout.addWidget(self.btn_copy_img_path)
        img_btns_layout.addWidget(self.btn_copy_img_data)
        layout.addLayout(img_btns_layout)
        
        # Done/Fail Row
        action_layout = QHBoxLayout()
        self.btn_fail = self._make_btn("✗ Fail", self.mark_failed, "#ef4444")
        self.btn_done = self._make_btn("✓ Done", self.mark_complete, "#22c55e")
        action_layout.addWidget(self.btn_fail)
        action_layout.addWidget(self.btn_done)
        layout.addLayout(action_layout)
        
        # Navigation Row
        nav_layout = QHBoxLayout()
        self.btn_prev = self._make_btn("←", self.prev_job, "#6b7280")
        self.btn_next = self._make_btn("Skip →", self.next_job, "#6b7280")
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        layout.addLayout(nav_layout)

        # Style
        self.setStyleSheet("""
            QMainWindow { background: #1a1a1a; }
            QLabel { font-family: Segoe UI, sans-serif; }
        """)

    def _make_btn(self, text, func, color):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setFixedHeight(35)
        # Use simple color values to avoid parsing issues, add hover
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
            }}
            QPushButton:hover {{ background-color: white; color: {color}; }}
        """)
        return btn

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(self.copy_title)
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(self.copy_caption)
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(self.copy_image_path)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.mark_complete)
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(self.next_job)
        QShortcut(QKeySequence("Ctrl+Left"), self).activated.connect(self.prev_job)

    def refresh_queue(self):
        count = self.queue.refresh()
        self.count_label.setText(f"Queue: {self.queue.current_index + 1}/{count}" if count > 0 else "Queue: 0")
        if count > 0 and self.title_label.text() == "No Job Selected":
            self.update_display()
        
        # If queue was just emptied
        if count == 0:
            self.update_display()

    def update_display(self):
        job = self.queue.current_job
        
        if not job:
            self.header_label.setText("OSP: Idle")
            self.header_label.setStyleSheet("color: white; font-weight: bold;")
            self.btn_open_link.setVisible(False)
            self.title_label.setText("No Job Selected")
            self.caption_text.setText("")
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No Media")
            return
            
        # Update Platform Header
        color = PLATFORM_COLORS.get(job.platform, "#888888")
        self.header_label.setText(f"Platform: {job.platform.value.upper()}")
        self.header_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 16px;")
        
        # Update Link Button
        if job.link:
            self.btn_open_link.setVisible(True)
            self.btn_open_link.setText(f"↗ Open {job.platform.value.title()} Link")
            self.btn_open_link.setToolTip(job.link)
        else:
            self.btn_open_link.setVisible(False)
        
        self.title_label.setText(job.title or "(No Title)")
        self.caption_text.setText(job.caption)
        self.caption_text.adjustSize()
        
        # Load Image
        img_path = job.image_path
        if img_path and os.path.exists(img_path):
            try:
                # Resize for preview
                # Constrain to available width minus padding (approx 40px)
                max_w = max(100, self.target_width - 40)
                
                pixmap = QPixmap(img_path)
                scaled = pixmap.scaled(
                    max_w, 
                    300, # Max height for visual sanity
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
                self.image_label.setText("")
            except Exception:
                self.image_label.setText("Image Error")
        else:
            self.image_label.setText("No Image")

    # Actions
    def copy_title(self):
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.title)
            self._flash_btn(self.btn_copy_title)

    def copy_caption(self):
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.caption)
            self._flash_btn(self.btn_copy_caption)

    def copy_image_path(self):
        job = self.queue.current_job
        if job and job.image_path:
            # Copy file path to clipboard (useful for file upload dialogs)
            pyperclip.copy(str(Path(job.image_path).absolute()))
            self._flash_btn(self.btn_copy_img_path)

    def copy_image_data(self):
        """Copy actual image bitmap to clipboard."""
        job = self.queue.current_job
        if job and job.image_path:
            try:
                img = QImage(job.image_path)
                QApplication.clipboard().setImage(img)
                self._flash_btn(self.btn_copy_img_data)
            except Exception as e:
                logger.error(f"Failed to copy image data: {e}")

    def open_link(self):
        job = self.queue.current_job
        if job and job.link:
            QDesktopServices.openUrl(QUrl(job.link))

    def mark_complete(self):
        if self.queue.complete_current():
            self.refresh_queue()
            self.update_display()

    def mark_failed(self):
        if self.queue.fail_current("Marked failed by user"):
            self.refresh_queue()
            self.update_display()

    def next_job(self):
        self.queue.next()
        self.refresh_queue()
        self.update_display()

    def prev_job(self):
        self.queue.prev()
        self.refresh_queue()
        self.update_display()

    def _flash_btn(self, btn):
        orig = btn.styleSheet()
        # Invert colors for simple flash
        btn.setStyleSheet("background-color: white; color: black; border-radius: 4px;")
        QTimer.singleShot(200, lambda: btn.setStyleSheet(orig))


def main():
    app = QApplication(sys.argv)
    
    # Dark theme palette
    app.setStyle("Fusion")
    
    window = PrompterWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
