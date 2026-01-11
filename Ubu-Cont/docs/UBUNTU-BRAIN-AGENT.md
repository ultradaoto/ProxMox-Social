# UBUNTU-BRAIN-AGENT.md
# The Complete Ubuntu Orchestration System for Social Media Automation

## Overview

This document specifies the **Ubuntu Brain** - a Python-based orchestration system that:
1. Monitors the Social Dashboard API for pending posts
2. Connects to Windows 10 VM via VNC
3. Uses vision (Qwen2.5-VL) to navigate the UI
4. Sends input commands to Windows 10 via Proxmox QMP
5. Completes social media posts and reports success/failure

**This is the BRAIN. It makes ALL decisions. Windows 10 is just the hands.**

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           UBUNTU BRAIN AGENT                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                         MAIN ORCHESTRATOR                           │   │
│  │                                                                     │   │
│  │   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │   │
│  │   │   FETCHER    │   │   WORKFLOW   │   │   REPORTER   │           │   │
│  │   │   MODULE     │──▶│   ENGINE     │──▶│   MODULE     │           │   │
│  │   │              │   │              │   │              │           │   │
│  │   │ Polls API    │   │ Executes     │   │ Reports      │           │   │
│  │   │ Gets posts   │   │ steps        │   │ results      │           │   │
│  │   └──────────────┘   └──────────────┘   └──────────────┘           │   │
│  │                             │                                       │   │
│  │                             ▼                                       │   │
│  │   ┌─────────────────────────────────────────────────────────────┐   │   │
│  │   │                    SUBSYSTEMS                               │   │   │
│  │   │                                                             │   │   │
│  │   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │   │   │
│  │   │  │   VNC       │  │   VISION    │  │   INPUT     │         │   │   │
│  │   │  │   CAPTURE   │  │   ENGINE    │  │   INJECTOR  │         │   │   │
│  │   │  │             │  │             │  │             │         │   │   │
│  │   │  │ Screenshots │  │ Qwen2.5-VL  │  │ Mouse/KB    │         │   │   │
│  │   │  │ from Win10  │  │ Find coords │  │ to Win10    │         │   │   │
│  │   │  └─────────────┘  └─────────────┘  └─────────────┘         │   │   │
│  │   │                                                             │   │   │
│  │   └─────────────────────────────────────────────────────────────┘   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      PLATFORM WORKFLOWS                             │   │
│  │                                                                     │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │   │
│  │  │  SKOOL   │  │INSTAGRAM │  │ FACEBOOK │  │  TIKTOK  │            │   │
│  │  │ WORKFLOW │  │ WORKFLOW │  │ WORKFLOW │  │ WORKFLOW │            │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      UTILITY SUBROUTINES                            │   │
│  │                                                                     │   │
│  │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐        │   │
│  │  │ WINDOWS_LOGIN  │  │ BROWSER_FOCUS  │  │ ERROR_RECOVERY │        │   │
│  │  │ SUBROUTINE     │  │ SUBROUTINE     │  │ SUBROUTINE     │        │   │
│  │  └────────────────┘  └────────────────┘  └────────────────┘        │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ VNC / QMP
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           WINDOWS 10 VM                                     │
│                                                                             │
│   ┌─────────────────────────────────────┐  ┌─────────────────────────────┐  │
│   │         CHROME BROWSER              │  │      OSP PANEL              │  │
│   │                                     │  │                             │  │
│   │   Social media platform             │  │  [OPEN URL]                 │  │
│   │   (Skool, Instagram, etc.)          │  │  [COPY TITLE]               │  │
│   │                                     │  │  [COPY BODY]                │  │
│   │                                     │  │  [COPY IMAGE]               │  │
│   │                                     │  │  [POST]                     │  │
│   │                                     │  │  [SUCCESS] [FAILED]         │  │
│   └─────────────────────────────────────┘  └─────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
/home/ubuntu/social-brain/
├── main.py                      # Entry point - runs the brain
├── config/
│   ├── settings.yaml            # Configuration
│   ├── credentials.yaml         # Windows password, API keys (encrypted)
│   └── platforms.yaml           # Platform-specific settings
├── src/
│   ├── __init__.py
│   ├── fetcher.py               # API polling module
│   ├── orchestrator.py          # Main workflow engine
│   ├── reporter.py              # Success/failure reporting
│   ├── subsystems/
│   │   ├── __init__.py
│   │   ├── vnc_capture.py       # VNC screenshot capture
│   │   ├── vision_engine.py     # Qwen2.5-VL interface
│   │   └── input_injector.py    # Mouse/keyboard to Windows
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── base_workflow.py     # Base class for all workflows
│   │   ├── skool_workflow.py    # Skool-specific steps
│   │   ├── instagram_workflow.py
│   │   ├── facebook_workflow.py
│   │   └── tiktok_workflow.py
│   ├── subroutines/
│   │   ├── __init__.py
│   │   ├── windows_login.py     # Windows 10 login handler
│   │   ├── browser_focus.py     # Ensure Chrome is focused
│   │   └── error_recovery.py    # Handle unexpected states
│   └── utils/
│       ├── __init__.py
│       ├── logger.py            # Logging utilities
│       ├── screenshot_saver.py  # Save screenshots for debugging
│       └── retry_handler.py     # Retry logic
├── tests/
│   ├── test_vnc.py
│   ├── test_vision.py
│   ├── test_input.py
│   └── test_workflows.py
├── logs/
│   ├── brain.log
│   └── screenshots/             # Debug screenshots
└── requirements.txt
```

---

## Core Module Specifications

### 1. Configuration (`config/settings.yaml`)

```yaml
# Ubuntu Brain Configuration

api:
  base_url: "https://social.sterlingcooley.com/api"
  poll_interval_seconds: 30
  timeout_seconds: 10

windows_vm:
  vnc_host: "192.168.100.20"
  vnc_port: 5900
  vnc_password: "${VNC_PASSWORD}"  # From environment
  
proxmox:
  host: "192.168.100.1"
  input_api_port: 8888

vision:
  model: "qwen2.5vl:7b"
  ollama_host: "localhost"
  ollama_port: 11434
  timeout_seconds: 60

windows_credentials:
  username: "User"
  password: "${WINDOWS_PASSWORD}"  # From environment

workflow:
  screenshot_delay_ms: 500        # Wait after action before screenshot
  action_delay_ms: 300            # Wait between actions
  max_retries: 3                  # Retries per step
  step_timeout_seconds: 30        # Timeout per step

logging:
  level: "INFO"
  save_screenshots: true
  screenshot_dir: "logs/screenshots"
```

---

### 2. Main Entry Point (`main.py`)

```python
#!/usr/bin/env python3
"""
Ubuntu Brain Agent - Main Entry Point

This is the BRAIN that orchestrates all social media posting.
It runs continuously, polling for posts and executing workflows.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.orchestrator import BrainOrchestrator
from src.utils.logger import setup_logging, get_logger

logger = get_logger(__name__)


class UbuntuBrain:
    """Main brain controller."""
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = config_path
        self.orchestrator = None
        self.running = False
    
    async def start(self):
        """Start the brain."""
        logger.info("=" * 60)
        logger.info("UBUNTU BRAIN AGENT STARTING")
        logger.info("=" * 60)
        
        self.running = True
        
        # Initialize orchestrator
        self.orchestrator = BrainOrchestrator(self.config_path)
        await self.orchestrator.initialize()
        
        logger.info("Brain initialized successfully")
        logger.info("Beginning main loop...")
        
        # Main loop
        await self.orchestrator.run_forever()
    
    async def stop(self):
        """Stop the brain gracefully."""
        logger.info("Stopping Ubuntu Brain...")
        self.running = False
        
        if self.orchestrator:
            await self.orchestrator.shutdown()
        
        logger.info("Ubuntu Brain stopped")
    
    def handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self.running = False


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging()
    
    brain = UbuntuBrain()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, brain.handle_signal)
    signal.signal(signal.SIGTERM, brain.handle_signal)
    
    try:
        await brain.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
    finally:
        await brain.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

---

### 3. Fetcher Module (`src/fetcher.py`)

```python
"""
Fetcher Module - Polls API for pending posts.

