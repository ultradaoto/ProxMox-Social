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
from datetime import datetime
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
    QPushButton, QLabel, QScrollArea, QFrame, QMessageBox, QSizePolicy,
    QListWidget, QAbstractItemView, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, QTimer, QSize, QUrl, pyqtSignal, QObject
from PyQt6.QtGui import QPixmap, QImage, QShortcut, QKeySequence, QIcon, QAction, QDesktopServices, QColor
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
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self.loop)
        
    async def broadcast(self, message):
        if self.clients:
            # Create a list of tasks for sending messages
            send_tasks = []
            for client in list(self.clients): # Iterate over a copy to allow modification during iteration
                send_tasks.append(client.send(message))
            
            # Run all send tasks concurrently, ignoring individual errors
            await asyncio.gather(*send_tasks, return_exceptions=True)


# =============================================================================
# GUI
# =============================================================================

class WorkflowEditor(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OSP Workflow Editor")
        self.resize(1100, 700)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #e0e0e0; }
            QListWidget { background-color: #252526; border: 1px solid #333; color: #e0e0e0; }
            QListWidget::item:selected { background-color: #37373d; }
            QLabel { color: #ccc; }
        """)
        
        # Central Widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        
        # Splitter for 3 Panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- LEFT: PLATFORMS ---
        plat_widget = QWidget()
        plat_layout = QVBoxLayout(plat_widget)
        plat_layout.setContentsMargins(0, 0, 0, 0)
        plat_label = QLabel("1. Platform")
        plat_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        plat_layout.addWidget(plat_label)
        
        self.plat_list = QListWidget()
        self.plat_list.itemClicked.connect(self.filter_files_by_platform)
        plat_layout.addWidget(self.plat_list)
        splitter.addWidget(plat_widget)
        
        # --- MIDDLE: RECORDINGS ---
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        file_layout.setContentsMargins(0, 0, 0, 0)
        file_label = QLabel("2. Recordings (Newest First)")
        file_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        file_layout.addWidget(file_label)
        
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.load_steps)
        file_layout.addWidget(self.file_list)
        
        self.file_info_label = QLabel("Select a file...")
        self.file_info_label.setStyleSheet("color: #888; font-size: 11px;")
        file_layout.addWidget(self.file_info_label)
        
        splitter.addWidget(file_widget)
        
        # --- RIGHT: STEPS ---
        step_widget = QWidget()
        step_layout = QVBoxLayout(step_widget)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_label = QLabel("3. Steps Editor")
        step_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        step_layout.addWidget(step_label)
        
        self.step_list = QListWidget()
        self.step_list.setStyleSheet("background-color: #252526; border: 1px solid #333; font-family: Consolas;")
        self.step_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        step_layout.addWidget(self.step_list)
        splitter.addWidget(step_widget)
        splitter.setSizes([150, 250, 600])
        
        # Add Splitter to Main Layout
        main_layout.addWidget(splitter, stretch=4)
        
        # --- FAR RIGHT: CONTROLS ---
        ctrl_layout = QVBoxLayout()
        ctrl_label = QLabel("Actions")
        ctrl_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #fff;")
        ctrl_layout.addWidget(ctrl_label)
        
        btn_style = "background-color: #333; padding: 8px; border-radius: 4px; margin-bottom: 5px;"
        
        self.btn_up = QPushButton("Move Up ▲")
        self.btn_up.setStyleSheet(btn_style)
        self.btn_up.clicked.connect(self.move_up)
        ctrl_layout.addWidget(self.btn_up)
        
        self.btn_down = QPushButton("Move Down ▼")
        self.btn_down.setStyleSheet(btn_style)
        self.btn_down.clicked.connect(self.move_down)
        ctrl_layout.addWidget(self.btn_down)
        
        self.btn_del = QPushButton("Delete Step")
        self.btn_del.setStyleSheet("background-color: #ef4444; color: white; padding: 8px; border-radius: 4px;")
        self.btn_del.clicked.connect(self.delete_step)
        ctrl_layout.addWidget(self.btn_del)
        
        # Spacer
        ctrl_layout.addSpacing(10)
        
        self.btn_del_file = QPushButton("Delete Rec 🗑️")
        self.btn_del_file.setStyleSheet("background-color: #7f1d1d; color: #fca5a5; padding: 8px; border-radius: 4px; border: 1px solid #ef4444;")
        self.btn_del_file.setToolTip("Delete the entire recording file")
        self.btn_del_file.clicked.connect(self.delete_recording)
        ctrl_layout.addWidget(self.btn_del_file)
        
        ctrl_layout.addStretch()
        
        self.btn_save = QPushButton("Save Changes 💾")
        self.btn_save.setStyleSheet("background-color: #22c55e; color: black; padding: 10px; border-radius: 4px; font-weight: bold;")
        self.btn_save.clicked.connect(self.save_workflow)
        ctrl_layout.addWidget(self.btn_save)
        
        main_layout.addLayout(ctrl_layout, stretch=1)
        
        # Data State
        self.current_data = [] 
        self.current_file_path = None
        self.all_files = [] # Store (Path, mtime, platform)
        
        self.load_data_model()

    def load_data_model(self):
        """Scan all files and build platform list."""
        self.plat_list.clear()
        self.file_list.clear()
        self.all_files = []
        
        if not RECORDING_DIR.exists(): return
        
        # 1. Scan Files
        raw_files = sorted(RECORDING_DIR.glob("*.json"), key=os.path.getmtime, reverse=True)
        platforms = set()
        
        for f in raw_files:
            # Parse: recording_{platform}_{variant}.json
            parts = f.stem.split('_')
            platform = "Unknown"
            if len(parts) >= 2:
                platform = parts[1].capitalize()
            
            platforms.add(platform)
            self.all_files.append({
                "path": f,
                "name": f.name,
                "platform": platform,
                "mtime": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            })
            
        # 2. Populate Platforms
        item_all = QListWidgetItem("All Platforms")
        item_all.setData(Qt.ItemDataRole.UserRole, "All")
        self.plat_list.addItem(item_all)
        
        for p in sorted(platforms):
            item = QListWidgetItem(p)
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.plat_list.addItem(item)
            
        # Select "All" by default
        self.plat_list.setCurrentRow(0)
        self.filter_files_by_platform(item_all)

    def filter_files_by_platform(self, item):
        target_plat = item.data(Qt.ItemDataRole.UserRole)
        self.file_list.clear()
        self.step_list.clear()
        self.current_data = []
        self.current_file_path = None
        self.file_info_label.setText("Select a file...")
        
        for f in self.all_files:
            if target_plat == "All" or f["platform"] == target_plat:
                # Display: Filename \n Date
                disp = f"{f['name']}\n{f['mtime']}"
                list_item = QListWidgetItem(disp)
                list_item.setData(Qt.ItemDataRole.UserRole, str(f["path"]))
                self.file_list.addItem(list_item)

    def load_steps(self, item=None):
        if item:
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            self.current_file_path = path
            
            # Find meta for label
            meta = next((x for x in self.all_files if x["path"] == path), None)
            
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.current_data = json.load(f)
                
                # Update Info Label
                if meta:
                    self.file_info_label.setText(f"{meta['mtime']} | {len(self.current_data)} Steps")
                    
            except Exception as e:
                print(f"Error loading {path}: {e}")
                self.current_data = []
        
        self.render_steps()
        
    def render_steps(self):
        self.step_list.clear()
        for i, step in enumerate(self.current_data):
            source = step.get('source', 'unknown')
            interaction = step.get('interaction', {})
            # Handle both Chrome interaction types and OSP actions
            action_type = interaction.get('type') or interaction.get('action') or 'unknown'
            selector = interaction.get('selector', '')
            
            display_text = f"[{i+1}] {source.upper()}: {action_type}"
            if selector:
                display_text += f" - {selector[:40]}"
            
            list_item = QListWidgetItem(display_text)
            
            if source == 'osp':
                list_item.setForeground(QColor('#22c55e')) # Green
            else:
                list_item.setForeground(QColor('#3b82f6')) # Blue
                
            self.step_list.addItem(list_item)
            
    def move_up(self):
        row = self.step_list.currentRow()
        if row > 0:
            item = self.current_data.pop(row)
            self.current_data.insert(row - 1, item)
            self.render_steps()
            self.step_list.setCurrentRow(row - 1)
            
    def move_down(self):
        row = self.step_list.currentRow()
        if row < len(self.current_data) - 1:
            item = self.current_data.pop(row)
            self.current_data.insert(row + 1, item)
            self.render_steps()
            self.step_list.setCurrentRow(row + 1)

    def delete_step(self):
        row = self.step_list.currentRow()
        if row >= 0:
            self.current_data.pop(row)
            self.render_steps()
            if row < self.step_list.count():
                self.step_list.setCurrentRow(row)
            elif self.step_list.count() > 0:
                self.step_list.setCurrentRow(self.step_list.count() - 1)
                
    def delete_recording(self):
        if not self.current_file_path:
            QMessageBox.warning(self, "No Selection", "Please select a recording to delete.")
            return
            
        confirm = QMessageBox.question(
            self, 
            "Confirm Delete", 
            f"Are you sure you want to PERMANENTLY delete:\n{self.current_file_path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                os.remove(self.current_file_path)
                self.current_file_path = None
                self.current_data = []
                self.step_list.clear()
                self.load_data_model() # Refresh lists
                QMessageBox.information(self, "Deleted", "Recording deleted successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete file: {e}")
            
    def save_workflow(self):
        if self.current_file_path:
             try:
                 with open(self.current_file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_data, f, indent=2)
                 QMessageBox.information(self, "Saved", f"Workflow saved to {self.current_file_path.name}")
                 self.load_data_model() # Refresh timestamps
             except Exception as e:
                 QMessageBox.critical(self, "Error", f"Failed to save: {e}")

class PrompterWindow(QMainWindow):
    new_log_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        
        # Connect log signal
        self.new_log_message.connect(self.update_log_window)
        
        # Override global log_ws to use our signal
        global log_ws
        original_log_ws = log_ws
        def gui_log_ws(msg):
            original_log_ws(msg)
            self.new_log_message.emit(msg)
        log_ws = gui_log_ws
        
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
        self.recording_started = False  # Track if new recording session started
        self.playback_steps = []
        self.current_playback_index = 0
        self.current_step = 0
        self.target_width = 300
        self.last_guidance_field = None
        self.last_guidance_text = None
        
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
        
        # Restore 100% height
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
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # --- LOG WINDOW ---
        self.log_list = QListWidget()
        self.log_list.setFixedHeight(60)
        self.log_list.setStyleSheet("""
            QListWidget {
                background-color: #000; color: #22c55e; border: 1px solid #333;
                font-family: Consolas, monospace; font-size: 10px;
            }
            QListWidget::item { padding: 2px; }
        """)
        self.log_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.log_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.log_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.log_list.setWordWrap(True)
        layout.addWidget(self.log_list)

        # --- TOP STATUS BAR ---
        status_layout = QHBoxLayout()
        self.conn_label = QLabel("● Disconnected")
        self.conn_label.setStyleSheet("color: #ef4444; font-size: 11px;") # Red
        status_layout.addWidget(self.conn_label)
        
        # Mode Label (Recording/Playback)
        self.mode_label = QLabel("")
        self.mode_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        status_layout.addWidget(self.mode_label)
        
        status_layout.addStretch()
        
        # Workflow Button
        workflow_btn = QPushButton("WORKFLOWS")
        workflow_btn.setStyleSheet("background-color: #3b82f6; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        workflow_btn.clicked.connect(self.open_workflow_editor)
        status_layout.addWidget(workflow_btn)
        
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
        
        # DEBUG: Log everything from Chrome (except heartbeats)
        if msg_type != "content_ready":
            log_ws(f"RECV RAW: {msg_type}")
        
        # 1. Page Lifecycle
        if msg_type == "page_loaded":
            if self.is_recording:
                log_ws("Page loaded (Recording Mode) - Recording event for sync")
                self.record_interaction({"action": "page_loaded", "url": payload.get("url")}, source="chrome")
                
                # TRIGGER WIZARD: Start with Title guidance
                self.send_guidance("title", "Step 1: Click the TITLE input field horizontally")
                return

            if self.playback_steps:
                now = time.time()
                if not hasattr(self, 'last_nav_trigger') or (now - self.last_nav_trigger > 1.0):
                    self.last_nav_trigger = now
                    log_ws("Page loaded (Playback Mode) - Triggering Next Step (with 800ms delay)")
                    QTimer.singleShot(800, self.advance_playback)
                return

        elif msg_type == "content_ready":
            if self.playback_steps:
                now = time.time()
                if not hasattr(self, 'last_nav_trigger') or (now - self.last_nav_trigger > 1.0):
                    self.last_nav_trigger = now
                    log_ws("Content ready (Playback Mode) - Triggering Next Step (immediately)")
                    self.advance_playback()
                return

            # No macro loaded - just show generic button, UNLESS recording
            if not self.is_recording:
                self.set_instruction_step("OPEN URL", "#22c55e", self.open_link_action)
            
        # 2. Interactions (Recording & Playback)
        elif msg_type == "interaction_recorded":
            self.record_interaction(payload)
            return

        elif msg_type == "paste_detected":
            if self.is_recording:
                record_payload = payload.copy()
                record_payload['action'] = 'paste'
                self.record_interaction(record_payload, source="chrome")
                return

            # Playback Match
            match_idx = self.check_playback_match({'type': 'paste', 'action': 'paste'}, lookahead=5)
            if match_idx != -1:
                log_ws(f"Playback: Paste Matched step {match_idx}")
                self.current_playback_index = match_idx + 1
                self.advance_playback()
            else:
                # Fallback paste logic if no macro
                selector = payload.get("selector", "")
                if "title" in selector.lower():
                    self.set_instruction_step("COPY BODY", "#22c55e", self.copy_body_action)
                    self.ws_server.send("highlight_element", {
                        "selector": "[data-placeholder='Write something...'], textarea, .body-input",
                        "label": "CLICK HERE - Body"
                    })
                elif "write" in selector.lower() or "body" in selector.lower():
                    self.set_instruction_step("CLICK POST", "#22c55e", self.mark_complete)
                    self.btn_instruction.setText("MARK DONE")
                    self.btn_instruction.setStyleSheet("background-color: #22c55e; color: white; font-weight: bold; border-radius: 6px;")

        elif msg_type == "highlight_clicked":
            if self.playback_steps and self.current_playback_index < len(self.playback_steps):
                step = self.playback_steps[self.current_playback_index]
                if step.get('source') == 'chrome':
                    self.current_playback_index += 1
                    log_ws(f"Playback advanced to index {self.current_playback_index}")
                    self.advance_playback()

        # 3. Mode Control
        elif msg_type == "start_recording":
            if self.is_recording: return
            self.is_recording = True
            self.recording_started = True
            self.playback_steps = []
            self.current_playback_index = 0
            
            log_ws("Entered Recording Mode")
            self.mode_label.setText("● Recording")
            self.mode_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px; margin-left: 10px;")
            self.btn_instruction.setText("REC: waiting...")
            self.btn_instruction.setStyleSheet("""
                QPushButton {
                    background-color: #7f1d1d; color: #fca5a5; border: none; 
                    border-radius: 6px; font-weight: bold; font-size: 16px;
                    border: 2px solid #ef4444;
                }
            """)
            self.btn_instruction.setEnabled(True)

        elif msg_type == "stop_recording":
            self.is_recording = False
            log_ws("Exited Recording Mode")
            self.set_instruction_step("SAVING MACRO...", "#eab308", lambda: None)
            QTimer.singleShot(1500, self.reset_flow)

        # 4. Miscellaneous
        elif msg_type == "request_copy":
            field = payload.get("field")
            if field == "title":
                self.set_instruction_step("COPY TITLE", "#22c55e", self.copy_title_action)
            elif field == "body":
                self.set_instruction_step("COPY BODY", "#22c55e", self.copy_body_action)

        elif msg_type == "element_not_found":
            log_ws(f"Element not found: {payload.get('selector', 'unknown')}")

        # Final catch for playback matching if not in recording mode and not handled above
        if not self.is_recording and msg_type == "interaction_recorded":
            # This is a bit redundant now with the elif chain but good for safety
            pass

    # --- ACTION LOGIC ---
    def get_job_variant(self, job):
        """Extract variant from job link (e.g., 'desci' from 'skool.com/desci-xxxx')."""
        if not job or not job.link:
            return "default"
        
        try:
            # Basic parsing for Skool
            if "skool.com/" in job.link:
                parts = job.link.split("skool.com/")
                if len(parts) > 1:
                    # 'desci-2718/...' -> 'desci'
                    group_part = parts[1].split("/")[0]
                    variant = group_part.split("-")[0]
                    return variant
        except:
            pass
            
        return "default"

    def record_interaction(self, payload: Dict, source: str = "chrome", label: str = None):
        """Save recorded interaction to file."""
        # Don't record during playback - only during actual recording mode
        # ALLOW recording if self.recording_started is True (to catch Step #1)
        if not self.is_recording and not self.recording_started:
            return
            
        try:
            job = self.queue.current_job
            platform = job.platform.value if job else "unknown"
            variant = self.get_job_variant(job)
            
            # recording_skool_desci.json
            filename = f"recording_{platform}_{variant}.json"
            filepath = RECORDING_DIR / filename
            
            # If this is first record of new session, start fresh (don't append to old)
            recordings = []
            if self.recording_started:
                # New session - clear old recordings
                self.recording_started = False
                log_ws(f"New recording session - clearing {filename}")
            elif filepath.exists():
                # Continuing session - read existing
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        recordings = json.load(f)
                except:
                    pass
            
            # Append new entry
            # CLEAN SELECTOR: Remove brittle state classes like .is-empty, .is-focused, etc.
            if source == "chrome":
                selector = payload.get("selector", "")
                # Clean specific brittle classes using regex for accuracy
                import re
                # 1. Transient/State classes
                bad_classes = ['is-empty', 'is-focused', 'is-editor-empty', 'ProseMirror', 'ProseMirror-focused']
                # 2. Styled-component hashes (e.g. styled__..., sc-..., -sc-...)
                # Matches .styled__x, .sc-x, etc. or class containing -sc-
                hash_patterns = [r'\.styled__[a-zA-Z0-9_-]+', r'\.sc-[a-zA-Z0-9_-]+', r'\.[a-zA-Z0-9_-]+-sc-[a-zA-Z0-9_-]+']
                
                for cls in bad_classes:
                    pattern = rf'\.{re.escape(cls)}(?=[.>\s]|$)'
                    selector = re.sub(pattern, '', selector)
                
                for pattern in hash_patterns:
                    selector = re.sub(pattern, '', selector)
                
                # Clean up any Double Spaces or leading/trailing separators left over
                selector = selector.replace("  ", " ").replace(" >  >", " >").strip()
                selector = re.sub(r'\s*>\s*', ' > ', selector) # Normalize spacing around arrows
                payload["selector"] = selector

            # Auto-generate Label if missing
            if not label:
                if source == "osp":
                    # For OSP actions, use a clean uppercase name
                    label = f"{payload.get('action', 'action').upper().replace('_', ' ')}"
                elif source == "chrome":
                    action = payload.get('type') or payload.get('action') or "interaction"
                    selector = payload.get('selector', '')
                    element_type = payload.get('element_type', '').upper()
                    
                    if "title" in selector.lower():
                        label = f"TYPE TITLE" if action == "paste" else "CLICK TITLE INPUT"
                    elif "placeholder" in selector.lower() and ("write" in selector.lower() or "body" in selector.lower()):
                        label = f"TYPE BODY" if action == "paste" else "CLICK BODY INPUT"
                    elif "submit" in selector.lower() or "jhqXbj" in selector or "post" in selector.lower():
                        label = f"CLICK POST BUTTON"
                    elif action == "paste":
                        label = f"PASTE INTO {element_type if element_type else 'BOX'}"
                    else:
                        label = f"CLICK {element_type if element_type else 'ELEMENT'}"

            entry = {
                "timestamp": time.time(),
                "job_id": job.job_id if job else None,
                "source": source,
                "label": label,
                "interaction": payload
            }
            recordings.append(entry)
            
            # Update UI with step count for live feedback
            step_num = len(recordings)
            action_desc = payload.get('type') or payload.get('action') or "click"
            selector = payload.get('selector', '')
            if len(selector) > 15:
                selector = selector[:15] + "..."
            
            self.btn_instruction.setText(f"REC: {label[:15]}... ({step_num})")
            
            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(recordings, f, indent=2)
                
            log_ws(f"Recorded ({source}): {action_desc} -> {filename} (Step {step_num})")
            
        except Exception as e:
            log_ws(f"Failed to record interaction: {e}")

    def load_playback_macro(self):
        """Try to load a macro for the current variant."""
        job = self.queue.current_job
        if not job: return
        
        platform = job.platform.value
        variant = self.get_job_variant(job)
        filename = f"recording_{platform}_{variant}.json"
        filepath = RECORDING_DIR / filename
        
        if filepath.exists():
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.playback_steps = json.load(f)
                self.current_playback_index = 0
                log_ws(f"Loaded macro: {filename} ({len(self.playback_steps)} steps)")
                
                # Update Mode Indicator (Yellow)
                self.mode_label.setText("● Playback")
                self.mode_label.setStyleSheet("color: #eab308; font-weight: bold; font-size: 11px; margin-left: 10px;")
                
                self.advance_playback()
                return True
            except Exception as e:
                log_ws(f"Error loading macro: {e}")
                return False
        else:
            log_ws(f"No macro found for {variant}")
            return False

    def check_playback_match(self, payload, lookahead=3):
        """Check if payload matches current or future steps."""
        if not self.playback_steps: return -1
        
        start = self.current_playback_index
        end = min(len(self.playback_steps), start + lookahead)
        
        for i in range(start, end):
            step = self.playback_steps[i]
            if step.get('source') != 'chrome': continue
            
            expected = step.get('interaction', {})
            
            # Match Logic
            # 1. Action Name (e.g., 'paste')
            if payload.get('action') == 'paste' and expected.get('action') == 'paste':
                return i
            
            # 2. Event Type (click vs click)
            p_type = payload.get('type')
            e_type = expected.get('type')
            
            if p_type and e_type and p_type == e_type:
                # Optional: Check selector similarity? For now, type is usually enough for sequential flow
                return i
                
        return -1

    def advance_playback(self):
        """Update UI to show next expected step and send Chrome highlight."""
        if not self.playback_steps: return
        
        log_ws(f"advance_playback: starting at index {self.current_playback_index}")
        
        # Skip any already-completed OSP steps (like open_url which triggered page_loaded)
        while self.current_playback_index < len(self.playback_steps):
            step = self.playback_steps[self.current_playback_index]
            source = step.get('source')
            interaction = step.get('interaction', {})
            
            # For OSP steps: show the label AND look ahead for next Chrome highlight
            if source == 'osp':
                action = interaction.get('action')
                # Skip open_url since that already happened
                if action == 'open_url':
                    self.current_playback_index += 1
                    continue
                    
                label = action.upper().replace("_", " ")
                self.set_instruction_step(f"→ {label}", "#8b5cf6", lambda: None)
                
                # IMPORTANT: Look ahead and send highlight for next Chrome step
                self._send_next_chrome_highlight()
                return
            
            elif source == 'chrome':
                action_type = interaction.get('type')
                action_name = interaction.get('action')
                selector = interaction.get('selector')
                
                # Skip page_loaded events during playback (they are sync points, not interaction steps)
                if action_name == 'page_loaded' or action_type == 'page_loaded':
                    self.current_playback_index += 1
                    continue

                # Use the label from the recording if available, else fallback to generic
                label = step.get('label')
                if not label or label == "CLICK HIGHLIGHT" or label == "PASTE CONTENT":
                    label = "PASTE CONTENT" if action_name == "paste" else "CLICK HIGHLIGHT"
                
                color = "#3b82f6"
                if "PASTE" in label or "TYPE" in label:
                    color = "#eab308"
                elif "POST" in label or "SUBMIT" in label:
                    color = "#ef4444"
                
                # Send highlight to Chrome ONLY if we have a selector
                if selector:
                    log_ws(f"advance_playback: sending highlight for {selector[:30]}...")
                    self.ws_server.send("highlight_element", {
                        "selector": selector,
                        "label": label
                    })
                else:
                    log_ws("advance_playback: skipping step with empty selector")
                    self.current_playback_index += 1
                    continue
                
                self.set_instruction_step(f"→ {label}", color, lambda: None)
                return
            
            self.current_playback_index += 1
            
        self.set_instruction_step("WORKFLOW COMPLETED", "#22c55e", lambda: None)
    
    def _send_next_chrome_highlight(self):
        """Look ahead from current position and send highlight for next Chrome step."""
        for i in range(self.current_playback_index + 1, len(self.playback_steps)):
            step = self.playback_steps[i]
            if step.get('source') == 'chrome':
                interaction = step.get('interaction', {})
                selector = interaction.get('selector')
                action_name = interaction.get('action') or interaction.get('type')
                
                # SKIP page loads or empty selectors
                if action_name == 'page_loaded' or not selector:
                    log_ws("_send_next_chrome_highlight: skipping empty selector or page_loaded")
                    continue

                label = step.get('label')
                if not label or label == "CLICK HIGHLIGHT" or label == "PASTE CONTENT":
                    label = "PASTE HERE" if action_name == "paste" else "CLICK HERE"
                
                log_ws(f"_send_next_chrome_highlight: sending highlight for {selector[:30]}...")
                self.ws_server.send("highlight_element", {
                    "selector": selector,
                    "label": label
                })
                return
        
        log_ws("_send_next_chrome_highlight: no more Chrome steps found")

    def trigger_playback_step(self, action_name):
        """Called when a button is clicked. Advances macro if it matches."""
        if not self.playback_steps: return
        
        # Check if current expected step matches this action
        if self.current_playback_index < len(self.playback_steps):
            step = self.playback_steps[self.current_playback_index]
            if step.get('source') == 'osp':
                expected = step.get('interaction', {}).get('action')
                if expected == action_name:
                    self.current_playback_index += 1
                    # Slight delay to let the click register visually
                    QTimer.singleShot(500, self.advance_playback)

    def reset_flow(self):
        # GUARD: Don't reset if we are actively recording! 
        # This prevents the poll timer from killing a session.
        if self.is_recording:
            log_ws("reset_flow: Blocked by active recording")
            return

        # Reset Mode Label
        self.mode_label.setText("")
        
        # Reset Connection Label (Always Green if connected, but here we assume connected if resetting flow)
        self.conn_label.setText("● Connected")
        self.conn_label.setStyleSheet("color: #22c55e; font-size: 11px;")
        
        self.is_recording = False

        # Button State based on Queue
        if self.queue.current_job:
            self.set_instruction_step("OPEN URL", "#22c55e", self.open_link_action)
        else:
            self.set_instruction_step("NO JOBS", "#555", lambda: None)
            self.btn_instruction.setEnabled(False)

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
        
        if self.is_recording:
            # ALREADY RECORDING - CONTINUE SESSION
            log_ws("Already in Recording Mode - Recording Open URL as a step")
            # If this is the VERY first step, we might want to restart, but usually user just clicked Record -> then Open URL
            # So we record it.
            self.record_interaction({"action": "open_url"}, source="osp", label="Launch Browser & Navigation")
            # Signal Chrome just in case
            self.ws_server.send("start_recording", {"reapply": True})
        else:
            # NOT RECORDING - TRY PLAYBACK OR START NEW RECORDING
            macro_loaded = self.load_playback_macro()
            
            if macro_loaded:
                # PLAYBACK MODE
                log_ws("Macro found - Starting Playback")
                self.is_recording = False
                self.recording_started = False
            else:
                # NO MACRO - START NEW RECORDING SESSION
                log_ws("No macro found - Starting New Recording Session")
                self.is_recording = True
                self.recording_started = True 
                
                # Record Step 1 (Open URL)
                self.record_interaction({"action": "open_url"}, source="osp", label="Launch Browser & Navigation")
                
                # Synchronize Chrome with Recording Mode
                self.ws_server.send("start_recording", {})
                
                # Update Mode Indicator for Recording
                self.mode_label.setText("● Recording")
                self.mode_label.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 11px; margin-left: 10px;")

        # Track the step internally
        self.trigger_playback_step("open_url")
        
        job = self.queue.current_job
        if job and job.link:
            self.ws_server.send("open_url", {"url": job.link})
            self.set_instruction_step("WAITING FOR CHROME INFO...", "#eab308", lambda: None)
            self.btn_instruction.setEnabled(False)
            QTimer.singleShot(4000, lambda: self.btn_instruction.setEnabled(True))
        else:
            self.open_link()

    def copy_title_action(self):
        log_ws("UI: Copy Title Clicked")
        self.record_interaction({"action": "copy_title"}, source="osp", label="Copy Title from OSP")
        self.trigger_playback_step("copy_title")
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.title)
            self._flash_btn(self.btn_copy_title)
            self.set_instruction_step("PASTE IN CHROME", "#3b82f6", lambda: None)
            
            # TRIGGER WIZARD: Support visual guidance in Chrome
            self.send_guidance("title", "Title copied! Now CLICK & PASTE it into the highlighted box")

            # DIRECTIVE: Record that we are asking Chrome to highlight the Title
            self.record_interaction({
                "action": "directive", 
                "directive": "highlight_element",
                "selector": "[placeholder='Title'], .title-input",
                "label": "Highlight Title Input"
            }, source="osp", label="Directive: Point to Title Input") # Blue

    def copy_body_action(self):
        log_ws("UI: Copy Body Clicked")
        self.record_interaction({"action": "copy_body"}, source="osp", label="Copy Caption/Body from OSP")
        self.trigger_playback_step("copy_body")
        job = self.queue.current_job
        if job:
            pyperclip.copy(job.caption)
            self._flash_btn(self.btn_copy_body)
            self.set_instruction_step("PASTE IN CHROME", "#3b82f6", lambda: None)
            
            # TRIGGER WIZARD: Support visual guidance in Chrome
            self.send_guidance("body", "Body copied! Now CLICK & PASTE it into the highlighted box")

            # DIRECTIVE: Record highlight for Body
            self.record_interaction({
                "action": "directive",
                "directive": "highlight_element",
                "selector": "[data-placeholder='Write something...'], .tiptap.skool-editor, textarea",
                "label": "Highlight Body Input"
            }, source="osp", label="Directive: Point to Body Input")

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
                self.record_interaction({"action": "copy_img_data"}, source="osp", label="Copy Image Data")
                self.trigger_playback_step("copy_img_data")
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
        # Reset guidance tracking so highlights can be re-triggered for new jobs
        self.last_guidance_field = None
        self.last_guidance_text = None
        
        job = self.queue.current_job
        if not job:
            self.platform_label.setText("Platform: ---")
            self.content_text.setText("No Job Selected")
            self.image_label.clear()
            self.btn_instruction.setText("NO JOBS")
            self.btn_instruction.setStyleSheet("background-color: #333; color: #666;")
            return

        if not self.is_recording:
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
        self.record_interaction({"action": "mark_done"}, source="osp", label="Workflow Completed Successfully")
        self.trigger_playback_step("mark_done")
        if self.queue.complete_current():
            self.refresh_queue()
            self.update_display()

    def mark_failed(self):
        log_ws("UI: Mark Failed Clicked")
        self.record_interaction({"action": "mark_failed"}, source="osp", label="Workflow Marked as Failed")
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

    def update_log_window(self, msg):
        """Add message to log window and keep last 3."""
        # Strip timestamp for UI cleanliness if present
        display_msg = msg
        if "] WS: " in msg:
            display_msg = msg.split("] WS: ")[1]
        
        # Truncate long messages to prevent UI overflow
        max_len = 50
        if len(display_msg) > max_len:
            display_msg = display_msg[:max_len] + "..."
            
        self.log_list.addItem(display_msg)
        self.log_list.scrollToBottom()
        
        while self.log_list.count() > 3:
            self.log_list.takeItem(0)

    def send_guidance(self, field: str, text: str):
        """Send guidance to Chrome, but only if it's different from the last signal."""
        if field == self.last_guidance_field and text == self.last_guidance_text:
            return
            
        self.last_guidance_field = field
        self.last_guidance_text = text
        
        if field:
            self.ws_server.send("suggest_field", {"field": field})
        if text:
            self.ws_server.send("show_instruction", {"text": text})

    def open_workflow_editor(self):
        self.workflow_editor = WorkflowEditor(self)
        self.workflow_editor.show()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PrompterWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
