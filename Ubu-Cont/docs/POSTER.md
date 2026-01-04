# POSTER.md - Ubuntu Social Media Poster (Computer-Use Agent)

## Overview

The Poster runs on **Ubuntu** and controls the Windows 10 machine via:
- **VNC** for screen capture (seeing what's on the Windows desktop)
- **Virtual HID devices** for mouse/keyboard input (controlling the Windows machine)

This architecture ensures the Windows 10 machine sees genuine-looking Logitech hardware input, not Playwright or any automation library. Facebook, Instagram, and other platforms cannot detect automation.

```
┌─────────────────────────────────────────────────────────────────┐
│                         UBUNTU VM                                │
│                    (AI Controller / Poster)                      │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  POSTER (this component)                                  │  │
│   │                                                           │  │
│   │  1. Read job from shared folder or network path           │  │
│   │  2. Capture Windows screen via VNC                        │  │
│   │  3. Analyze with Qwen2.5-VL vision model                  │  │
│   │  4. Send mouse/keyboard via virtual HID                   │  │
│   │  5. Verify success with vision                            │  │
│   │  6. Report back to dashboard API                          │  │
│   └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              │ VNC (screen capture)              │
│                              │ Virtual HID (mouse/keyboard)      │
│                              ▼                                   │
└──────────────────────────────┼───────────────────────────────────┘
                               │
┌──────────────────────────────┼───────────────────────────────────┐
│                         WINDOWS 10 VM                            │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  REAL CHROME BROWSER                                      │  │
│   │  - Normal Chrome installation (not Playwright)            │  │
│   │  - Logged into Facebook, Instagram                        │  │
│   │  - Receives input from "Logitech" USB devices             │  │
│   │  - NO automation detection possible                       │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  C:\PostQueue\ (shared/accessible from Ubuntu)            │  │
│   │  ├── pending\        ← Fetcher writes, Poster reads       │  │
│   │  ├── in_progress\    ← Poster moves jobs here             │  │
│   │  ├── completed\      ← Success                            │  │
│   │  └── failed\         ← Failures                           │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │  VIRTUAL HID DEVICE (appears as Logitech hardware)        │  │
│   │  - Vendor ID: 0x046D (Logitech)                           │  │
│   │  - Product ID: 0xC52B (Unifying Receiver)                 │  │
│   │  - Windows sees genuine USB input                         │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Architecture Components

### 1. Screen Capture (VNC)

Ubuntu captures the Windows 10 desktop via VNC. This gives us a live view of what Chrome is displaying.

```python
# Using vncdotool or similar
from vncdotool import api

client = api.connect('windows10-vm:5900', password='vnc-password')
screenshot = client.capture()  # PIL Image
```

### 2. Vision Analysis (Qwen2.5-VL)

The screenshot is analyzed by a local vision model to understand:
- What's currently on screen
- Where UI elements are located
- Whether actions succeeded

```python
# Using Ollama with Qwen2.5-VL
import ollama

response = ollama.chat(
    model='qwen2.5vl:7b',
    messages=[{
        'role': 'user',
        'content': 'What Facebook page is open? Where is the "Create Post" button?',
        'images': ['screenshot.png']
    }]
)
```

### 3. HID Input (Virtual USB)

Mouse and keyboard commands are sent via virtual HID devices that appear as genuine Logitech hardware to Windows.

```python
# Conceptual - actual implementation depends on your HID setup
class VirtualHID:
    def move_mouse(self, x, y, duration=0.5):
        """Move mouse with human-like curve"""
        # Bezier curve interpolation
        # Fitts's Law timing
        pass
    
    def click(self, x, y):
        """Click with natural timing"""
        pass
    
    def type_text(self, text, wpm=60):
        """Type with human-like rhythm"""
        pass
```

### 4. Behavioral Biometrics

All input mimics human patterns:
- Mouse movements follow Bezier curves
- Click timing varies naturally
- Typing speed matches your personal WPM
- Micro-pauses between actions

---

## Installation (Ubuntu)

### Prerequisites

```bash
# System packages
sudo apt update
sudo apt install -y python3-pip python3-venv vnc-client

# Create project directory
mkdir -p ~/social-poster
cd ~/social-poster

# Virtual environment
python3 -m venv venv
source venv/bin/activate
```

### Dependencies

Create `requirements.txt`:

```text
# Vision and LLM
ollama>=0.1.0

# VNC screen capture
vncdotool>=1.0.0
Pillow>=10.0.0

# API communication
requests>=2.31.0
aiohttp>=3.9.0

# Async support
asyncio>=3.4.3

# Configuration
python-dotenv>=1.0.0

# Image processing
numpy>=1.24.0
opencv-python>=4.8.0
```

```bash
pip install -r requirements.txt
```

### Configuration

Create `.env`:

```env
# Windows 10 VNC
VNC_HOST=192.168.1.100
VNC_PORT=5900
VNC_PASSWORD=your-vnc-password

# Job queue access (SMB share or network path)
QUEUE_PATH=/mnt/windows-share/PostQueue
# Or if using SSH/SFTP:
# QUEUE_HOST=192.168.1.100
# QUEUE_USER=sterling
# QUEUE_PATH=/c/PostQueue

# Social Dashboard API (for reporting results)
DASHBOARD_URL=https://social.sterlingcooley.com
API_KEY=your-api-key

# Ollama (vision model)
OLLAMA_HOST=http://localhost:11434

# Timing (milliseconds)
ACTION_DELAY_MIN=500
ACTION_DELAY_MAX=1500
TYPING_WPM=65
```

---

## Poster Implementation

Create `poster.py`:

```python
"""
Social Media Poster - Ubuntu Computer-Use Agent

Controls Windows 10 via VNC (screen) and virtual HID (input)
to post content to Facebook, Instagram, etc.

NO automation libraries touch the Windows browser.
All input appears as genuine Logitech USB hardware.
"""
import os
import sys
import json
import time
import random
import logging
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from io import BytesIO

import requests
import numpy as np
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

VNC_HOST = os.getenv('VNC_HOST', '192.168.1.100')
VNC_PORT = int(os.getenv('VNC_PORT', '5900'))
VNC_PASSWORD = os.getenv('VNC_PASSWORD', '')

QUEUE_PATH = Path(os.getenv('QUEUE_PATH', '/mnt/windows-share/PostQueue'))
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://social.sterlingcooley.com')
API_KEY = os.getenv('API_KEY', '')

OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
VISION_MODEL = os.getenv('VISION_MODEL', 'qwen2.5vl:7b')

ACTION_DELAY_MIN = int(os.getenv('ACTION_DELAY_MIN', '500'))
ACTION_DELAY_MAX = int(os.getenv('ACTION_DELAY_MAX', '1500'))
TYPING_WPM = int(os.getenv('TYPING_WPM', '65'))

# =============================================================================
# LOGGING
# =============================================================================

LOG_DIR = Path('~/social-poster/logs').expanduser()
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / 'poster.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('poster')

# =============================================================================
# SCREEN CAPTURE (VNC)
# =============================================================================

class ScreenCapture:
    """Captures Windows 10 screen via VNC."""
    
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
    
    def connect(self):
        """Establish VNC connection."""
        try:
            from vncdotool import api
            self.client = api.connect(f'{self.host}:{self.port}', password=self.password)
            logger.info(f"VNC connected to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
            raise
    
    def capture(self) -> Image.Image:
        """Capture current screen."""
        if not self.client:
            self.connect()
        return self.client.capture()
    
    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """Capture a specific region."""
        full = self.capture()
        return full.crop((x, y, x + width, y + height))
    
    def save_screenshot(self, path: Path) -> Path:
        """Save screenshot to file."""
        img = self.capture()
        img.save(path)
        return path

# =============================================================================
# VISION ANALYSIS (Qwen2.5-VL via Ollama)
# =============================================================================

class VisionAgent:
    """Analyzes screenshots using vision language model."""
    
    def __init__(self, model: str = VISION_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.host = host
    
    def analyze(self, image: Image.Image, query: str) -> str:
        """
        Analyze image with a query.
        
        Args:
            image: PIL Image to analyze
            query: Question about the image
            
        Returns:
            Model's response
        """
        # Convert image to base64
        import base64
        buffer = BytesIO()
        image.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Call Ollama API
        response = requests.post(
            f"{self.host}/api/chat",
            json={
                'model': self.model,
                'messages': [{
                    'role': 'user',
                    'content': query,
                    'images': [img_base64]
                }],
                'stream': False
            },
            timeout=60
        )
        
        if response.ok:
            return response.json()['message']['content']
        else:
            raise Exception(f"Vision API error: {response.status_code}")
    
    def find_element(self, image: Image.Image, element_description: str) -> Optional[Tuple[int, int]]:
        """
        Find UI element coordinates.
        
        Args:
            image: Screenshot
            element_description: What to find (e.g., "Create Post button")
            
        Returns:
            (x, y) coordinates or None
        """
        query = f"""Look at this screenshot and find the {element_description}.
        
Return ONLY the pixel coordinates as: x,y
For example: 450,320

If you cannot find it, respond with: NOT_FOUND"""
        
        response = self.analyze(image, query)
        
        if 'NOT_FOUND' in response:
            return None
        
        try:
            # Parse coordinates from response
            # Handle various formats: "450,320" or "x=450, y=320" etc.
            import re
            numbers = re.findall(r'\d+', response)
            if len(numbers) >= 2:
                return int(numbers[0]), int(numbers[1])
        except Exception:
            pass
        
        return None
    
    def read_text(self, image: Image.Image, region_description: str = None) -> str:
        """Extract text from image."""
        query = "Extract all readable text from this image."
        if region_description:
            query = f"Extract the text from the {region_description} in this image."
        
        return self.analyze(image, query)
    
    def check_success(self, image: Image.Image, expected_outcome: str) -> bool:
        """
        Verify if an action succeeded.
        
        Args:
            image: Screenshot after action
            expected_outcome: What success looks like
            
        Returns:
            True if success detected
        """
        query = f"""Look at this screenshot and determine if this action succeeded:
Expected outcome: {expected_outcome}

Respond with ONLY: SUCCESS or FAILURE"""
        
        response = self.analyze(image, query)
        return 'SUCCESS' in response.upper()

# =============================================================================
# HID INPUT (Virtual USB Mouse/Keyboard)
# =============================================================================

class HIDController:
    """
    Controls virtual HID devices that appear as Logitech hardware.
    
    This is a placeholder - actual implementation depends on your
    virtual HID setup (USB/IP, VHCI, custom driver, etc.)
    """
    
    def __init__(self):
        self.screen_width = 1920
        self.screen_height = 1080
        self.current_x = self.screen_width // 2
        self.current_y = self.screen_height // 2
    
    def _human_delay(self):
        """Random delay to simulate human timing."""
        delay = random.uniform(ACTION_DELAY_MIN, ACTION_DELAY_MAX) / 1000
        time.sleep(delay)
    
    def _bezier_points(self, start: Tuple[int, int], end: Tuple[int, int], 
                       num_points: int = 50) -> List[Tuple[int, int]]:
        """Generate human-like mouse path using Bezier curve."""
        x0, y0 = start
        x3, y3 = end
        
        # Random control points for natural curve
        x1 = x0 + random.randint(-100, 100)
        y1 = y0 + random.randint(-100, 100)
        x2 = x3 + random.randint(-100, 100)
        y2 = y3 + random.randint(-100, 100)
        
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            
            # Cubic Bezier formula
            x = (1-t)**3 * x0 + 3*(1-t)**2*t * x1 + 3*(1-t)*t**2 * x2 + t**3 * x3
            y = (1-t)**3 * y0 + 3*(1-t)**2*t * y1 + 3*(1-t)*t**2 * y2 + t**3 * y3
            
            points.append((int(x), int(y)))
        
        return points
    
    def move_mouse(self, x: int, y: int):
        """
        Move mouse to coordinates with human-like motion.
        
        TODO: Replace with actual HID device communication
        """
        logger.debug(f"Moving mouse to ({x}, {y})")
        
        # Generate path
        path = self._bezier_points((self.current_x, self.current_y), (x, y))
        
        # Move along path with varying speed
        for px, py in path:
            # TODO: Send actual HID mouse movement
            # self.hid_device.send_mouse_move(px - self.current_x, py - self.current_y)
            self.current_x, self.current_y = px, py
            time.sleep(random.uniform(0.005, 0.015))
        
        self.current_x, self.current_y = x, y
    
    def click(self, x: int = None, y: int = None, button: str = 'left'):
        """
        Click at coordinates.
        
        TODO: Replace with actual HID device communication
        """
        if x is not None and y is not None:
            self.move_mouse(x, y)
        
        self._human_delay()
        
        logger.debug(f"Clicking {button} at ({self.current_x}, {self.current_y})")
        
        # TODO: Send actual HID click
        # self.hid_device.send_click(button)
        
        # Human-like click duration
        time.sleep(random.uniform(0.05, 0.15))
    
    def double_click(self, x: int = None, y: int = None):
        """Double click."""
        if x is not None and y is not None:
            self.move_mouse(x, y)
        
        self.click()
        time.sleep(random.uniform(0.05, 0.1))
        self.click()
    
    def type_text(self, text: str):
        """
        Type text with human-like timing.
        
        TODO: Replace with actual HID device communication
        """
        logger.debug(f"Typing: {text[:50]}...")
        
        # Calculate delay per character based on WPM
        # Average word = 5 characters
        chars_per_minute = TYPING_WPM * 5
        base_delay = 60 / chars_per_minute
        
        for char in text:
            # TODO: Send actual HID keypress
            # self.hid_device.send_key(char)
            
            # Variable delay for natural typing
            delay = base_delay * random.uniform(0.5, 1.5)
            
            # Longer pauses after punctuation
            if char in '.!?,;:':
                delay *= 2
            
            time.sleep(delay)
    
    def press_key(self, key: str):
        """
        Press a special key.
        
        TODO: Replace with actual HID device communication
        """
        logger.debug(f"Pressing key: {key}")
        # TODO: self.hid_device.send_key(key)
        self._human_delay()
    
    def hotkey(self, *keys):
        """
        Press key combination (e.g., Ctrl+V).
        
        TODO: Replace with actual HID device communication
        """
        logger.debug(f"Hotkey: {'+'.join(keys)}")
        # TODO: self.hid_device.send_hotkey(*keys)
        self._human_delay()

# =============================================================================
# JOB QUEUE MANAGEMENT
# =============================================================================

class JobQueue:
    """Manages the PostQueue shared folder."""
    
    def __init__(self, queue_path: Path):
        self.queue_path = queue_path
        self.pending_dir = queue_path / 'pending'
        self.in_progress_dir = queue_path / 'in_progress'
        self.completed_dir = queue_path / 'completed'
        self.failed_dir = queue_path / 'failed'
    
    def get_pending_jobs(self) -> List[Dict[str, Any]]:
        """Get list of pending jobs."""
        jobs = []
        
        if not self.pending_dir.exists():
            logger.warning(f"Pending directory not found: {self.pending_dir}")
            return jobs
        
        for job_dir in self.pending_dir.iterdir():
            if not job_dir.is_dir():
                continue
            
            job_file = job_dir / 'job.json'
            if not job_file.exists():
                continue
            
            try:
                with open(job_file, encoding='utf-8') as f:
                    job = json.load(f)
                job['job_dir'] = job_dir
                jobs.append(job)
            except Exception as e:
                logger.error(f"Failed to read job: {e}")
        
        return sorted(jobs, key=lambda x: x.get('scheduled_time', ''))
    
    def claim_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Move job to in_progress."""
        import shutil
        
        src = job['job_dir']
        dst = self.in_progress_dir / src.name
        
        self.in_progress_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        job['job_dir'] = dst
        
        self._update_status(job, 'in_progress')
        return job
    
    def complete_job(self, job: Dict[str, Any], success: bool, error: str = None):
        """Move job to completed or failed."""
        import shutil
        
        src = job['job_dir']
        dst_dir = self.completed_dir if success else self.failed_dir
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name
        
        shutil.move(str(src), str(dst))
        job['job_dir'] = dst
        
        status = 'completed' if success else 'failed'
        self._update_status(job, status, error)
    
    def _update_status(self, job: Dict[str, Any], status: str, error: str = None):
        """Update job.json with new status."""
        job_file = job['job_dir'] / 'job.json'
        
        try:
            with open(job_file, encoding='utf-8') as f:
                data = json.load(f)
            
            data['status'] = status
            data['updated_at'] = datetime.now().isoformat()
            if error:
                data['error'] = error
            if status in ('completed', 'failed'):
                data['finished_at'] = datetime.now().isoformat()
            
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")

# =============================================================================
# PLATFORM PLAYBOOKS
# =============================================================================

class SocialPoster:
    """
    Executes social media posting using vision + HID control.
    """
    
    def __init__(self):
        self.screen = ScreenCapture(VNC_HOST, VNC_PORT, VNC_PASSWORD)
        self.vision = VisionAgent()
        self.hid = HIDController()
        self.queue = JobQueue(QUEUE_PATH)
    
    def _wait_and_capture(self, delay: float = 2.0) -> Image.Image:
        """Wait for screen to update, then capture."""
        time.sleep(delay)
        return self.screen.capture()
    
    def _find_and_click(self, description: str, timeout: int = 10) -> bool:
        """Find element and click it."""
        start = time.time()
        
        while time.time() - start < timeout:
            screenshot = self.screen.capture()
            coords = self.vision.find_element(screenshot, description)
            
            if coords:
                x, y = coords
                logger.info(f"Found '{description}' at ({x}, {y})")
                self.hid.click(x, y)
                return True
            
            time.sleep(1)
        
        logger.warning(f"Could not find: {description}")
        return False
    
    async def post_to_facebook(self, job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Post to Facebook using vision-guided HID control.
        
        Steps:
        1. Ensure Chrome is open to Facebook
        2. Navigate to page/profile
        3. Click "Create Post"
        4. Upload image (if any)
        5. Type caption
        6. Click Post
        7. Verify success
        """
        logger.info(f"[Facebook] Starting post: {job.get('id')}")
        
        try:
            # Step 1: Open Chrome and go to Facebook (if not already there)
            screenshot = self._wait_and_capture(1)
            page_text = self.vision.read_text(screenshot)
            
            if 'facebook' not in page_text.lower():
                # Need to navigate to Facebook
                # Click address bar, type URL, press Enter
                self.hid.hotkey('ctrl', 'l')  # Focus address bar
                time.sleep(0.5)
                self.hid.type_text('https://www.facebook.com')
                self.hid.press_key('enter')
                self._wait_and_capture(3)
            
            # Step 2: Find and click "Create Post" or "What's on your mind?"
            if not self._find_and_click("Create post button or 'What's on your mind' text box"):
                return False, "Could not find Create Post"
            
            self._wait_and_capture(2)
            
            # Step 3: Upload image if present
            if job.get('media'):
                media_path = job['job_dir'] / job['media'][0]['local_path']
                
                # Find and click "Photo/Video" button
                if self._find_and_click("Photo/Video button or camera icon"):
                    self._wait_and_capture(2)
                    
                    # File dialog should open - type path
                    # This assumes Windows file dialog is open
                    self.hid.type_text(str(media_path))
                    self.hid.press_key('enter')
                    self._wait_and_capture(5)  # Wait for upload
            
            # Step 4: Type caption
            caption = job.get('caption', '')
            if job.get('link'):
                caption += f"\n\n{job['link']}"
            
            # Click in the text area and type
            if self._find_and_click("post text area or 'What's on your mind'"):
                self.hid.type_text(caption)
                self._wait_and_capture(1)
            
            # Step 5: Click Post button
            if not self._find_and_click("Post button"):
                return False, "Could not find Post button"
            
            # Step 6: Wait and verify
            screenshot = self._wait_and_capture(5)
            
            # Save screenshot for verification
            screenshot.save(job['job_dir'] / 'result.png')
            
            # Check for success
            if self.vision.check_success(screenshot, "Post was published successfully"):
                logger.info("[Facebook] Post published successfully")
                return True, None
            else:
                return False, "Could not verify post success"
            
        except Exception as e:
            logger.exception(f"[Facebook] Error: {e}")
            return False, str(e)
    
    async def post_to_instagram(self, job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Post to Instagram via Creator Studio.
        
        Instagram requires an image, so we use Creator Studio which
        allows posting from desktop.
        """
        logger.info(f"[Instagram] Starting post: {job.get('id')}")
        
        if not job.get('media'):
            return False, "Instagram requires an image"
        
        try:
            # Navigate to Creator Studio
            self.hid.hotkey('ctrl', 'l')
            time.sleep(0.5)
            self.hid.type_text('https://business.facebook.com/creatorstudio')
            self.hid.press_key('enter')
            self._wait_and_capture(5)
            
            # Click Instagram icon/tab
            if not self._find_and_click("Instagram icon or tab"):
                return False, "Could not find Instagram in Creator Studio"
            
            self._wait_and_capture(2)
            
            # Click Create Post
            if not self._find_and_click("Create Post button"):
                return False, "Could not find Create Post"
            
            self._wait_and_capture(2)
            
            # Select Instagram Feed
            if not self._find_and_click("Instagram Feed option"):
                pass  # May already be selected
            
            self._wait_and_capture(2)
            
            # Upload image
            media_path = job['job_dir'] / job['media'][0]['local_path']
            
            if self._find_and_click("Add Content button or upload area"):
                self._wait_and_capture(1)
                self.hid.type_text(str(media_path))
                self.hid.press_key('enter')
                self._wait_and_capture(5)
            
            # Type caption
            if self._find_and_click("Caption text area"):
                self.hid.type_text(job.get('caption', ''))
                self._wait_and_capture(1)
            
            # Click Publish
            if not self._find_and_click("Publish button"):
                return False, "Could not find Publish button"
            
            # Verify
            screenshot = self._wait_and_capture(5)
            screenshot.save(job['job_dir'] / 'result.png')
            
            if self.vision.check_success(screenshot, "Post was published to Instagram"):
                logger.info("[Instagram] Post published successfully")
                return True, None
            
            return False, "Could not verify success"
            
        except Exception as e:
            logger.exception(f"[Instagram] Error: {e}")
            return False, str(e)
    
    async def execute_job(self, job: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Route to appropriate platform handler."""
        platform = job.get('platform', '').lower()
        
        if platform == 'facebook':
            return await self.post_to_facebook(job)
        elif platform == 'instagram':
            return await self.post_to_instagram(job)
        else:
            return False, f"Unsupported platform: {platform}"
    
    def report_to_dashboard(self, post_id: str, success: bool, error: str = None):
        """Report result to Social Dashboard API."""
        if not API_KEY:
            return
        
        endpoint = '/api/queue/gui/complete' if success else '/api/queue/gui/failed'
        
        try:
            response = requests.post(
                f"{DASHBOARD_URL}{endpoint}",
                headers={'X-API-Key': API_KEY},
                json={'id': post_id, 'error': error},
                timeout=30
            )
            logger.info(f"Reported to dashboard: {response.status_code}")
        except Exception as e:
            logger.error(f"Dashboard report failed: {e}")
    
    async def run_once(self) -> int:
        """Process pending jobs once."""
        jobs = self.queue.get_pending_jobs()
        
        if not jobs:
            logger.debug("No pending jobs")
            return 0
        
        logger.info(f"Found {len(jobs)} pending job(s)")
        processed = 0
        
        for job in jobs:
            try:
                job = self.queue.claim_job(job)
                logger.info(f"Processing: {job.get('job_id')} ({job.get('platform')})")
                
                success, error = await self.execute_job(job)
                self.queue.complete_job(job, success, error)
                self.report_to_dashboard(job['id'], success, error)
                
                if success:
                    logger.info(f"✓ Posted: {job.get('job_id')}")
                else:
                    logger.error(f"✗ Failed: {job.get('job_id')} - {error}")
                
                processed += 1
                
                # Delay between posts
                await asyncio.sleep(random.uniform(30, 60))
                
            except Exception as e:
                logger.exception(f"Job error: {e}")
        
        return processed
    
    async def run_forever(self, interval: int = 60):
        """Continuously process jobs."""
        logger.info(f"Starting poster loop (checking every {interval}s)")
        
        try:
            while True:
                await self.run_once()
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Stopped by user")

# =============================================================================
# ENTRY POINT
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(description='Social Media Poster - Ubuntu Agent')
    parser.add_argument('--once', action='store_true', help='Process jobs once and exit')
    parser.add_argument('--test-vnc', action='store_true', help='Test VNC connection')
    parser.add_argument('--test-vision', action='store_true', help='Test vision model')
    args = parser.parse_args()
    
    if args.test_vnc:
        print("Testing VNC connection...")
        screen = ScreenCapture(VNC_HOST, VNC_PORT, VNC_PASSWORD)
        screen.connect()
        img = screen.capture()
        img.save('/tmp/vnc_test.png')
        print(f"✓ Screenshot saved to /tmp/vnc_test.png ({img.size})")
        return
    
    if args.test_vision:
        print("Testing vision model...")
        vision = VisionAgent()
        img = Image.new('RGB', (100, 100), color='red')
        result = vision.analyze(img, "What color is this image?")
        print(f"✓ Vision response: {result}")
        return
    
    poster = SocialPoster()
    
    if args.once:
        count = await poster.run_once()
        print(f"Processed {count} job(s)")
    else:
        await poster.run_forever()


if __name__ == '__main__':
    asyncio.run(main())
```

---

## Setup: VNC Access to Windows 10

### On Windows 10

Install a VNC server:
```powershell
# TightVNC is a good option
choco install tightvnc -y
```

Or use the built-in Windows Remote Desktop and a VNC bridge.

### On Ubuntu

Test VNC connection:
```bash
cd ~/social-poster
source venv/bin/activate
python poster.py --test-vnc
# Should save screenshot to /tmp/vnc_test.png
```

---

## Setup: Shared Folder Access

The Ubuntu machine needs access to `C:\PostQueue` on Windows 10.

### Option 1: SMB Share

On Windows 10:
1. Right-click `C:\PostQueue` → Properties → Sharing
2. Share with appropriate permissions

On Ubuntu:
```bash
# Mount the share
sudo mkdir -p /mnt/windows-share
sudo mount -t cifs //192.168.1.100/PostQueue /mnt/windows-share -o username=sterling,password=xxx

# Add to /etc/fstab for persistent mount
# //192.168.1.100/PostQueue /mnt/windows-share cifs credentials=/etc/samba/credentials,uid=1000 0 0
```

### Option 2: SSH/SFTP

If Windows has OpenSSH server enabled, use sshfs:
```bash
sshfs sterling@192.168.1.100:/c/PostQueue /mnt/windows-share
```

---

## Setup: Virtual HID Devices

The HIDController class is a placeholder. You need to implement actual HID communication based on your setup:

### Option A: USB/IP

If using USB/IP to share virtual USB devices:
```python
# Example using python-usbip or similar
class HIDController:
    def __init__(self):
        self.device = USBIPDevice(
            vendor_id=0x046D,   # Logitech
            product_id=0xC52B,  # Unifying Receiver
        )
```

### Option B: Proxmox VHCI

If using Proxmox's virtual HID:
```python
# Send HID reports through Proxmox API or QEMU monitor
```

### Option C: Network HID Bridge

Custom solution that receives commands and injects them into Windows:
```python
# Send commands to a small service on Windows that uses SendInput()
```

---

## Usage

### Test Components

```bash
cd ~/social-poster
source venv/bin/activate

# Test VNC
python poster.py --test-vnc

# Test vision model
python poster.py --test-vision
```

### Process Jobs Once

```bash
python poster.py --once
```

### Run Continuously

```bash
python poster.py
# Or as a systemd service
```

### Install as Service

Create `/etc/systemd/system/social-poster.service`:

```ini
[Unit]
Description=Social Media Poster
After=network.target

[Service]
Type=simple
User=sterling
WorkingDirectory=/home/sterling/social-poster
ExecStart=/home/sterling/social-poster/venv/bin/python poster.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable social-poster
sudo systemctl start social-poster
```

---

## The Complete Flow

1. **You** create a post on social.sterlingcooley.com/social
2. **Fetcher** (Windows 10) polls the API, downloads the job to `C:\PostQueue\pending\`
3. **Poster** (Ubuntu) sees the new job via shared folder
4. **Poster** captures Windows screen via VNC
5. **Poster** uses vision model to understand what's on screen
6. **Poster** sends mouse/keyboard commands via virtual HID
7. **Windows** receives "Logitech" input, Chrome posts to Facebook/Instagram
8. **Poster** verifies success with vision, reports to dashboard
9. **Job** moves to `completed\` or `failed\`

---

## Key Differences from Playwright Approach

| Aspect | Playwright (Bad) | HID Control (Good) |
|--------|------------------|-------------------|
| Detection | Instantly detected | Undetectable |
| Browser | Automated Chromium | Real Chrome |
| Input | JS injection | USB HID signals |
| Fingerprint | Bot signatures | Human signatures |
| Sessions | Cookie export | Normal login |
| Rate limits | Aggressive | Normal user |