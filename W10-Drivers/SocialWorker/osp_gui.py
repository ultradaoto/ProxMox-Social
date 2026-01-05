"""
One-Click Social Poster (OSP) GUI
Windows 10 Desktop Application

Updates:
- Integrates WebSocket Server to communicate with Chrome Extension.
- New "Flow-based" UI with step-by-step instructions.
- Auto-docks to right 15% of screen.
"""
import sys
import os
import json
import time
import shutil
import logging
import re
import asyncio
import threading
import websockets
from pathlib import Path
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QScrollArea, QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl, pyqtSignal, QObject
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
WS_HOST = "localhost"
WS_PORT = 8765
RECORDING_DIR = Path('C:/OSP_Recordings')
RECORDING_DIR.mkdir(parents=True, exist_ok=True)

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
logging.getLogger("websockets").setLevel(logging.WARNING) # Silence websockets INFO logs
logger = logging.getLogger('OSP_GUI')

def log_ws(msg):
    """Simple timestamped logging for WebSocket events."""
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] WS: {msg}")


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
        t = self.data.get('title')
        if t: return t
        caption = self.caption
        if caption:
            first_line = caption.split('\n')[0].strip()
            if len(first_line) < 100:
                return first_line
        return ""
        
    @property
    def caption(self) -> str:
        return self.data.get('caption') or self.data.get('body') or ""
        
    @property
    def platform(self) -> Platform:
        raw = self.data.get('platform', 'unknown').lower()
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
        if not media: return None
        local_name = media[0].get('local_path')
        if local_name: return str(self.path / local_name)
        return None

    @property
    def link(self) -> Optional[str]:
        if self.data.get('platform_url'): return self.data.get('platform_url')
        options = self.data.get('options', {})
        if isinstance(options, dict) and options.get('target_url'): return options.get('target_url')
        if self.data.get('link'): return self.data.get('link')
        return None

    @property
    def hashtags(self) -> str:
        # Extract hashtags from data or caption
        tags = self.data.get('hashtags', [])
        if isinstance(tags, list):
            return ' '.join(tags)
        return str(tags) if tags else ""

    @property
    def email_members(self) -> bool:
        return self.data.get('email_members', False)


class JobQueue:
    """Manages local job folders."""
    def __init__(self):
        self.jobs: List[LocalJob] = []
        self.current_index: int = 0
        
    def refresh(self) -> int:
        new_jobs = []
        try:
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
            if self.current_index >= len(self.jobs):
                self.current_index = max(0, len(self.jobs) - 1)
            return len(self.jobs)
        except Exception as e:
            logger.error(f"Failed to refresh queue: {e}")
            return 0

    @property
    def current_job(self) -> Optional[LocalJob]:
        if not self.jobs or self.current_index >= len(self.jobs): return None
        return self.jobs[self.current_index]

    def next(self):
        if self.current_index < len(self.jobs) - 1: self.current_index += 1

    def prev(self):
        if self.current_index > 0: self.current_index -= 1

    def complete_current(self) -> bool:
        job = self.current_job
        if not job: return False
        try:
            dest = COMPLETED_DIR / job.job_id
            if dest.exists(): shutil.rmtree(dest)
            shutil.move(str(job.path), str(dest))
            self.jobs.pop(self.current_index)
            if self.current_index >= len(self.jobs): self.current_index = max(0, len(self.jobs) - 1)
            return True
        except Exception as e:
            logger.error(f"Failed to complete job {job.job_id}: {e}")
            return False

    def fail_current(self, reason: str = "") -> bool:
        job = self.current_job
        if not job: return False
        try:
            dest = FAILED_DIR / job.job_id
            if dest.exists(): shutil.rmtree(dest)
            shutil.move(str(job.path), str(dest))
            with open(dest / 'failure_reason.txt', 'w') as f: f.write(reason)
            self.jobs.pop(self.current_index)
            if self.current_index >= len(self.jobs): self.current_index = max(0, len(self.jobs) - 1)
            return True
        except Exception as e:
            logger.error(f"Failed to fail job {job.job_id}: {e}")
            return False


# =============================================================================
# WEBSOCKET SERVER
# =============================================================================

class WSSignals(QObject):
    """Signals for the WebSocket server."""
    client_connected = pyqtSignal()
    client_disconnected = pyqtSignal()
    message_received = pyqtSignal(dict)