This module is responsible for:
1. Polling the Social Dashboard API
2. Retrieving pending posts
3. Parsing post data into workflow-ready format
"""

import aiohttp
import asyncio
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class Platform(Enum):
    """Supported social media platforms."""
    SKOOL = "skool"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"


@dataclass
class PendingPost:
    """Represents a post to be made."""
    id: str
    platform: Platform
    url: str                          # Platform URL to open
    title: str                        # Post title
    body: str                         # Post body/content
    image_path: Optional[str]         # Path to image on Windows
    image_base64: Optional[str]       # Base64 image data
    send_email: bool                  # Whether to toggle email send
    hashtags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_api_response(cls, data: dict) -> "PendingPost":
        """Create PendingPost from API response."""
        return cls(
            id=data.get("id", ""),
            platform=Platform(data.get("platform", "skool").lower()),
            url=data.get("url", ""),
            title=data.get("title", ""),
            body=data.get("body", ""),
            image_path=data.get("image_path"),
            image_base64=data.get("image_base64"),
            send_email=data.get("send_email", False),
            hashtags=data.get("hashtags", []),
            metadata=data.get("metadata", {})
        )


class Fetcher:
    """Fetches pending posts from the Social Dashboard API."""
    
    def __init__(self, api_base_url: str, timeout: int = 10):
        """
        Initialize fetcher.
        
        Args:
            api_base_url: Base URL for Social Dashboard API
            timeout: Request timeout in seconds
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        logger.info(f"Fetcher initialized with API: {self.api_base_url}")
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    async def get_next_pending_post(self) -> Optional[PendingPost]:
        """
        Fetch the next pending post from the API.
        
        Returns:
            PendingPost if one is available, None otherwise
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/gui_post_queue/pending"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    if data and len(data) > 0:
                        post = PendingPost.from_api_response(data[0])
                        logger.info(f"Found pending post: {post.id} for {post.platform.value}")
                        return post
                    
                elif response.status != 404:
                    logger.warning(f"API returned status {response.status}")
                    
        except aiohttp.ClientError as e:
            logger.error(f"API connection error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error fetching post: {e}")
        
        return None
    
    async def get_all_pending_posts(self) -> List[PendingPost]:
        """
        Fetch all pending posts from the API.
        
        Returns:
            List of PendingPost objects
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/gui_post_queue/pending"
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return [PendingPost.from_api_response(p) for p in data]
                    
        except Exception as e:
            logger.exception(f"Error fetching all posts: {e}")
        
        return []
    
    async def mark_post_in_progress(self, post_id: str) -> bool:
        """
        Mark a post as being processed.
        
        Args:
            post_id: Post ID to mark
            
        Returns:
            True if successful
        """
        try:
            async with self.session.post(
                f"{self.api_base_url}/gui_post_queue/{post_id}/processing",
                json={"status": "processing"}
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Error marking post in progress: {e}")
            return False
    
    async def check_api_health(self) -> bool:
        """
        Check if API is reachable.
        
        Returns:
            True if API is healthy
        """
        try:
            async with self.session.get(
                f"{self.api_base_url}/health"
            ) as response:
                return response.status == 200
        except:
            return False
```

---

### 4. VNC Capture Subsystem (`src/subsystems/vnc_capture.py`)

```python
"""
VNC Capture Subsystem - Screenshots from Windows 10 VM.

This module captures screenshots from the Windows 10 VM via VNC.
These screenshots are used by the vision engine to find UI elements.
"""

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import io

from src.utils.logger import get_logger

logger = get_logger(__name__)


class VNCCapture:
    """Captures screenshots from Windows 10 VM via VNC."""
    
    def __init__(
        self,
        host: str = "192.168.100.20",
        port: int = 5900,
        password: Optional[str] = None
    ):
        """
        Initialize VNC capture.
        
        Args:
            host: Windows 10 VM IP address
            port: VNC port
            password: VNC password (if required)
        """
        self.host = host
        self.port = port
        self.password = password
        self.connected = False
        
        # Temp directory for screenshots
        self.temp_dir = Path(tempfile.gettempdir()) / "vnc_captures"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """
        Initialize VNC connection.
        
        Returns:
            True if connection successful
        """
        # Test connection with a capture
        try:
            screenshot = await self.capture()
            if screenshot:
                self.connected = True
                logger.info(f"VNC connected to {self.host}:{self.port}")
                return True
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
        
        return False
    
    async def capture(self) -> Optional[Image.Image]:
        """
        Capture current screen from Windows 10 VM.
        
        Returns:
            PIL Image of the screen, or None if capture failed
        """
        output_path = self.temp_dir / "current_screen.png"
        
        try:
            # Use vncsnapshot to capture screen
            # Alternative: use vncdotool or python-vnc library
            cmd = [
                "vncsnapshot",
                "-passwd", "/dev/stdin" if self.password else "",
                f"{self.host}:{self.port}",
                str(output_path)
            ]
            
            # Run vncsnapshot
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if self.password else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdin_data = self.password.encode() if self.password else None
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=stdin_data),
                timeout=10
            )
            
            if process.returncode == 0 and output_path.exists():
                image = Image.open(output_path)
                logger.debug(f"Captured screen: {image.size}")
                return image
            else:
                logger.error(f"vncsnapshot failed: {stderr.decode()}")
                
        except asyncio.TimeoutError:
            logger.error("VNC capture timed out")
        except FileNotFoundError:
            logger.error("vncsnapshot not found - install with: apt install vncsnapshot")
        except Exception as e:
            logger.exception(f"VNC capture error: {e}")
        
        return None
    
    async def capture_region(
        self,
        x: int,
        y: int,
        width: int,
        height: int
    ) -> Optional[Image.Image]:
        """
        Capture a specific region of the screen.
        
        Args:
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height
            
        Returns:
            PIL Image of the region
        """
        full_screen = await self.capture()
        if full_screen:
            return full_screen.crop((x, y, x + width, y + height))
        return None
    
    async def get_screen_size(self) -> Tuple[int, int]:
        """
        Get the screen dimensions.
        
        Returns:
            Tuple of (width, height)
        """
        screenshot = await self.capture()
        if screenshot:
            return screenshot.size
        return (1920, 1080)  # Default assumption
    
    def save_screenshot(self, image: Image.Image, name: str) -> Path:
        """
        Save screenshot for debugging.
        
        Args:
            image: PIL Image to save
            name: Filename (without extension)
            
        Returns:
            Path to saved file
        """
        save_path = self.temp_dir / f"{name}.png"
        image.save(save_path)
        return save_path


class VNCCaptureAlternative:
    """
    Alternative VNC capture using Python VNC library.
    Use this if vncsnapshot is not available.
    """
    
    def __init__(self, host: str, port: int, password: Optional[str] = None):
        self.host = host
        self.port = port
        self.password = password
        self.client = None
    
    async def initialize(self) -> bool:
        """Initialize VNC connection using vncdotool."""
        try:
            from vncdotool import api as vnc_api
            
            self.client = vnc_api.connect(
                f"{self.host}::{self.port}",
                password=self.password
            )
            return True
        except ImportError:
            logger.error("vncdotool not installed: pip install vncdotool")
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
        return False
    
    async def capture(self) -> Optional[Image.Image]:
        """Capture screen using vncdotool."""
        if not self.client:
            return None
        
        try:
            # Capture to bytes
            self.client.refreshScreen()
            return self.client.screen
        except Exception as e:
            logger.error(f"VNC capture failed: {e}")
            return None
```

---

### 5. Vision Engine Subsystem (`src/subsystems/vision_engine.py`)

```python
"""
Vision Engine Subsystem - Qwen2.5-VL interface for finding UI elements.

This is the "eyes" of the brain. It takes screenshots and answers questions like:
- "Where is the OPEN URL button?"
- "What are the coordinates of the green confirmation box?"
- "Do you see a login screen?"

It does NOT make decisions. It only reports what it sees and where things are.
"""

import asyncio
import json
import base64
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from PIL import Image
import aiohttp

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FoundElement:
    """Represents a UI element found by vision."""
    description: str          # What was found
    x: int                    # X coordinate (center)
    y: int                    # Y coordinate (center)
    confidence: float         # How confident (0-1)
    raw_response: str         # Raw model response for debugging


@dataclass
class ScreenState:
    """Represents the analyzed state of the screen."""
    description: str          # What the screen shows
    is_match: bool            # Does it match expected state
    details: Dict[str, Any]   # Additional details


class VisionEngine:
    """
    Vision engine using Qwen2.5-VL via Ollama.
    
    This is the EYES of the system. It answers questions about what's on screen.
    It does NOT make decisions about what to do next.
    """
    
    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        ollama_host: str = "localhost",
        ollama_port: int = 11434,
        timeout: int = 60
    ):
        """
        Initialize vision engine.
        
        Args:
            model: Ollama vision model name
            ollama_host: Ollama server host
            ollama_port: Ollama server port
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Temp directory for images
        self.temp_dir = Path(tempfile.gettempdir()) / "vision_engine"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """Initialize HTTP session and verify model is available."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Check if model is available
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
                    if any(self.model in m for m in models):
                        logger.info(f"Vision engine initialized with model: {self.model}")
                        return True
                    else:
                        logger.error(f"Model {self.model} not found. Available: {models}")
                        
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
        
        return False
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        import io
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    
    async def _query_vision(self, image: Image.Image, prompt: str) -> str:
        """
        Send query to vision model.
        
        Args:
            image: Screenshot to analyze
            prompt: Question to ask
            
        Returns:
            Model's response text
        """
        image_b64 = self._image_to_base64(image)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                else:
                    logger.error(f"Vision query failed: {response.status}")
                    return ""
                    
        except Exception as e:
            logger.exception(f"Vision query error: {e}")
            return ""
    
    # ==================== ELEMENT FINDING ====================
    
    async def find_element(
        self,
        screenshot: Image.Image,
        element_description: str
    ) -> Optional[FoundElement]:
        """
        Find a UI element on the screen.
        
        Args:
            screenshot: Current screen capture
            element_description: What to find, e.g., "OPEN URL button on the right side"
            
        Returns:
            FoundElement with coordinates, or None if not found
        """
        prompt = f"""Look at this screenshot carefully.

I need you to find: {element_description}

If you find it, respond with ONLY this JSON format (no other text):
{{"found": true, "x": <center_x_coordinate>, "y": <center_y_coordinate>, "confidence": <0.0-1.0>}}

The x,y coordinates should be the CENTER of the element, suitable for clicking.
Coordinates should be in pixels from the top-left corner.

If you cannot find it, respond with ONLY:
{{"found": false, "reason": "<brief explanation>"}}

IMPORTANT: Respond with ONLY the JSON, no additional text or explanation."""

        logger.debug(f"Vision query: Find '{element_description}'")
        
        response = await self._query_vision(screenshot, prompt)
        logger.debug(f"Vision response: {response}")
        
        try:
            # Parse JSON from response
            # Handle case where model adds extra text
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                
                if result.get("found"):
                    element = FoundElement(
                        description=element_description,
                        x=int(result["x"]),
                        y=int(result["y"]),
                        confidence=float(result.get("confidence", 0.8)),
                        raw_response=response
                    )
                    logger.info(f"Found element at ({element.x}, {element.y})")
                    return element
                else:
                    logger.warning(f"Element not found: {result.get('reason', 'unknown')}")
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vision response: {e}")
            logger.error(f"Raw response: {response}")
        
        return None
    
    async def find_button_by_text(
        self,
        screenshot: Image.Image,
        button_text: str,
        location_hint: str = ""
    ) -> Optional[FoundElement]:
        """
        Find a button with specific text.
        
        Args:
            screenshot: Current screen capture
            button_text: Text on the button
            location_hint: Where to look, e.g., "on the right side", "at the bottom"
            
        Returns:
            FoundElement with coordinates
        """
        description = f"button that says '{button_text}'"
        if location_hint:
            description += f" {location_hint}"
        
        return await self.find_element(screenshot, description)
    
    async def find_input_field(
        self,
        screenshot: Image.Image,
        field_description: str
    ) -> Optional[FoundElement]:
        """
        Find an input field or text area.
        
        Args:
            screenshot: Current screen capture
            field_description: Description of the field
            
        Returns:
            FoundElement with coordinates
        """
        return await self.find_element(
            screenshot,
            f"text input field or text area for {field_description}"
        )
    
    async def find_colored_element(
        self,
        screenshot: Image.Image,
        color: str,
        element_type: str,
        text_content: Optional[str] = None
    ) -> Optional[FoundElement]:
        """
        Find an element by color.
        
        Args:
            screenshot: Current screen capture
            color: Color of element (e.g., "green", "red", "orange")
            element_type: Type (e.g., "button", "box", "circle")
            text_content: Optional text in the element
            
        Returns:
            FoundElement with coordinates
        """
        description = f"{color} {element_type}"
        if text_content:
            description += f" that says '{text_content}'"
        
        return await self.find_element(screenshot, description)
    
    # ==================== STATE VERIFICATION ====================
    
    async def verify_screen_state(
        self,
        screenshot: Image.Image,
        expected_state: str
    ) -> ScreenState:
        """
        Verify the screen shows an expected state.
        
        Args:
            screenshot: Current screen capture
            expected_state: Description of expected state
            
        Returns:
            ScreenState with match result
        """
        prompt = f"""Look at this screenshot carefully.

Does this screen show: "{expected_state}"?

Respond with ONLY this JSON format (no other text):
{{"matches": true/false, "description": "<what you actually see>", "confidence": <0.0-1.0>}}

Be specific about what you see. Respond with ONLY the JSON."""

        logger.debug(f"Verifying state: '{expected_state}'")
        
        response = await self._query_vision(screenshot, prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                
                return ScreenState(
                    description=result.get("description", ""),
                    is_match=result.get("matches", False),
                    details={"confidence": result.get("confidence", 0.5)}
                )
                
        except json.JSONDecodeError:
            pass
        
        return ScreenState(
            description="Failed to parse response",
            is_match=False,
            details={"raw_response": response}
        )
    
    async def check_for_login_screen(self, screenshot: Image.Image) -> bool:
        """
        Check if Windows 10 is showing a login screen.
        
        Returns:
            True if login screen is visible
        """
        state = await self.verify_screen_state(
            screenshot,
            "Windows 10 login screen or lock screen with password field"
        )
        return state.is_match
    
    async def check_for_error_dialog(self, screenshot: Image.Image) -> Optional[str]:
        """
        Check if there's an error dialog on screen.
        
        Returns:
            Error message if found, None otherwise
        """
        prompt = """Look at this screenshot.

Is there any error dialog, error message, or warning popup visible?

Respond with ONLY this JSON format:
{"has_error": true/false, "error_message": "<the error text if visible>"}

Respond with ONLY the JSON."""

        response = await self._query_vision(screenshot, prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                
                if result.get("has_error"):
                    return result.get("error_message", "Unknown error")
                    
        except json.JSONDecodeError:
            pass
        
        return None
    
    async def check_for_confirmation(
        self,
        screenshot: Image.Image,
        confirmation_type: str = "success"
    ) -> bool:
        """
        Check for a confirmation message.
        
        Args:
            screenshot: Current screen capture
            confirmation_type: "success" or "failure"
            
        Returns:
            True if confirmation is visible
        """
        if confirmation_type == "success":
            state = await self.verify_screen_state(
                screenshot,
                "green success message, confirmation box, or 'post successful' notification"
            )
        else:
            state = await self.verify_screen_state(
                screenshot,
                "red error message, failure notification, or 'post failed' message"
            )
        
        return state.is_match
    
    # ==================== OSP-SPECIFIC QUERIES ====================
    
    async def find_osp_button(
        self,
        screenshot: Image.Image,
        button_name: str
    ) -> Optional[FoundElement]:
        """
        Find a button on the OSP panel (right side of screen).
        
        Args:
            screenshot: Current screen capture
            button_name: Button text (e.g., "OPEN URL", "COPY TITLE")
            
        Returns:
            FoundElement with coordinates
        """
        return await self.find_element(
            screenshot,
            f"button labeled '{button_name}' on the right side panel (OSP)"
        )
    
    async def check_osp_email_toggle(self, screenshot: Image.Image) -> bool:
        """
        Check if the OSP indicates email should be sent.
        
        Returns:
            True if email toggle is indicated/checked
        """
        prompt = """Look at the right side of this screenshot where the OSP panel is.

Is there an indication that an email should be sent? Look for:
- A checked checkbox for email
- Text indicating "send email" is enabled
- An active email toggle

Respond with ONLY: {"send_email": true/false}"""

        response = await self._query_vision(screenshot, prompt)
        
        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
                return result.get("send_email", False)
                
        except json.JSONDecodeError:
            pass
        
        return False
    
    # ==================== PLATFORM-SPECIFIC QUERIES ====================
    
    async def find_skool_new_post_button(
        self,
        screenshot: Image.Image
    ) -> Optional[FoundElement]:
        """Find the 'Start a post' or 'New post' button on Skool."""
        return await self.find_element(
            screenshot,
            "button or area to start a new post on Skool, might say 'Start a post' or have a plus icon or 'Create' button"
        )
    
    async def find_platform_post_button(
        self,
        screenshot: Image.Image,
        platform: str
    ) -> Optional[FoundElement]:
        """Find the final 'Post' or 'Share' button on a platform."""
        platform_hints = {
            "skool": "Post button or Submit button on Skool",
            "instagram": "Share button on Instagram post creation",
            "facebook": "Post button on Facebook",
            "tiktok": "Post button on TikTok"
        }
        
        hint = platform_hints.get(platform.lower(), "Post or Share button")
        return await self.find_element(screenshot, hint)
    
    async def find_paste_target(
        self,
        screenshot: Image.Image,
        target_type: str,
        visual_hint: str = ""
    ) -> Optional[FoundElement]:
        """
        Find where to paste content.
        
        Args:
            screenshot: Current screen capture
            target_type: "title", "body", or "image"
            visual_hint: Visual hint like "green box" or "red area"
            
        Returns:
            FoundElement with coordinates
        """
        descriptions = {
            "title": "area to paste the title, possibly a green highlighted box or input field labeled for title",
            "body": "area to paste body content or description, possibly a red highlighted box or larger text area",
            "image": "area to paste or upload an image, possibly highlighted or showing an upload zone"
        }
        
        description = descriptions.get(target_type, f"area to paste {target_type}")
        if visual_hint:
            description = f"{visual_hint} where I should {description}"
        
        return await self.find_element(screenshot, description)
```

---

### 6. Input Injector Subsystem (`src/subsystems/input_injector.py`)

```python
"""
Input Injector Subsystem - Send mouse/keyboard commands to Windows 10.

This module sends input commands to the Windows 10 VM via the Proxmox host.
The Proxmox host translates these commands to QMP for the VM.
"""

import asyncio
import aiohttp
from typing import Optional, List
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MouseButton(Enum):
    """Mouse button types."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class InputInjector:
    """
    Injects mouse and keyboard input into Windows 10 VM.
    
    Commands are sent to Proxmox host which translates them to QMP
    commands for the virtual HID device.
    """
    
    def __init__(
        self,
        proxmox_host: str = "192.168.100.1",
        api_port: int = 8888,
        timeout: int = 10
    ):
        """
        Initialize input injector.
        
        Args:
            proxmox_host: Proxmox host IP
            api_port: Port for input API
            timeout: Request timeout in seconds
        """
        self.base_url = f"http://{proxmox_host}:{api_port}"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Default delays for human-like behavior
        self.move_duration_ms = 300      # Mouse movement duration
        self.click_delay_ms = 50         # Delay before click
        self.type_delay_ms = 30          # Delay between keystrokes
        self.action_delay_ms = 200       # Delay after actions
    
    async def initialize(self) -> bool:
        """Initialize HTTP session and verify connection."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Test connection
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info(f"Input injector connected to {self.base_url}")
                    return True
        except Exception as e:
            logger.error(f"Failed to connect to input API: {e}")
        
        return False
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    async def _post(self, endpoint: str, data: dict) -> bool:
        """Send POST request to input API."""
        try:
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=data
            ) as response:
                success = response.status == 200
                if not success:
                    logger.warning(f"Input API returned {response.status} for {endpoint}")
                return success
        except Exception as e:
            logger.error(f"Input API error: {e}")
            return False
    
    # ==================== MOUSE OPERATIONS ====================
    
    async def move_mouse(
        self,
        x: int,
        y: int,
        duration_ms: Optional[int] = None
    ) -> bool:
        """
        Move mouse to absolute position.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration_ms: Movement duration (for human-like motion)
            
        Returns:
            True if successful
        """
        logger.debug(f"Moving mouse to ({x}, {y})")
        
        return await self._post("/mouse/move", {
            "x": x,
            "y": y,
            "duration": duration_ms or self.move_duration_ms
        })
    
    async def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT
    ) -> bool:
        """
        Click at position (or current position if x,y not specified).
        
        Args:
            x: Optional X coordinate
            y: Optional Y coordinate
            button: Mouse button to click
            
        Returns:
            True if successful
        """
        data = {"button": button.value}
        
        if x is not None and y is not None:
            data["x"] = x
            data["y"] = y
            logger.debug(f"Clicking at ({x}, {y}) with {button.value} button")
        else:
            logger.debug(f"Clicking at current position with {button.value} button")
        
        return await self._post("/mouse/click", data)
    
    async def click_at(self, x: int, y: int) -> bool:
        """
        Move to position and click.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        # Move first
        if not await self.move_mouse(x, y):
            return False
        
        # Small delay before click
        await asyncio.sleep(self.click_delay_ms / 1000)
        
        # Click
        return await self.click()
    
    async def double_click(self, x: int, y: int) -> bool:
        """
        Double-click at position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        logger.debug(f"Double-clicking at ({x}, {y})")
        
        return await self._post("/mouse/double_click", {
            "x": x,
            "y": y
        })
    
    async def right_click(self, x: int, y: int) -> bool:
        """Right-click at position."""
        return await self.click(x, y, MouseButton.RIGHT)
    
    async def scroll(
        self,
        direction: str = "down",
        amount: int = 3
    ) -> bool:
        """
        Scroll the page.
        
        Args:
            direction: "up" or "down"
            amount: Number of scroll units
            
        Returns:
            True if successful
        """
        logger.debug(f"Scrolling {direction} by {amount}")
        
        return await self._post("/mouse/scroll", {
            "direction": direction,
            "amount": amount
        })
    
    # ==================== KEYBOARD OPERATIONS ====================
    
    async def type_text(
        self,
        text: str,
        delay_ms: Optional[int] = None
    ) -> bool:
        """
        Type a string of text.
        
        Args:
            text: Text to type
            delay_ms: Delay between keystrokes
            
        Returns:
            True if successful
        """
        logger.debug(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        return await self._post("/keyboard/type", {
            "text": text,
            "delay": delay_ms or self.type_delay_ms
        })
    
    async def press_key(
        self,
        key: str,
        modifiers: Optional[List[str]] = None
    ) -> bool:
        """
        Press a single key with optional modifiers.
        
        Args:
            key: Key name (e.g., "enter", "tab", "a", "1")
            modifiers: List of modifiers ["ctrl", "shift", "alt"]
            
        Returns:
            True if successful
        """
        mod_str = "+".join(modifiers) + "+" if modifiers else ""
        logger.debug(f"Pressing key: {mod_str}{key}")
        
        return await self._post("/keyboard/press", {
            "key": key,
            "modifiers": modifiers or []
        })
    
    async def key_combo(self, *keys: str) -> bool:
        """
        Press a key combination.
        
        Args:
            *keys: Keys to press together (e.g., "ctrl", "v")
            
        Returns:
            True if successful
        """
        if len(keys) == 1:
            return await self.press_key(keys[0])
        
        modifiers = list(keys[:-1])
        key = keys[-1]
        return await self.press_key(key, modifiers)
    
    # ==================== COMMON OPERATIONS ====================
    
    async def paste(self) -> bool:
        """Send Ctrl+V to paste from clipboard."""
        logger.debug("Pasting (Ctrl+V)")
        return await self.key_combo("ctrl", "v")
    
    async def copy(self) -> bool:
        """Send Ctrl+C to copy to clipboard."""
        logger.debug("Copying (Ctrl+C)")
        return await self.key_combo("ctrl", "c")
    
    async def select_all(self) -> bool:
        """Send Ctrl+A to select all."""
        logger.debug("Select all (Ctrl+A)")
        return await self.key_combo("ctrl", "a")
    
    async def enter(self) -> bool:
        """Press Enter key."""
        return await self.press_key("enter")
    
    async def tab(self) -> bool:
        """Press Tab key."""
        return await self.press_key("tab")
    
    async def escape(self) -> bool:
        """Press Escape key."""
        return await self.press_key("escape")
    
    # ==================== COMPOUND OPERATIONS ====================
    
    async def click_and_type(self, x: int, y: int, text: str) -> bool:
        """
        Click at position and type text.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to type
            
        Returns:
            True if successful
        """
        if not await self.click_at(x, y):
            return False
        
        await asyncio.sleep(self.action_delay_ms / 1000)
        
        return await self.type_text(text)
    
    async def click_and_paste(self, x: int, y: int) -> bool:
        """
        Click at position and paste from clipboard.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        if not await self.click_at(x, y):
            return False
        
        await asyncio.sleep(self.action_delay_ms / 1000)
        
        return await self.paste()
    
    async def triple_click_select_all(self, x: int, y: int) -> bool:
        """
        Triple-click to select all text in a field.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        # Move to position
        if not await self.move_mouse(x, y):
            return False
        
        # Triple click (select all in text field)
        for _ in range(3):
            if not await self.click():
                return False
            await asyncio.sleep(0.05)
        
        return True
```

---

### 7. Windows Login Subroutine (`src/subroutines/windows_login.py`)

```python
"""
Windows Login Subroutine - Handles Windows 10 login screen.

This subroutine is called when the brain detects a Windows login screen.
It enters the password and waits for the desktop to appear.
"""

import asyncio
from typing import TYPE_CHECKING

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.subsystems.vnc_capture import VNCCapture
    from src.subsystems.vision_engine import VisionEngine
    from src.subsystems.input_injector import InputInjector

logger = get_logger(__name__)


class WindowsLoginSubroutine:
    """Handles Windows 10 login."""
    
    def __init__(
        self,
        vnc: "VNCCapture",
        vision: "VisionEngine",
        input_injector: "InputInjector",
        password: str
    ):
        """
        Initialize login subroutine.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
            password: Windows password
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        self.password = password
        
        self.max_attempts = 3
        self.timeout_seconds = 60
    
    async def execute(self) -> bool:
        """
        Execute Windows login.
        
        Returns:
            True if login successful
        """
        logger.info("Executing Windows login subroutine")
        
        for attempt in range(self.max_attempts):
            logger.info(f"Login attempt {attempt + 1}/{self.max_attempts}")
            
            try:
                # Step 1: Take screenshot
                screenshot = await self.vnc.capture()
                if not screenshot:
                    logger.error("Failed to capture screenshot")
                    continue
                
                # Step 2: Verify we're on login screen
                is_login = await self.vision.check_for_login_screen(screenshot)
                if not is_login:
                    logger.info("Not on login screen - may already be logged in")
                    return True
                
                # Step 3: Find password field
                password_field = await self.vision.find_element(
                    screenshot,
                    "password input field or text box on Windows login screen"
                )
                
                if not password_field:
                    # Try clicking anywhere to wake up the screen
                    logger.info("Password field not found, trying to wake screen")
                    await self.input.click_at(960, 540)  # Center of screen
                    await asyncio.sleep(1)
                    await self.input.press_key("space")
                    await asyncio.sleep(1)
                    continue
                
                # Step 4: Click password field
                logger.info(f"Clicking password field at ({password_field.x}, {password_field.y})")
                await self.input.click_at(password_field.x, password_field.y)
                await asyncio.sleep(0.5)
                
                # Step 5: Type password
                logger.info("Typing password")
                await self.input.type_text(self.password)
                await asyncio.sleep(0.3)
                
                # Step 6: Press Enter
                logger.info("Pressing Enter")
                await self.input.enter()
                
                # Step 7: Wait for desktop
                if await self._wait_for_desktop():
                    logger.info("Login successful!")
                    return True
                else:
                    logger.warning("Desktop did not appear after login")
                    
            except Exception as e:
                logger.exception(f"Login attempt failed: {e}")
            
            await asyncio.sleep(2)
        
        logger.error("All login attempts failed")
        return False
    
    async def _wait_for_desktop(self) -> bool:
        """Wait for Windows desktop to appear."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < self.timeout_seconds:
            await asyncio.sleep(2)
            
            screenshot = await self.vnc.capture()
            if not screenshot:
                continue
            
            # Check if we're past the login screen
            is_login = await self.vision.check_for_login_screen(screenshot)
            if not is_login:
                # Verify we see desktop elements
                state = await self.vision.verify_screen_state(
                    screenshot,
                    "Windows desktop with taskbar, or Chrome browser, or desktop icons"
                )
                
                if state.is_match:
                    return True
        
        return False
```

---

### 8. Reporter Module (`src/reporter.py`)

```python
"""
Reporter Module - Reports workflow results to the API.

This module handles all communication back to the Social Dashboard API
to report success, failure, and status updates.
"""

import asyncio
import aiohttp
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class PostStatus(Enum):
    """Post status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    POSTING = "posting"
    SUCCESS = "success"
    FAILED = "failed"


class Reporter:
    """Reports workflow results to the API."""
    
    def __init__(self, api_base_url: str, timeout: int = 10):
        """
        Initialize reporter.
        
        Args:
            api_base_url: Base URL for Social Dashboard API
            timeout: Request timeout in seconds
        """
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self):
        """Initialize HTTP session."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        logger.info("Reporter initialized")
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
    
    async def report_status(
        self,
        post_id: str,
        status: PostStatus,
        details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Report status update for a post.
        
        Args:
            post_id: Post ID
            status: New status
            details: Optional additional details
            
        Returns:
            True if report was accepted
        """
        endpoint_map = {
            PostStatus.PROCESSING: "processing",
            PostStatus.POSTING: "posting",
            PostStatus.SUCCESS: "complete",
            PostStatus.FAILED: "failed"
        }
        
        endpoint = endpoint_map.get(status)
        if not endpoint:
            logger.error(f"Unknown status: {status}")
            return False
        
        payload = {
            "status": status.value,
            "timestamp": datetime.now().isoformat()
        }
        
        if details:
            payload.update(details)
        
        try:
            async with self.session.post(
                f"{self.api_base_url}/gui_post_queue/{post_id}/{endpoint}",
                json=payload
            ) as response:
                
                success = response.status == 200
                if success:
                    logger.info(f"Reported {status.value} for post {post_id}")
                else:
                    logger.warning(f"Report failed: {response.status}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to report status: {e}")
            return False
    
    async def report_success(
        self,
        post_id: str,
        email_sent: bool = False,
        post_url: Optional[str] = None
    ) -> bool:
        """
        Report successful post.
        
        Args:
            post_id: Post ID
            email_sent: Whether email was toggled
            post_url: URL of the created post (if available)
            
        Returns:
            True if report was accepted
        """
        return await self.report_status(
            post_id,
            PostStatus.SUCCESS,
            {
                "email_sent": email_sent,
                "post_url": post_url,
                "completed_at": datetime.now().isoformat()
            }
        )
    
    async def report_failure(
        self,
        post_id: str,
        error_message: str,
        step: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> bool:
        """
        Report failed post.
        
        Args:
            post_id: Post ID
            error_message: Description of what failed
            step: Which step failed
            screenshot_path: Path to debug screenshot
            
        Returns:
            True if report was accepted
        """
        return await self.report_status(
            post_id,
            PostStatus.FAILED,
            {
                "error": error_message,
                "failed_step": step,
                "screenshot": screenshot_path,
                "failed_at": datetime.now().isoformat()
            }
        )
    
    async def report_processing(self, post_id: str) -> bool:
        """Mark post as being processed."""
        return await self.report_status(post_id, PostStatus.PROCESSING)
    
    async def report_posting(self, post_id: str) -> bool:
        """Mark post as in the posting phase."""
        return await self.report_status(post_id, PostStatus.POSTING)
```

---

### 9. Base Workflow (`src/workflows/base_workflow.py`)

```python
"""
Base Workflow - Abstract base class for all platform workflows.

All platform-specific workflows inherit from this class.
It provides the common structure and helper methods.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
from PIL import Image

from src.fetcher import PendingPost
from src.subsystems.vnc_capture import VNCCapture
from src.subsystems.vision_engine import VisionEngine, FoundElement
from src.subsystems.input_injector import InputInjector
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StepStatus(Enum):
    """Status of a workflow step."""
    PENDING = auto()
    IN_PROGRESS = auto()
    SUCCESS = auto()
    FAILED = auto()
    SKIPPED = auto()


@dataclass
class StepResult:
    """Result of executing a workflow step."""
    status: StepStatus
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    screenshot_path: Optional[str] = None


@dataclass
class WorkflowResult:
    """Final result of workflow execution."""
    success: bool
    post_id: str
    platform: str
    steps_completed: int
    total_steps: int
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    duration_seconds: float = 0.0


class BaseWorkflow(ABC):
    """
    Base class for platform-specific workflows.
    
    Each workflow is a sequence of steps that:
    1. Take a screenshot
    2. Ask vision where to click
    3. Send the click command
    4. Verify the result
    """
    
    def __init__(
        self,
        vnc: VNCCapture,
        vision: VisionEngine,
        input_injector: InputInjector
    ):
        """
        Initialize workflow.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        
        # Configuration
        self.screenshot_delay = 0.5      # Seconds to wait after action before screenshot
        self.action_delay = 0.3          # Seconds between actions
        self.max_retries = 3             # Retries per step
        self.step_timeout = 30           # Seconds timeout per step
        
        # State
        self.current_post: Optional[PendingPost] = None
        self.current_step: int = 0
        self.screenshots_dir: Optional[str] = None
    
    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name."""
        pass
    
    @property
    @abstractmethod
    def steps(self) -> List[str]:
        """Return list of step names in order."""
        pass
    
    # ==================== CORE EXECUTION ====================
    
    async def execute(self, post: PendingPost) -> WorkflowResult:
        """
        Execute the full workflow for a post.
        
        Args:
            post: Post data to process
            
        Returns:
            WorkflowResult with success/failure details
        """
        self.current_post = post
        self.current_step = 0
        start_time = datetime.now()
        
        logger.info(f"{'='*60}")
        logger.info(f"Starting {self.platform_name} workflow for post {post.id}")
        logger.info(f"{'='*60}")
        
        try:
            # Execute each step
            for i, step_name in enumerate(self.steps):
                self.current_step = i
                logger.info(f"Step {i+1}/{len(self.steps)}: {step_name}")
                
                result = await self._execute_step_with_retry(step_name)
                
                if result.status == StepStatus.FAILED:
                    duration = (datetime.now() - start_time).total_seconds()
                    return WorkflowResult(
                        success=False,
                        post_id=post.id,
                        platform=self.platform_name,
                        steps_completed=i,
                        total_steps=len(self.steps),
                        error_message=result.message,
                        error_step=step_name,
                        duration_seconds=duration
                    )
                
                # Brief pause between steps
                await asyncio.sleep(self.action_delay)
            
            # All steps completed
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Workflow completed successfully in {duration:.1f}s")
            
            return WorkflowResult(
                success=True,
                post_id=post.id,
                platform=self.platform_name,
                steps_completed=len(self.steps),
                total_steps=len(self.steps),
                duration_seconds=duration
            )
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.exception(f"Workflow error: {e}")
            
            return WorkflowResult(
                success=False,
                post_id=post.id,
                platform=self.platform_name,
                steps_completed=self.current_step,
                total_steps=len(self.steps),
                error_message=str(e),
                error_step=self.steps[self.current_step] if self.current_step < len(self.steps) else None,
                duration_seconds=duration
            )
    
    async def _execute_step_with_retry(self, step_name: str) -> StepResult:
        """Execute a step with retries."""
        for attempt in range(self.max_retries):
            try:
                result = await self._execute_step(step_name)
                
                if result.status == StepStatus.SUCCESS:
                    return result
                elif result.status == StepStatus.SKIPPED:
                    return result
                    
                logger.warning(f"Step failed (attempt {attempt+1}): {result.message}")
                
            except asyncio.TimeoutError:
                logger.warning(f"Step timed out (attempt {attempt+1})")
            except Exception as e:
                logger.exception(f"Step error (attempt {attempt+1}): {e}")
            
            if attempt < self.max_retries - 1:
                await asyncio.sleep(1)
        
        return StepResult(
            status=StepStatus.FAILED,
            message=f"Step '{step_name}' failed after {self.max_retries} attempts"
        )
    
    @abstractmethod
    async def _execute_step(self, step_name: str) -> StepResult:
        """
        Execute a single step. Must be implemented by subclass.
        
        Args:
            step_name: Name of the step to execute
            
        Returns:
            StepResult
        """
        pass
    
    # ==================== HELPER METHODS ====================
    
    async def take_screenshot(self) -> Optional[Image.Image]:
        """Take a screenshot and optionally save it."""
        await asyncio.sleep(self.screenshot_delay)
        
        screenshot = await self.vnc.capture()
        
        if screenshot and self.screenshots_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            step_name = self.steps[self.current_step] if self.current_step < len(self.steps) else "unknown"
            filename = f"{timestamp}_{self.current_step}_{step_name}.png"
            self.vnc.save_screenshot(screenshot, filename)
        
        return screenshot
    
    async def find_and_click(
        self,
        element_description: str,
        click_after_find: bool = True
    ) -> Optional[FoundElement]:
        """
        Take screenshot, find element, and optionally click it.
        
        Args:
            element_description: What to find
            click_after_find: Whether to click the element
            
        Returns:
            FoundElement if found
        """
        screenshot = await self.take_screenshot()
        if not screenshot:
            logger.error("Failed to capture screenshot")
            return None
        
        element = await self.vision.find_element(screenshot, element_description)
        
        if not element:
            logger.warning(f"Element not found: {element_description}")
            return None
        
        if click_after_find:
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked at ({element.x}, {element.y})")
        
        return element
    
    async def find_osp_button_and_click(self, button_name: str) -> bool:
        """
        Find and click an OSP button.
        
        Args:
            button_name: Button text (e.g., "OPEN URL", "COPY TITLE")
            
        Returns:
            True if successful
        """
        element = await self.find_and_click(
            f"button labeled '{button_name}' on the right side panel (OSP)"
        )
        return element is not None
    
    async def find_paste_target_and_paste(
        self,
        target_description: str
    ) -> bool:
        """
        Find paste target, click it, and paste.
        
        Args:
            target_description: Description of where to paste
            
        Returns:
            True if successful
        """
        element = await self.find_and_click(target_description)
        if not element:
            return False
        
        await asyncio.sleep(0.3)
        await self.input.paste()
        return True
    
    async def verify_screen_state(self, expected_state: str) -> bool:
        """
        Verify the screen shows expected state.
        
        Args:
            expected_state: Description of expected state
            
        Returns:
            True if screen matches
        """
        screenshot = await self.take_screenshot()
        if not screenshot:
            return False
        
        state = await self.vision.verify_screen_state(screenshot, expected_state)
        return state.is_match
```

---

### 10. Skool Workflow (`src/workflows/skool_workflow.py`)

```python
"""
Skool Workflow - Complete posting workflow for Skool.com

This workflow handles posting to Skool community platform.
It follows the exact sequence described in the brain specification.
"""

import asyncio
from typing import List

from src.workflows.base_workflow import BaseWorkflow, StepResult, StepStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SkoolWorkflow(BaseWorkflow):
    """Workflow for posting to Skool.com"""
    
    @property
    def platform_name(self) -> str:
        return "Skool"
    
    @property
    def steps(self) -> List[str]:
        return [
            "click_osp_open_url",           # Step 1: Click OPEN URL on OSP
            "wait_for_skool_page",          # Step 2: Wait for Skool to load
            "click_start_post",             # Step 3: Click "Start a post" on Skool
            "wait_for_post_dialog",         # Step 4: Wait for post dialog
            "click_osp_copy_title",         # Step 5: Click COPY TITLE on OSP
            "paste_title",                  # Step 6: Find title field and paste
            "click_osp_copy_body",          # Step 7: Click COPY BODY on OSP
            "paste_body",                   # Step 8: Find body field and paste
            "click_osp_copy_image",         # Step 9: Click COPY IMAGE on OSP
            "paste_image",                  # Step 10: Find image area and paste
            "check_email_toggle",           # Step 11: Check if email toggle needed
            "toggle_email_if_needed",       # Step 12: Toggle email if indicated
            "click_osp_post",               # Step 13: Click POST on OSP
            "click_skool_post_button",      # Step 14: Click actual Post button on Skool
            "verify_post_success",          # Step 15: Verify green confirmation
            "click_success_or_fail"         # Step 16: Click SUCCESS or FAILED on OSP
        ]
    
    async def _execute_step(self, step_name: str) -> StepResult:
        """Execute a single step in the Skool workflow."""
        
        # ==================== STEP 1: OPEN URL ====================
        if step_name == "click_osp_open_url":
            logger.info("Looking for OPEN URL button on OSP...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the OPEN URL button on the right side?
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'OPEN URL' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "OPEN URL button not found on OSP")
            
            # Click the button
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked OPEN URL at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Clicked OPEN URL")
        
        # ==================== STEP 2: WAIT FOR SKOOL ====================
        elif step_name == "wait_for_skool_page":
            logger.info("Waiting for Skool page to load...")
            
            # Wait a bit for page load
            await asyncio.sleep(3)
            
            # Verify Skool page is visible
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            state = await self.vision.verify_screen_state(
                screenshot,
                "Skool community page with navigation and content area visible"
            )
            
            if state.is_match:
                return StepResult(StepStatus.SUCCESS, "Skool page loaded")
            else:
                return StepResult(StepStatus.FAILED, "Skool page not detected")
        
        # ==================== STEP 3: START POST ====================
        elif step_name == "click_start_post":
            logger.info("Looking for 'Start a post' button on Skool...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the Start a post button?
            element = await self.vision.find_element(
                screenshot,
                "button or clickable area to start a new post on Skool, might say 'Start a post', 'Create', or have a plus icon"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "'Start a post' button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked 'Start a post' at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Clicked Start a post")
        
        # ==================== STEP 4: WAIT FOR DIALOG ====================
        elif step_name == "wait_for_post_dialog":
            logger.info("Waiting for post creation dialog...")
            
            await asyncio.sleep(2)
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            state = await self.vision.verify_screen_state(
                screenshot,
                "post creation dialog or form with title and body input fields"
            )
            
            if state.is_match:
                return StepResult(StepStatus.SUCCESS, "Post dialog opened")
            else:
                return StepResult(StepStatus.FAILED, "Post dialog not detected")
        
        # ==================== STEP 5: COPY TITLE ====================
        elif step_name == "click_osp_copy_title":
            logger.info("Looking for COPY TITLE button on OSP...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY TITLE' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "COPY TITLE button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY TITLE at ({element.x}, {element.y})")
            
            # Brief wait for clipboard
            await asyncio.sleep(0.3)
            
            return StepResult(StepStatus.SUCCESS, "Title copied to clipboard")
        
        # ==================== STEP 6: PASTE TITLE ====================
        elif step_name == "paste_title":
            logger.info("Looking for title paste location...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where do I paste the title?
            element = await self.vision.find_element(
                screenshot,
                "input field or text area for the post title, possibly highlighted or labeled 'Title', or a green box indicating where to paste title"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Title paste location not found")
            
            # Click the location
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            
            # Paste
            await self.input.paste()
            logger.info(f"Pasted title at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Title pasted")
        
        # ==================== STEP 7: COPY BODY ====================
        elif step_name == "click_osp_copy_body":
            logger.info("Looking for COPY BODY button on OSP...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY BODY' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "COPY BODY button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY BODY at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.3)
            
            return StepResult(StepStatus.SUCCESS, "Body copied to clipboard")
        
        # ==================== STEP 8: PASTE BODY ====================
        elif step_name == "paste_body":
            logger.info("Looking for body paste location...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "larger text area for post body content, possibly labeled 'Description' or 'Content', or a red box indicating where to paste body"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Body paste location not found")
            
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            await self.input.paste()
            logger.info(f"Pasted body at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Body pasted")
        
        # ==================== STEP 9: COPY IMAGE ====================
        elif step_name == "click_osp_copy_image":
            logger.info("Looking for COPY IMAGE button on OSP...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'COPY IMAGE' on the right side panel"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "COPY IMAGE button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked COPY IMAGE at ({element.x}, {element.y})")
            
            await asyncio.sleep(0.5)  # Image copy may take longer
            
            return StepResult(StepStatus.SUCCESS, "Image copied to clipboard")
        
        # ==================== STEP 10: PASTE IMAGE ====================
        elif step_name == "paste_image":
            logger.info("Looking for image paste location...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "image upload area, drag and drop zone, or button to add image/media, possibly highlighted or showing 'Add image'"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Image paste location not found")
            
            await self.input.click_at(element.x, element.y)
            await asyncio.sleep(0.3)
            await self.input.paste()
            logger.info(f"Pasted image at ({element.x}, {element.y})")
            
            # Wait for image to upload
            await asyncio.sleep(2)
            
            return StepResult(StepStatus.SUCCESS, "Image pasted")
        
        # ==================== STEP 11: CHECK EMAIL TOGGLE ====================
        elif step_name == "check_email_toggle":
            logger.info("Checking if email toggle is needed...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Does the OSP indicate email should be sent?
            needs_email = await self.vision.check_osp_email_toggle(screenshot)
            
            # Store result for next step
            self._email_toggle_needed = needs_email
            
            if needs_email:
                logger.info("Email toggle IS needed")
            else:
                logger.info("Email toggle NOT needed")
            
            return StepResult(
                StepStatus.SUCCESS, 
                f"Email toggle check: {'needed' if needs_email else 'not needed'}",
                data={"needs_email": needs_email}
            )
        
        # ==================== STEP 12: TOGGLE EMAIL IF NEEDED ====================
        elif step_name == "toggle_email_if_needed":
            if not getattr(self, '_email_toggle_needed', False):
                logger.info("Skipping email toggle (not needed)")
                return StepResult(StepStatus.SKIPPED, "Email toggle not needed")
            
            logger.info("Looking for email toggle on Skool...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the email toggle?
            element = await self.vision.find_element(
                screenshot,
                "checkbox or toggle for 'send email to members' or 'notify members', possibly an orange circle or toggle switch"
            )
            
            if not element:
                logger.warning("Email toggle not found, skipping")
                return StepResult(StepStatus.SKIPPED, "Email toggle not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Toggled email at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Email toggled")
        
        # ==================== STEP 13: CLICK OSP POST ====================
        elif step_name == "click_osp_post":
            logger.info("Looking for POST button on OSP...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            element = await self.vision.find_element(
                screenshot,
                "button labeled 'POST' on the right side panel, likely orange colored"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "POST button not found on OSP")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked OSP POST at ({element.x}, {element.y})")
            
            return StepResult(StepStatus.SUCCESS, "Ready to post")
        
        # ==================== STEP 14: CLICK SKOOL POST ====================
        elif step_name == "click_skool_post_button":
            logger.info("Looking for Skool's Post button...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Where is the final Post button on Skool?
            element = await self.vision.find_element(
                screenshot,
                "the main Post or Submit button on Skool to publish the post, NOT the OSP panel button"
            )
            
            if not element:
                return StepResult(StepStatus.FAILED, "Skool Post button not found")
            
            await self.input.click_at(element.x, element.y)
            logger.info(f"Clicked Skool Post at ({element.x}, {element.y})")
            
            # Wait for posting to complete
            await asyncio.sleep(3)
            
            return StepResult(StepStatus.SUCCESS, "Clicked Post")
        
        # ==================== STEP 15: VERIFY SUCCESS ====================
        elif step_name == "verify_post_success":
            logger.info("Verifying post was successful...")
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            # Ask vision: Is there a green confirmation box?
            state = await self.vision.verify_screen_state(
                screenshot,
                "green confirmation message, success notification, or 'Post created' message"
            )
            
            if state.is_match:
                logger.info("Post confirmed successful!")
                self._post_successful = True
                return StepResult(StepStatus.SUCCESS, "Post confirmed")
            else:
                logger.warning("Success confirmation not found")
                self._post_successful = False
                return StepResult(StepStatus.SUCCESS, "No confirmation found")
        
        # ==================== STEP 16: CLICK SUCCESS OR FAIL ====================
        elif step_name == "click_success_or_fail":
            post_successful = getattr(self, '_post_successful', False)
            
            screenshot = await self.take_screenshot()
            if not screenshot:
                return StepResult(StepStatus.FAILED, "Failed to capture screenshot")
            
            if post_successful:
                logger.info("Looking for SUCCESS button on OSP...")
                
                element = await self.vision.find_element(
                    screenshot,
                    "green button labeled 'SUCCESS' on the right side panel"
                )
                
                if not element:
                    return StepResult(StepStatus.FAILED, "SUCCESS button not found")
                
                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked SUCCESS at ({element.x}, {element.y})")
                
                return StepResult(StepStatus.SUCCESS, "Reported success")
            
            else:
                logger.info("Looking for FAILED button on OSP...")
                
                element = await self.vision.find_element(
                    screenshot,
                    "red button labeled 'FAILED' on the right side panel"
                )
                
                if not element:
                    return StepResult(StepStatus.FAILED, "FAILED button not found")
                
                await self.input.click_at(element.x, element.y)
                logger.info(f"Clicked FAILED at ({element.x}, {element.y})")
                
                return StepResult(StepStatus.SUCCESS, "Reported failure")
        
        # Unknown step
        else:
            return StepResult(StepStatus.FAILED, f"Unknown step: {step_name}")
```

---

### 11. Main Orchestrator (`src/orchestrator.py`)

```python
"""
Brain Orchestrator - The main control loop.

This is the BRAIN that coordinates everything:
1. Fetches pending posts from API
2. Connects to Windows 10 via VNC
3. Handles login if needed
4. Dispatches to platform-specific workflows
5. Reports results
"""

import asyncio
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

from src.fetcher import Fetcher, PendingPost, Platform
from src.reporter import Reporter
from src.subsystems.vnc_capture import VNCCapture
from src.subsystems.vision_engine import VisionEngine
from src.subsystems.input_injector import InputInjector
from src.subroutines.windows_login import WindowsLoginSubroutine
from src.workflows.base_workflow import WorkflowResult
from src.workflows.skool_workflow import SkoolWorkflow
# from src.workflows.instagram_workflow import InstagramWorkflow
# from src.workflows.facebook_workflow import FacebookWorkflow
# from src.workflows.tiktok_workflow import TikTokWorkflow
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BrainOrchestrator:
    """
    The main brain orchestrator.
    
    This class coordinates all subsystems to:
    1. Monitor for pending posts
    2. Connect to Windows 10
    3. Execute platform-specific workflows
    4. Report results
    """
    
    def __init__(self, config_path: str = "config/settings.yaml"):
        """
        Initialize the brain.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        
        # Subsystems
        self.fetcher: Optional[Fetcher] = None
        self.reporter: Optional[Reporter] = None
        self.vnc: Optional[VNCCapture] = None
        self.vision: Optional[VisionEngine] = None
        self.input: Optional[InputInjector] = None
        
        # Subroutines
        self.windows_login: Optional[WindowsLoginSubroutine] = None
        
        # Workflows
        self.workflows: Dict[Platform, Any] = {}
        
        # State
        self.running = False
        self.current_post: Optional[PendingPost] = None
    
    async def initialize(self) -> bool:
        """
        Initialize all subsystems.
        
        Returns:
            True if all subsystems initialized successfully
        """
        # Load configuration
        logger.info("Loading configuration...")
        self.config = self._load_config()
        
        # Initialize fetcher
        logger.info("Initializing fetcher...")
        self.fetcher = Fetcher(
            api_base_url=self.config["api"]["base_url"],
            timeout=self.config["api"]["timeout_seconds"]
        )
        await self.fetcher.initialize()
        
        # Initialize reporter
        logger.info("Initializing reporter...")
        self.reporter = Reporter(
            api_base_url=self.config["api"]["base_url"],
            timeout=self.config["api"]["timeout_seconds"]
        )
        await self.reporter.initialize()
        
        # Initialize VNC capture
        logger.info("Initializing VNC capture...")
        self.vnc = VNCCapture(
            host=self.config["windows_vm"]["vnc_host"],
            port=self.config["windows_vm"]["vnc_port"],
            password=self.config["windows_vm"].get("vnc_password")
        )
        vnc_ok = await self.vnc.initialize()
        if not vnc_ok:
            logger.error("VNC initialization failed")
            return False
        
        # Initialize vision engine
        logger.info("Initializing vision engine...")
        self.vision = VisionEngine(
            model=self.config["vision"]["model"],
            ollama_host=self.config["vision"]["ollama_host"],
            ollama_port=self.config["vision"]["ollama_port"],
            timeout=self.config["vision"]["timeout_seconds"]
        )
        vision_ok = await self.vision.initialize()
        if not vision_ok:
            logger.error("Vision engine initialization failed")
            return False
        
        # Initialize input injector
        logger.info("Initializing input injector...")
        self.input = InputInjector(
            proxmox_host=self.config["proxmox"]["host"],
            api_port=self.config["proxmox"]["input_api_port"]
        )
        input_ok = await self.input.initialize()
        if not input_ok:
            logger.error("Input injector initialization failed")
            return False
        
        # Initialize Windows login subroutine
        self.windows_login = WindowsLoginSubroutine(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input,
            password=self.config["windows_credentials"]["password"]
        )
        
        # Initialize workflows
        logger.info("Initializing workflows...")
        self._initialize_workflows()
        
        logger.info("Brain initialization complete!")
        return True
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(self.config_path) as f:
            config = yaml.safe_load(f)
        
        # Substitute environment variables
        import os
        def substitute_env(obj):
            if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
                var_name = obj[2:-1]
                return os.environ.get(var_name, obj)
            elif isinstance(obj, dict):
                return {k: substitute_env(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [substitute_env(item) for item in obj]
            return obj
        
        return substitute_env(config)
    
    def _initialize_workflows(self):
        """Initialize platform-specific workflows."""
        self.workflows[Platform.SKOOL] = SkoolWorkflow(
            vnc=self.vnc,
            vision=self.vision,
            input_injector=self.input
        )
        
        # TODO: Add other platforms
        # self.workflows[Platform.INSTAGRAM] = InstagramWorkflow(...)
        # self.workflows[Platform.FACEBOOK] = FacebookWorkflow(...)
        # self.workflows[Platform.TIKTOK] = TikTokWorkflow(...)
    
    async def shutdown(self):
        """Shutdown all subsystems gracefully."""
        logger.info("Shutting down brain...")
        self.running = False
        
        if self.fetcher:
            await self.fetcher.shutdown()
        if self.reporter:
            await self.reporter.shutdown()
        if self.vision:
            await self.vision.shutdown()
        if self.input:
            await self.input.shutdown()
        
        logger.info("Brain shutdown complete")
    
    async def run_forever(self):
        """
        Main loop - continuously process posts.
        
        This is the main brain loop that:
        1. Polls for pending posts
        2. Processes one post at a time
        3. Reports results
        4. Repeats
        """
        self.running = True
        poll_interval = self.config["api"]["poll_interval_seconds"]
        
        logger.info(f"Starting main loop (poll interval: {poll_interval}s)")
        
        while self.running:
            try:
                # Step 1: Check for pending post
                post = await self.fetcher.get_next_pending_post()
                
                if post:
                    # Step 2: Process the post
                    await self._process_post(post)
                else:
                    logger.debug("No pending posts, waiting...")
                
            except Exception as e:
                logger.exception(f"Main loop error: {e}")
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
        
        logger.info("Main loop ended")
    
    async def _process_post(self, post: PendingPost):
        """
        Process a single post.
        
        Args:
            post: Post to process
        """
        logger.info(f"{'='*60}")
        logger.info(f"PROCESSING POST: {post.id}")
        logger.info(f"Platform: {post.platform.value}")
        logger.info(f"{'='*60}")
        
        self.current_post = post
        
        try:
            # Step 1: Mark post as processing
            await self.reporter.report_processing(post.id)
            
            # Step 2: Ensure Windows 10 is ready
            if not await self._ensure_windows_ready():
                await self.reporter.report_failure(
                    post.id,
                    "Failed to connect to Windows 10",
                    step="windows_setup"
                )
                return
            
            # Step 3: Get workflow for platform
            workflow = self.workflows.get(post.platform)
            
            if not workflow:
                logger.error(f"No workflow for platform: {post.platform.value}")
                await self.reporter.report_failure(
                    post.id,
                    f"Unsupported platform: {post.platform.value}",
                    step="workflow_selection"
                )
                return
            
            # Step 4: Execute workflow
            result = await workflow.execute(post)
            
            # Step 5: Report result
            if result.success:
                await self.reporter.report_success(
                    post.id,
                    email_sent=post.send_email
                )
                logger.info(f"Post {post.id} completed successfully!")
            else:
                await self.reporter.report_failure(
                    post.id,
                    result.error_message or "Unknown error",
                    step=result.error_step
                )
                logger.warning(f"Post {post.id} failed: {result.error_message}")
            
        except Exception as e:
            logger.exception(f"Error processing post {post.id}: {e}")
            await self.reporter.report_failure(
                post.id,
                str(e),
                step="unknown"
            )
        
        finally:
            self.current_post = None
    
    async def _ensure_windows_ready(self) -> bool:
        """
        Ensure Windows 10 is connected and ready.
        
        Returns:
            True if Windows is ready
        """
        logger.info("Checking Windows 10 state...")
        
        # Step 1: Capture screenshot
        screenshot = await self.vnc.capture()
        if not screenshot:
            logger.error("Failed to capture Windows 10 screen")
            return False
        
        # Step 2: Check if login screen is showing
        is_login = await self.vision.check_for_login_screen(screenshot)
        
        if is_login:
            logger.info("Windows login screen detected, logging in...")
            
            if not await self.windows_login.execute():
                logger.error("Windows login failed")
                return False
        
        # Step 3: Verify desktop is ready
        screenshot = await self.vnc.capture()
        if not screenshot:
            return False
        
        state = await self.vision.verify_screen_state(
            screenshot,
            "Windows desktop with Chrome browser and OSP panel visible on the right side"
        )
        
        if state.is_match:
            logger.info("Windows 10 is ready")
            return True
        
        # Try to bring up the required windows
        logger.warning("Expected windows not visible, attempting to prepare...")
        
        # TODO: Add logic to start Chrome and OSP if not running
        
        return True  # Assume ready for now
    
    async def run_single_post(self, post_id: str) -> WorkflowResult:
        """
        Run a single post by ID (for testing).
        
        Args:
            post_id: Post ID to process
            
        Returns:
            WorkflowResult
        """
        # Fetch the specific post
        # This would need an API endpoint to get post by ID
        pass
```

---

## Running the Brain

### Starting the Brain

```bash
cd /home/ubuntu/social-brain

# Set environment variables
export WINDOWS_PASSWORD="your_password_here"
export VNC_PASSWORD="your_vnc_password"

# Activate virtual environment
source venv/bin/activate

# Run the brain
python main.py
```

### Running as a Service

Create `/etc/systemd/system/social-brain.service`:

```ini
[Unit]
Description=Social Media Brain Agent
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/social-brain
Environment=WINDOWS_PASSWORD=your_password
Environment=VNC_PASSWORD=your_vnc_password
ExecStart=/home/ubuntu/social-brain/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable social-brain
sudo systemctl start social-brain
sudo systemctl status social-brain
```

---

## Dependencies (`requirements.txt`)

```
# Core
asyncio-mqtt>=0.16.0
aiohttp>=3.9.0
pyyaml>=6.0.0

# VNC
vncdotool>=1.0.0

# Image handling
Pillow>=10.0.0

# Utilities
python-dotenv>=1.0.0
```

---

## Testing

### Test VNC Connection
```python
# test_vnc.py
import asyncio
from src.subsystems.vnc_capture import VNCCapture

async def test():
    vnc = VNCCapture()
    await vnc.initialize()
    screenshot = await vnc.capture()
    print(f"Screenshot captured: {screenshot.size}")
    screenshot.save("test_capture.png")

asyncio.run(test())
```

### Test Vision Engine
```python
# test_vision.py
import asyncio
from PIL import Image
from src.subsystems.vision_engine import VisionEngine

async def test():
    vision = VisionEngine()
    await vision.initialize()
    
    # Load test screenshot
    screenshot = Image.open("test_capture.png")
    
    # Find element
    element = await vision.find_element(
        screenshot,
        "button labeled 'OPEN URL' on the right side"
    )
    
    if element:
        print(f"Found at ({element.x}, {element.y})")
    else:
        print("Not found")

asyncio.run(test())
```

### Test Input Injection
```python
# test_input.py
import asyncio
from src.subsystems.input_injector import InputInjector

async def test():
    input_inj = InputInjector()
    await input_inj.initialize()
    
    # Move mouse to center
    await input_inj.move_mouse(960, 540)
    
    # Click
    await input_inj.click()

asyncio.run(test())
```

---

## Summary: The Complete Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         BRAIN EXECUTION FLOW                             │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. POLL API                                                             │
│     └─▶ Check for pending posts at social.sterlingcooley.com             │
│         └─▶ If post found: continue                                      │
│         └─▶ If no post: wait and poll again                              │
│                                                                          │
│  2. PREPARE WINDOWS                                                      │
│     └─▶ Take VNC screenshot of Windows 10                                │
│         └─▶ Ask vision: "Is this a login screen?"                        │
│             └─▶ If yes: Run login subroutine                             │
│                 └─▶ Find password field → Click → Type → Enter           │
│             └─▶ If no: Continue                                          │
│                                                                          │
│  3. EXECUTE WORKFLOW (for each step):                                    │
│                                                                          │
│     ┌────────────────────────────────────────────────────────────────┐   │
│     │  STEP 1: Click OPEN URL                                        │   │
│     │  └─▶ Screenshot → Ask vision "Where is OPEN URL?" → Click      │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 2: Wait for platform page                                │   │
│     │  └─▶ Screenshot → Ask vision "Is Skool loaded?" → Verify       │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 3: Click "Start a post"                                  │   │
│     │  └─▶ Screenshot → Ask vision "Where is Start Post?" → Click    │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 4: Click COPY TITLE on OSP                               │   │
│     │  └─▶ Screenshot → Ask vision "Where is COPY TITLE?" → Click    │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 5: Paste title                                           │   │
│     │  └─▶ Screenshot → Ask vision "Where to paste title?" → Click   │   │
│     │  └─▶ Send Ctrl+V                                               │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 6: Click COPY BODY on OSP                                │   │
│     │  └─▶ Screenshot → Ask vision "Where is COPY BODY?" → Click     │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 7: Paste body                                            │   │
│     │  └─▶ Screenshot → Ask vision "Where to paste body?" → Click    │   │
│     │  └─▶ Send Ctrl+V                                               │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 8: Click COPY IMAGE on OSP                               │   │
│     │  └─▶ Screenshot → Ask vision "Where is COPY IMAGE?" → Click    │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 9: Paste image                                           │   │
│     │  └─▶ Screenshot → Ask vision "Where to paste image?" → Click   │   │
│     │  └─▶ Send Ctrl+V                                               │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 10: Check email toggle                                   │   │
│     │  └─▶ Screenshot → Ask vision "Send email indicated?" → Yes/No  │   │
│     │      └─▶ If yes: Screenshot → Find toggle → Click              │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 11: Click POST on OSP                                    │   │
│     │  └─▶ Screenshot → Ask vision "Where is POST?" → Click          │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 12: Click platform Post button                           │   │
│     │  └─▶ Screenshot → Ask vision "Where is Submit?" → Click        │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 13: Verify success                                       │   │
│     │  └─▶ Screenshot → Ask vision "Green confirmation?" → Yes/No    │   │
│     ├────────────────────────────────────────────────────────────────┤   │
│     │  STEP 14: Click SUCCESS or FAILED                              │   │
│     │  └─▶ If success: Find SUCCESS button → Click                   │   │
│     │  └─▶ If failed: Find FAILED button → Click                     │   │
│     └────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  4. REPORT RESULT                                                        │
│     └─▶ API call to report success/failure                               │
│     └─▶ Return to step 1 (poll for next post)                            │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

This is the complete brain. Every step is:
1. **Take screenshot** of Windows 10 via VNC
2. **Ask vision** where to click (Qwen2.5-VL)
3. **Send click** via input injector
4. **Verify** result with another screenshot
5. **Proceed** to next step or **fail** with report