class WebSocketServer:
    """Asyncio-based WebSocket Server running in a separate thread."""
    def __init__(self):
        self.signals = WSSignals()
        self.clients = set()
        self.loop = None
        
    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        
    def _run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        async def main():
            try:
                async with websockets.serve(self._handler, WS_HOST, WS_PORT):
                    print(f"WebSocket Server started on ws://{WS_HOST}:{WS_PORT}")
                    await asyncio.Future()  # Run forever
            except Exception as e:
                print(f"WebSocket Server failed to start: {e}")

        self.loop.run_until_complete(main())
        
    async def _handler(self, websocket):
        self.clients.add(websocket)
        self.signals.client_connected.emit()
        log_ws(f"Client connected. Remote: {websocket.remote_address} | Total: {len(self.clients)}")
        try:
            async for message in websocket:
                data = json.loads(message)
                log_ws(f"<- RECEIVED: {data.get('type')} payload={data.get('payload')}")
                self.signals.message_received.emit(data)
            log_ws("Client disconnected (Cleanly).")
        except websockets.exceptions.ConnectionClosed:
             log_ws("Client disconnected (ConnectionClosed).")
        except Exception as e:
            log_ws(f"Error: {e}")
        finally:
            self.clients.remove(websocket)
            self.signals.client_disconnected.emit()
            log_ws(f"Client removed. Total: {len(self.clients)}")

    def send(self, msg_type: str, payload: Dict[str, Any] = None):
        """Send message to all clients."""
        if not self.loop: return
        
        log_ws(f"-> SENDING: {msg_type} payload={payload}")
        message = json.dumps({"type": msg_type, "payload": payload or {}})
        asyncio.run_coroutine_threadsafe(self._send_all(message), self.loop)
        
    async def _send_all(self, message):
        if self.clients:
            await asyncio.gather(*[client.send(message) for client in self.clients])


# =============================================================================
# GUI
# =============================================================================

class PrompterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Logic
        self.queue = JobQueue()
        self.queue.refresh()
        self.ws_server = WebSocketServer()
        self.ws_server.signals.client_connected.connect(self.on_ws_connected)
        self.ws_server.signals.client_disconnected.connect(self.on_ws_disconnected)
        self.ws_server.signals.message_received.connect(self.on_ws_message)
        self.ws_server.start()
        
        # State
        self.is_recording = False
        self.current_step = 0
        self.target_width = 300
        
        # UI Setup
        self._setup_window()
        self._setup_ui()
        self._setup_shortcuts()
        
        # Timers
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self.refresh_queue)
        self.poll_timer.start(5000)
        
        self.dock_timer = QTimer()
        self.dock_timer.timeout.connect(self.enforce_docking)
        self.dock_timer.start(2000)
        
        # Initial State
        self.update_display()
        QTimer.singleShot(100, self.enforce_docking)

    def _setup_window(self):
        self.setWindowTitle("OSP Queue")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

    def enforce_docking(self):
        screen = QApplication.primaryScreen().availableGeometry()
        width = screen.width()
        height = screen.height()
        x_offset = screen.x()
        y_offset = screen.y()
        
        osp_width = int(width * 0.15)
        self.target_width = osp_width
        chrome_width = width - osp_width
        
        self.setGeometry(x_offset + width - osp_width, y_offset, osp_width, height)
        self.setMaximumWidth(osp_width)
        
        if gw:
            try:
                chrome_windows = [w for w in gw.getAllWindows() if 'Chrome' in w.title or 'Google Chrome' in w.title]
                for w in chrome_windows:
                    if w.visible:
                        if abs(w.width - chrome_width) > 50 or abs(w.left - x_offset) > 50:
                            w.restore()
                            w.resizeTo(chrome_width, height)
                            w.moveTo(x_offset, y_offset)
            except Exception:
                pass

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # --- TOP STATUS BAR ---
        status_layout = QHBoxLayout()
        self.conn_label = QLabel("● Disconnected")
        self.conn_label.setStyleSheet("color: #ef4444; font-size: 11px;") # Red
        status_layout.addWidget(self.conn_label)
        
        self.count_label = QLabel("Queue: 0")
        self.count_label.setStyleSheet("color: #aaa; font-size: 11px;")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_layout.addWidget(self.count_label)
        layout.addLayout(status_layout)
        
        # --- MAIN INSTRUCTION BUTTON ---
        self.btn_instruction = QPushButton("WAITING FOR JOB")
        self.btn_instruction.setMinimumHeight(60)
        self.btn_instruction.clicked.connect(self.on_instruction_click)
        self.btn_instruction.setStyleSheet("""
            QPushButton {
                background-color: #333; color: #888; border: none; 
                border-radius: 6px; font-weight: bold; font-size: 16px;
            }
        """)
        layout.addWidget(self.btn_instruction)
        
        # --- STEP INFO ---
        self.step_label = QLabel("Step: None")
        self.step_label.setStyleSheet("color: #888; font-size: 12px;")
        layout.addWidget(self.step_label)
        
        # --- JOB CONTENT ---
        self.content_frame = QFrame()
        self.content_frame.setStyleSheet("background: #2d2d2d; border-radius: 5px;")
        content_layout = QVBoxLayout(self.content_frame)
        
        # Platform Header
        self.platform_label = QLabel("Platform: ---")
        self.platform_label.setStyleSheet("color: white; font-weight: bold;")
        content_layout.addWidget(self.platform_label)

        # Email Alert Label (Hidden by default)
        self.email_alert_label = QLabel("📧 TOGGLE EMAIL TO MEMBERS")
        self.email_alert_label.setStyleSheet("background-color: #ef4444; color: white; font-weight: bold; padding: 4px; border-radius: 4px;")
        self.email_alert_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.email_alert_label.hide()
        content_layout.addWidget(self.email_alert_label)

        # Image Preview
        self.image_label = QLabel()
        self.image_label.setMinimumHeight(100)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background: #000; border-radius: 3px;")
        content_layout.addWidget(self.image_label)
        
        # Content Text
        self.content_text = QLabel()
        self.content_text.setWordWrap(True)
        self.content_text.setStyleSheet("color: #ddd;")
        content_layout.addWidget(self.content_text)
        
        layout.addWidget(self.content_frame)
        
        # --- MANUAL ACTIONS ---
        actions_label = QLabel("Manual Actions")
        actions_label.setStyleSheet("color: #666; font-size: 10px; margin-top: 10px;")
        layout.addWidget(actions_label)
        
        # Open URL
        self.btn_open_url = self._make_btn("1. OPEN URL", self.open_link_action, "#444")
        layout.addWidget(self.btn_open_url)
        
        # Copy Buttons
        copy_layout = QHBoxLayout()
        self.btn_copy_title = self._make_btn("2. COPY TITLE", self.copy_title_action, "#444")
        self.btn_copy_body = self._make_btn("3. COPY BODY", self.copy_body_action, "#444")
        copy_layout.addWidget(self.btn_copy_title)
        copy_layout.addWidget(self.btn_copy_body)
        layout.addLayout(copy_layout)

        # Image Actions Row (Restored)
        img_btns_layout = QHBoxLayout()
        self.btn_copy_img_path = self._make_btn("COPY IMG PATH", self.copy_image_path_action, "#3b82f6") # Blue
        self.btn_copy_img_data = self._make_btn("COPY IMG DATA", self.copy_image_data_action, "#8b5cf6") # Purple
        img_btns_layout.addWidget(self.btn_copy_img_path)
        img_btns_layout.addWidget(self.btn_copy_img_data)
        layout.addLayout(img_btns_layout)

        # Navigation
        nav_layout = QHBoxLayout()
        self.btn_fail = self._make_btn("✗ Fail", self.mark_failed, "#ef4444")
        self.btn_done = self._make_btn("✓ Done", self.mark_complete, "#22c55e")
        nav_layout.addWidget(self.btn_fail)
        nav_layout.addWidget(self.btn_done)
        layout.addLayout(nav_layout)
        
        # Nav Arrows
        arrows_layout = QHBoxLayout()
        self.btn_prev = self._make_btn("←", self.prev_job, "#333")
        self.btn_next = self._make_btn("→", self.next_job, "#333")
        arrows_layout.addWidget(self.btn_prev)
        arrows_layout.addWidget(self.btn_next)
        layout.addLayout(arrows_layout)

        # Style Global
        self.setStyleSheet("QMainWindow { background: #1a1a1a; } QLabel { font-family: Segoe UI; }")
    
    def _make_btn(self, text, func, color):
        btn = QPushButton(text)
        btn.clicked.connect(func)
        btn.setFixedHeight(30)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: white; border: none; 
                border-radius: 4px; font-weight: bold; font-size: 11px;
            }}
            QPushButton:hover {{ background-color: white; color: black; }}
        """)
        return btn

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+1"), self).activated.connect(self.open_link_action)
        QShortcut(QKeySequence("Ctrl+2"), self).activated.connect(self.copy_title_action)
        QShortcut(QKeySequence("Ctrl+3"), self).activated.connect(self.copy_body_action)
        QShortcut(QKeySequence("Ctrl+4"), self).activated.connect(self.copy_image_path_action)
        QShortcut(QKeySequence("Ctrl+5"), self).activated.connect(self.copy_image_data_action)
        QShortcut(QKeySequence("Ctrl+Return"), self).activated.connect(self.mark_complete)
        QShortcut(QKeySequence("Ctrl+Right"), self).activated.connect(self.next_job)

    # --- WEBSOCKET HANDLERS ---
    def on_ws_connected(self):
        self.conn_label.setText("● Connected")
        self.conn_label.setStyleSheet("color: #22c55e; font-size: 11px;") # Green

    def on_ws_disconnected(self):
        self.conn_label.setText("● Disconnected")
        self.conn_label.setStyleSheet("color: #ef4444; font-size: 11px;")

    def on_ws_message(self, data):
        msg_type = data.get("type")
        payload = data.get("payload", {})
        
        if msg_type == "page_loaded":
            if self.is_recording:
                log_ws("Page loaded (Recording Mode) - Skipping auto-guide")
                return

            # Page loaded -> Prompt to copy title
            self.set_instruction_step("COPY TITLE", "#22c55e", self.copy_title_action)
            self.ws_server.send("highlight_element", {
                "selector": "[data-placeholder='Title'], .title-input, input[name='title']",
                "label": "CLICK HERE - Title"
            })
            
        elif msg_type == "request_copy":
            field = payload.get("field")
            if field == "title":
                self.set_instruction_step("COPY TITLE", "#22c55e", self.copy_title_action)
            elif field == "body":
                self.set_instruction_step("COPY BODY", "#22c55e", self.copy_body_action)
                
        elif msg_type == "paste_detected":
            selector = payload.get("selector", "")
            
            if self.is_recording:
                # Record paste event
                record_payload = payload.copy()
                record_payload['action'] = 'paste'
                self.record_interaction(record_payload, source="chrome")
                return

            if "title" in selector.lower():
                # Title pasted -> Move to body
                self.set_instruction_step("COPY BODY", "#22c55e", self.copy_body_action)
                self.ws_server.send("highlight_element", {
                    "selector": "[data-placeholder='Write something...'], textarea, .body-input",
                    "label": "CLICK HERE - Body"
                })
            elif "write" in selector.lower() or "body" in selector.lower():
                # Body pasted -> Move to submit
                self.set_instruction_step("CLICK POST", "#22c55e", self.mark_complete) # Or just indicate done?
                self.ws_server.send("highlight_element", {
                    "selector": "button[type='submit'], .post-button",
                    "label": "CLICK TO POST"
                })
                self.btn_instruction.setText("MARK DONE")
                self.btn_instruction.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; border-radius: 6px;")

        elif msg_type == "interaction_recorded":
            self.record_interaction(payload)

        elif msg_type == "element_not_found":
            selector = payload.get("selector", "unknown")
            self.set_instruction_step("ELEMENT NOT FOUND", "#ef4444", lambda: None) # Red
            self.conn_label.setText(f"Missing: {selector}")
            self.conn_label.setStyleSheet("color: #ef4444; font-size: 11px;")

        elif msg_type == "start_recording":
            self.is_recording = True
            log_ws("Entered Recording Mode")
            self.set_instruction_step("🔴 RECORDING...", "#ef4444", lambda: None)
            self.conn_label.setText("● Recording")
            self.conn_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px;")

        elif msg_type == "stop_recording":
            self.is_recording = False
            log_ws("Exited Recording Mode")
            self.reset_flow()

    # --- ACTION LOGIC ---
    def record_interaction(self, payload: Dict, source: str = "chrome"):
        """Save recorded interaction to file."""
        try:
            timestamp = time.strftime("%Y%m%d")
            job = self.queue.current_job
            platform = job.platform.value if job else "unknown"
            
            filename = f"recording_{platform}_{timestamp}.json"
            filepath = RECORDING_DIR / filename
            
            # Read existing
            recordings = []
            if filepath.exists():
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        recordings = json.load(f)
                except:
                    pass
            
            # Append new
            entry = {
                "timestamp": time.time(),
                "job_id": job.job_id if job else None,
                "source": source,
                "interaction": payload
            }
            recordings.append(entry)
            
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recordings, f, indent=2)
                
            log_ws(f"Recorded step ({source}): {payload.get('action') or payload.get('selector')} -> {filename}")
            
        except Exception as e:
            log_ws(f"Failed to record interaction: {e}")

    def reset_flow(self):
        self.current_step = 0
        self.set_instruction_step("OPEN URL", "#22c55e", self.open_link_action)

    def set_instruction_step(self, text, color, func):
        self.btn_instruction.setText(text)
        self.btn_instruction.clicked.disconnect()
        self.btn_instruction.clicked.connect(func)
        self.btn_instruction.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; color: white; border: none; 
                border-radius: 6px; font-weight: bold; font-size: 16px;
                border: 2px solid white;
            }}
            QPushButton:hover {{ background-color: white; color: {color}; }}
        """)

    def on_instruction_click(self):
        log_ws("UI: Instruction/Main Button Clicked")
        # Placeholder
        pass

    def open_link_action(self):
        log_ws("UI: Open URL Button Clicked")
        self.record_interaction({"action": "open_url"}, source="osp")
        job = self.queue.current_job
        if job and job.link:
            self.ws_server.send("open_url", {"url": job.link})
            self.set_instruction_step("WAITING FOR CHROME...", "#eab308", lambda: None) # Yellow
            self.btn_instruction.setEnabled(False)
            # Re-enable after 5s timestamp to prevent lock
            QTimer.singleShot(5000, lambda: self.btn_instruction.setEnabled(True))
        else:
            self.open_link() # Fallback

    def copy_title_action(self):
        log_ws("UI: Copy Title Clicked")
        self.record_interaction({"action": "copy_title"}, source="osp")
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.title)
            self._flash_btn(self.btn_copy_title)
            self.set_instruction_step("PASTE IN CHROME", "#3b82f6", lambda: None) # Blue

    def copy_body_action(self):
        log_ws("UI: Copy Body Clicked")
        self.record_interaction({"action": "copy_body"}, source="osp")
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.caption)
            self._flash_btn(self.btn_copy_body)
            self.set_instruction_step("PASTE IN CHROME", "#3b82f6", lambda: None)

    def copy_image_path_action(self):
        job = self.queue.current_job
        if job and job.image_path:
            # Copy absolute path
            pyperclip.copy(str(Path(job.image_path).absolute()))
            self._flash_btn(self.btn_copy_img_path)

    def copy_image_data_action(self):
        job = self.queue.current_job
        if job and job.image_path:
            try:
                img = QImage(job.image_path)
                QApplication.clipboard().setImage(img)
                self._flash_btn(self.btn_copy_img_data)
                self.record_interaction({"action": "copy_img_data"}, source="osp")
            except Exception as e:
                print(f"Failed to copy image: {e}")

    # --- STANDARD QUEUE ACTIONS ---
    def refresh_queue(self):
        count = self.queue.refresh()
        self.count_label.setText(f"Queue: {self.queue.current_index + 1}/{count}" if count > 0 else "Queue: 0")
        if count > 0 and self.platform_label.text() == "Platform: ---":
            self.update_display()
        if count == 0:
            self.update_display()

    def update_display(self):
        job = self.queue.current_job
        if not job:
            self.platform_label.setText("Platform: ---")
            self.content_text.setText("No Job Selected")
            self.image_label.clear()
            self.btn_instruction.setText("NO JOBS")
            self.btn_instruction.setStyleSheet("background-color: #333; color: #666;")
            return

        self.reset_flow()
        
        color = PLATFORM_COLORS.get(job.platform, "#888888")
        self.platform_label.setText(f"Platform: {job.platform.value.upper()}")
        self.platform_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 14px;")
        
        if job.email_members:
            self.email_alert_label.show()
        else:
            self.email_alert_label.hide()

        self.content_text.setText(f"{job.title}\n---\n{job.caption[:50]}...")
        
        img_path = job.image_path
        if img_path and os.path.exists(img_path):
            try:
                pixmap = QPixmap(img_path).scaled(
                    200, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(pixmap)
            except:
                self.image_label.setText("Img Error")
        else:
            self.image_label.setText("No Image")

    def mark_complete(self):
        log_ws("UI: Mark Complete Clicked")
        self.record_interaction({"action": "mark_done"}, source="osp")
        if self.queue.complete_current():
            self.refresh_queue()
            self.update_display()

    def mark_failed(self):
        log_ws("UI: Mark Failed Clicked")
        if self.queue.fail_current("User marked failed"):
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

    def open_link(self):
        job = self.queue.current_job
        if job and job.link:
            QDesktopServices.openUrl(QUrl(job.link))

    def _flash_btn(self, btn):
        orig = btn.styleSheet()
        btn.setStyleSheet("background-color: white; color: black;")
        QTimer.singleShot(200, lambda: btn.setStyleSheet(orig))


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PrompterWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
