# UBUNTU-POSTER-INSTRUCTIONS.md
# Instructions for Ubuntu Agent (Computer-Use Poster Controller)

## YOUR ROLE

You are the **Poster Controller Agent** running on an Ubuntu VM inside Proxmox.

Your job is to:
1. **Monitor** the social dashboard API for pending posts (every 5 minutes)
2. **Control** the Windows 10 VM via VNC screen capture and QMP input injection
3. **Execute** posting workflows on social media platforms (starting with Skool.com)
4. **Verify** successful posting via vision analysis
5. **Report** completion/failure back to the API

**You do NOT download images or content.** The Windows 10 machine already has all content downloaded to `C:\PostQueue\pending\`. You simply check the API to know WHEN to act, then use computer-use to perform the posting.

---

## SYSTEM ARCHITECTURE - UNDERSTAND THIS FIRST

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PROXMOX HOST (192.168.100.1)                        │
│                         AMD Ryzen 9 7940HX                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────────┐│
│  │   UBUNTU VM (You are here)      │    │   WINDOWS 10 VM                 ││
│  │   192.168.100.X                 │    │   192.168.100.Y                 ││
│  │                                 │    │                                 ││
│  │   YOUR RESPONSIBILITIES:        │    │   ALREADY DONE:                 ││
│  │   • Poll API every 5 min        │    │   • Fetcher downloads content   ││
│  │   • VNC screen capture          │    │   • Content in C:\PostQueue\    ││
│  │   • Vision analysis (Qwen-VL)   │    │   • Browser installed           ││
│  │   • QMP input injection         │    │   • Logged into Skool.com       ││
│  │   • Execute posting playbook    │    │                                 ││
│  │   • Verify success              │    │   RECEIVES FROM YOU:            ││
│  │   • Report to API               │    │   • Mouse movements (QMP)       ││
│  │                                 │    │   • Keyboard input (QMP)        ││
│  │   TOOLS:                        │    │   • Looks like Logitech HID     ││
│  │   • Python + requests           │    │                                 ││
│  │   • OpenRouter API (Qwen-VL)    │    │                                 ││
│  │   • VNC client library          │    │                                 ││
│  │   • QMP socket connection       │    │                                 ││
│  └────────────┬────────────────────┘    └────────────┬────────────────────┘│
│               │                                      │                      │
│               │         VNC (screen capture)         │                      │
│               │◄─────────────────────────────────────┤                      │
│               │                                      │                      │
│               │         QMP (input injection)        │                      │
│               ├─────────────────────────────────────►│                      │
│               │                                      │                      │
└───────────────┴──────────────────────────────────────┴──────────────────────┘
                │
                │ HTTPS (API calls)
                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              social.sterlingcooley.com (DigitalOcean Droplet)               │
│                                                                             │
│   GET  /api/queue/gui/pending  ──► Returns pending posts (you check this)  │
│   POST /api/queue/gui/complete ──► Report successful posting               │
│   POST /api/queue/gui/failed   ──► Report failed posting                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## WHAT HAS ALREADY BEEN BUILT

### 1. Social Dashboard API (Working ✅)
- `GET /api/queue/gui/pending` returns pending posts as JSON
- Authentication via `X-API-Key` header
- Returns post metadata including platform, caption, Skool group URL

### 2. Windows 10 Fetcher (Working ✅)
- Polls API every 5 minutes
- Downloads images and content to `C:\PostQueue\pending\job_XXXXX\`
- Creates `job.json` with all posting instructions
- **You do NOT need to duplicate this** - just check the API to know when posts are ready

### 3. Your Existing Computer-Use Infrastructure
- VNC screen capture from Windows 10 VM
- QMP input injection with virtual Logitech HID devices
- Qwen2.5-VL for vision analysis via OpenRouter
- Behavioral biometrics for human-like mouse movements
- Bezier curves and Fitts's Law timing

---

## YOUR WORKFLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                    UBUNTU POSTER WORKFLOW                        │
└─────────────────────────────────────────────────────────────────┘

Every 5 minutes:
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: CHECK API FOR PENDING POSTS                            │
│                                                                 │
│  GET https://social.sterlingcooley.com/api/queue/gui/pending    │
│  Header: X-API-Key: {your_api_key}                              │
│                                                                 │
│  Response 200 with posts?  ──► Continue to Step 2               │
│  Response 204 (no posts)?  ──► Sleep 5 minutes, loop back       │
└─────────────────────────────────────────────────────────────────┘
    │
    │ (Only if pending posts exist)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: PARSE POST DATA                                        │
│                                                                 │
│  From API response, extract:                                    │
│  • id: "post-12345"                                             │
│  • platform: "skool"                                            │
│  • caption: "Hello world! 🚀"                                   │
│  • group_url: "https://www.skool.com/your-group"                │
│  • media: [{id: "xxx", type: "image"}] or []                    │
│                                                                 │
│  Note: The actual IMAGE FILE is on Windows at:                  │
│  C:\PostQueue\pending\job_XXXXX_post-12345\media_1.jpg          │
│  You will navigate the browser to select it.                    │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: CAPTURE WINDOWS SCREEN VIA VNC                         │
│                                                                 │
│  Connect to Windows 10 VM via VNC                               │
│  Capture current screen state                                   │
│  Send screenshot to Qwen2.5-VL for analysis:                    │
│  "What application is visible? Is a browser open?"              │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: EXECUTE PLATFORM-SPECIFIC PLAYBOOK                     │
│                                                                 │
│  For Skool.com (first platform to implement):                   │
│  1. Ensure browser is open and focused                          │
│  2. Navigate to group_url                                       │
│  3. Click "Create post" button                                  │
│  4. If media exists: Click upload, navigate to C:\PostQueue\... │
│  5. Type caption text                                           │
│  6. Click "Post" button                                         │
│  7. Wait for confirmation                                       │
│                                                                 │
│  ALL INPUTS via QMP (mouse moves, clicks, keystrokes)           │
│  Mouse movements use Bezier curves for human-like motion        │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: VERIFY SUCCESS WITH VISION                             │
│                                                                 │
│  Capture screen after posting                                   │
│  Send to Qwen2.5-VL: "Was the post successful?                  │
│  Do you see a confirmation message or the posted content?"      │
│                                                                 │
│  If success detected ──► Step 6a (report success)               │
│  If failure detected ──► Step 6b (report failure)               │
└─────────────────────────────────────────────────────────────────┘
    │
    ├──────────────────────────────────────┐
    ▼                                      ▼
┌─────────────────────────────┐  ┌─────────────────────────────┐
│  STEP 6a: REPORT SUCCESS    │  │  STEP 6b: REPORT FAILURE    │
│                             │  │                             │
│  POST /api/queue/gui/       │  │  POST /api/queue/gui/       │
│       complete              │  │       failed                │
│  Body: {                    │  │  Body: {                    │
│    "id": "post-12345",      │  │    "id": "post-12345",      │
│    "platform_post_id": "x"  │  │    "error": "description",  │
│  }                          │  │    "retry": true            │
│                             │  │  }                          │
└─────────────────────────────┘  └─────────────────────────────┘
    │                                      │
    └──────────────────┬───────────────────┘
                       │
                       ▼
              Continue loop...
```

---

## CRITICAL DISTINCTION: YOU vs WINDOWS

| Task | Who Does It |
|------|-------------|
| Download images from API | **Windows 10** (already done) |
| Store content locally | **Windows 10** (`C:\PostQueue\pending\`) |
| Check if posts are pending | **YOU (Ubuntu)** |
| See the Windows screen | **YOU (Ubuntu)** via VNC |
| Move the mouse | **YOU (Ubuntu)** via QMP |
| Type on keyboard | **YOU (Ubuntu)** via QMP |
| Click buttons in browser | **YOU (Ubuntu)** via QMP |
| Verify posting success | **YOU (Ubuntu)** via vision |
| Report to API | **YOU (Ubuntu)** |

**You are the "brain" that controls the Windows 10 "hands".**

---

## API RESPONSE FORMAT

When you call `GET /api/queue/gui/pending`, you'll receive:

### When posts are pending (200 OK):
```json
[
  {
    "id": "post-12345",
    "platform": "skool",
    "scheduled_time": "2025-01-02T15:30:00.000Z",
    "caption": "Check out this amazing content! 🚀\n\nLet me know what you think in the comments.",
    "hashtags": [],
    "link": null,
    "account": "personal",
    "group_url": "https://www.skool.com/sterling-ai-community",
    "media": [
      {
        "id": "post-12345",
        "type": "image",
        "filename": "content_image.jpg"
      }
    ]
  }
]
```

### When no posts pending (204 No Content):
Empty response - do nothing, wait 5 minutes.

---

## SKOOL.COM POSTING PLAYBOOK (First Platform)

This is the step-by-step workflow for posting to Skool.com:

### Prerequisites
- Windows 10 browser already logged into Skool.com
- Content already downloaded to `C:\PostQueue\pending\job_XXX\`

### Playbook Steps

```python
SKOOL_PLAYBOOK = {
    "name": "skool_post",
    "platform": "skool",
    "steps": [
        {
            "action": "ensure_browser_open",
            "description": "Make sure browser is open and focused",
            "vision_check": "Is a browser window visible?"
        },
        {
            "action": "navigate",
            "target": "{group_url}",  # From API response
            "description": "Go to the Skool group page",
            "vision_check": "Do you see the Skool group page with the group name visible?"
        },
        {
            "action": "wait",
            "duration_ms": 2000,
            "description": "Wait for page to fully load"
        },
        {
            "action": "click",
            "target": "Create post button",
            "vision_prompt": "Find the button or link to create a new post. It might say 'Write something...' or have a compose icon.",
            "description": "Click to start creating a post"
        },
        {
            "action": "wait",
            "duration_ms": 1000,
            "description": "Wait for post composer to open"
        },
        {
            "action": "conditional",
            "condition": "has_media",
            "if_true": [
                {
                    "action": "click",
                    "target": "Image upload button",
                    "vision_prompt": "Find the image/photo upload button in the post composer. Usually an image icon or 'Add photo' text."
                },
                {
                    "action": "wait",
                    "duration_ms": 500
                },
                {
                    "action": "file_dialog",
                    "path": "C:\\PostQueue\\pending\\{job_folder}\\media_1.jpg",
                    "description": "Navigate file picker to select the image"
                },
                {
                    "action": "wait",
                    "duration_ms": 2000,
                    "description": "Wait for image upload"
                },
                {
                    "action": "vision_verify",
                    "prompt": "Is the image now visible in the post composer? Do you see a thumbnail or preview?"
                }
            ]
        },
        {
            "action": "click",
            "target": "Text input area",
            "vision_prompt": "Find the text input area where you type the post content."
        },
        {
            "action": "type",
            "text": "{caption}",  # From API response
            "humanize": True,
            "description": "Type the post caption with human-like timing"
        },
        {
            "action": "wait",
            "duration_ms": 1000
        },
        {
            "action": "click",
            "target": "Post/Submit button",
            "vision_prompt": "Find the button to submit/publish the post. Usually says 'Post', 'Publish', or 'Share'."
        },
        {
            "action": "wait",
            "duration_ms": 3000,
            "description": "Wait for post to be published"
        },
        {
            "action": "vision_verify",
            "prompt": "Was the post successfully published? Do you see the post now displayed in the feed or a success confirmation?",
            "success_indicators": ["post visible in feed", "success message", "posted content displayed"],
            "failure_indicators": ["error message", "try again", "failed", "composer still open"]
        }
    ]
}
```

---

## CODE STRUCTURE TO BUILD

You need to build/extend these components:

### 1. API Monitor (`api_monitor.py`)
```python
"""
Polls social.sterlingcooley.com API for pending posts.
Does NOT download content - just checks what's pending.
"""

import requests
import time
import schedule
from typing import List, Dict, Optional

DASHBOARD_URL = "https://social.sterlingcooley.com"
API_KEY = "your-api-key"
POLL_INTERVAL = 5  # minutes

class APIMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers['X-API-Key'] = API_KEY
    
    def get_pending_posts(self) -> List[Dict]:
        """Check API for pending posts. Returns list or empty list."""
        url = f"{DASHBOARD_URL}/api/queue/gui/pending"
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                posts = response.json()
                print(f"[API] Found {len(posts)} pending post(s)")
                return posts
            
            elif response.status_code == 204:
                print("[API] No pending posts")
                return []
            
            else:
                print(f"[API] Unexpected status: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"[API] Error: {e}")
            return []
    
    def report_success(self, post_id: str, platform_post_id: str = None):
        """Report successful posting to API."""
        url = f"{DASHBOARD_URL}/api/queue/gui/complete"
        self.session.post(url, json={
            "id": post_id,
            "platform_post_id": platform_post_id
        })
    
    def report_failure(self, post_id: str, error: str, retry: bool = True):
        """Report failed posting to API."""
        url = f"{DASHBOARD_URL}/api/queue/gui/failed"
        self.session.post(url, json={
            "id": post_id,
            "error": error,
            "retry": retry
        })
```

### 2. Vision Controller (`vision_controller.py`)
```python
"""
Uses VNC to capture Windows screen and Qwen2.5-VL for analysis.
"""

import base64
from openai import OpenAI  # For OpenRouter

OPENROUTER_API_KEY = "your-openrouter-key"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

class VisionController:
    def __init__(self, vnc_host: str, vnc_port: int):
        self.vnc_host = vnc_host
        self.vnc_port = vnc_port
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY
        )
    
    def capture_screen(self) -> bytes:
        """Capture current Windows screen via VNC."""
        # TODO: Implement VNC capture
        # Return PNG bytes
        pass
    
    def analyze_screen(self, prompt: str) -> str:
        """Send screenshot to Qwen2.5-VL for analysis."""
        screenshot = self.capture_screen()
        screenshot_b64 = base64.b64encode(screenshot).decode()
        
        response = self.client.chat.completions.create(
            model="qwen/qwen-2.5-vl-72b-instruct",  # Or appropriate model
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_b64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )
        
        return response.choices[0].message.content
    
    def find_element(self, description: str) -> tuple[int, int]:
        """
        Use vision to find a UI element and return its coordinates.
        
        Returns (x, y) center coordinates of the element.
        """
        prompt = f"""Find this UI element on screen: {description}
        
Return ONLY the approximate X,Y coordinates of the center of this element.
Format: X,Y (just two numbers separated by comma, nothing else)
Screen resolution is 1920x1080."""
        
        result = self.analyze_screen(prompt)
        # Parse "X,Y" response
        try:
            x, y = map(int, result.strip().split(','))
            return (x, y)
        except:
            raise Exception(f"Could not parse coordinates: {result}")
```

### 3. Input Controller (`input_controller.py`)
```python
"""
Sends mouse/keyboard input to Windows VM via QMP.
Uses human-like movements with Bezier curves.
"""

import socket
import json
import time
import math
import random

class InputController:
    def __init__(self, qmp_socket_path: str):
        self.qmp_socket = qmp_socket_path
        self.current_x = 960  # Start at center
        self.current_y = 540
    
    def _send_qmp(self, command: dict):
        """Send command to QEMU via QMP socket."""
        # TODO: Implement QMP communication
        pass
    
    def _bezier_curve(self, start: tuple, end: tuple, steps: int = 50) -> list:
        """Generate human-like curved path between two points."""
        x0, y0 = start
        x3, y3 = end
        
        # Random control points for natural curve
        x1 = x0 + (x3 - x0) * 0.3 + random.randint(-50, 50)
        y1 = y0 + (y3 - y0) * 0.1 + random.randint(-30, 30)
        x2 = x0 + (x3 - x0) * 0.7 + random.randint(-50, 50)
        y2 = y0 + (y3 - y0) * 0.9 + random.randint(-30, 30)
        
        points = []
        for i in range(steps + 1):
            t = i / steps
            # Cubic Bezier formula
            x = (1-t)**3 * x0 + 3*(1-t)**2*t * x1 + 3*(1-t)*t**2 * x2 + t**3 * x3
            y = (1-t)**3 * y0 + 3*(1-t)**2*t * y1 + 3*(1-t)*t**2 * y2 + t**3 * y3
            points.append((int(x), int(y)))
        
        return points
    
    def _fitts_delay(self, distance: float, width: float = 50) -> float:
        """Calculate movement time using Fitts's Law."""
        # Fitts's Law: MT = a + b * log2(2D/W)
        a = 0.1  # Base time
        b = 0.15  # Movement factor
        
        if distance < 1:
            distance = 1
        
        movement_time = a + b * math.log2(2 * distance / width)
        # Add human variability
        movement_time *= random.uniform(0.8, 1.2)
        
        return max(0.1, movement_time)
    
    def move_to(self, x: int, y: int):
        """Move mouse to coordinates with human-like motion."""
        start = (self.current_x, self.current_y)
        end = (x, y)
        
        distance = math.sqrt((x - self.current_x)**2 + (y - self.current_y)**2)
        duration = self._fitts_delay(distance)
        
        path = self._bezier_curve(start, end)
        step_delay = duration / len(path)
        
        for px, py in path:
            self._send_qmp({
                "execute": "input-send-event",
                "arguments": {
                    "events": [{
                        "type": "abs",
                        "data": {"axis": "x", "value": px}
                    }, {
                        "type": "abs",
                        "data": {"axis": "y", "value": py}
                    }]
                }
            })
            time.sleep(step_delay + random.uniform(0, 0.01))
        
        self.current_x = x
        self.current_y = y
    
    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Click at coordinates (or current position if not specified)."""
        if x is not None and y is not None:
            self.move_to(x, y)
        
        # Small pause before click (human behavior)
        time.sleep(random.uniform(0.05, 0.15))
        
        # Mouse down
        self._send_qmp({
            "execute": "input-send-event",
            "arguments": {
                "events": [{
                    "type": "btn",
                    "data": {"down": True, "button": button}
                }]
            }
        })
        
        # Human-like click duration
        time.sleep(random.uniform(0.05, 0.12))
        
        # Mouse up
        self._send_qmp({
            "execute": "input-send-event",
            "arguments": {
                "events": [{
                    "type": "btn",
                    "data": {"down": False, "button": button}
                }]
            }
        })
    
    def type_text(self, text: str, humanize: bool = True):
        """Type text with optional human-like timing."""
        for char in text:
            # Send key press via QMP
            self._send_qmp({
                "execute": "input-send-event",
                "arguments": {
                    "events": [{
                        "type": "key",
                        "data": {"down": True, "key": {"type": "qcode", "data": char}}
                    }]
                }
            })
            
            if humanize:
                # Variable typing speed
                delay = random.uniform(0.03, 0.12)
                # Occasional longer pauses (thinking)
                if random.random() < 0.05:
                    delay += random.uniform(0.2, 0.5)
                time.sleep(delay)
            else:
                time.sleep(0.01)
```

### 4. Playbook Executor (`playbook_executor.py`)
```python
"""
Executes platform-specific posting playbooks.
"""

from typing import Dict, List
from api_monitor import APIMonitor
from vision_controller import VisionController
from input_controller import InputController

class PlaybookExecutor:
    def __init__(self, api: APIMonitor, vision: VisionController, input: InputController):
        self.api = api
        self.vision = vision
        self.input = input
    
    def execute_skool_post(self, post: Dict) -> bool:
        """Execute Skool.com posting playbook."""
        post_id = post['id']
        group_url = post.get('group_url', '')
        caption = post.get('caption', '')
        has_media = len(post.get('media', [])) > 0
        
        print(f"[Skool] Starting post {post_id}")
        
        try:
            # Step 1: Navigate to group
            print(f"[Skool] Navigating to {group_url}")
            self._navigate_to_url(group_url)
            time.sleep(2)
            
            # Step 2: Find and click "Create post"
            print("[Skool] Looking for create post button...")
            coords = self.vision.find_element(
                "The button or text area to create a new post in Skool. "
                "It might say 'Write something...' or be a compose button."
            )
            self.input.click(coords[0], coords[1])
            time.sleep(1)
            
            # Step 3: Handle media upload if needed
            if has_media:
                print("[Skool] Uploading media...")
                self._upload_media(post)
            
            # Step 4: Type caption
            print("[Skool] Typing caption...")
            # Click text area first
            text_coords = self.vision.find_element(
                "The text input area where post content is typed"
            )
            self.input.click(text_coords[0], text_coords[1])
            time.sleep(0.5)
            
            self.input.type_text(caption, humanize=True)
            time.sleep(1)
            
            # Step 5: Click post button
            print("[Skool] Clicking post button...")
            post_btn = self.vision.find_element(
                "The button to publish/submit the post. Usually says 'Post' or 'Publish'."
            )
            self.input.click(post_btn[0], post_btn[1])
            time.sleep(3)
            
            # Step 6: Verify success
            print("[Skool] Verifying post success...")
            verification = self.vision.analyze_screen(
                "Was the post successfully published? Look for:\n"
                "- The post appearing in the feed\n"
                "- A success message\n"
                "- The compose dialog closing\n\n"
                "Respond with 'SUCCESS' if posted, or 'FAILED: reason' if not."
            )
            
            if "SUCCESS" in verification.upper():
                print(f"[Skool] ✓ Post {post_id} successful!")
                self.api.report_success(post_id)
                return True
            else:
                print(f"[Skool] ✗ Post {post_id} failed: {verification}")
                self.api.report_failure(post_id, verification)
                return False
                
        except Exception as e:
            print(f"[Skool] ✗ Error: {e}")
            self.api.report_failure(post_id, str(e))
            return False
    
    def _navigate_to_url(self, url: str):
        """Navigate browser to URL."""
        # Press Ctrl+L to focus address bar
        self.input._send_qmp({"execute": "input-send-event", "arguments": {
            "events": [
                {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "ctrl"}}},
                {"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "l"}}}
            ]
        }})
        time.sleep(0.2)
        self.input._send_qmp({"execute": "input-send-event", "arguments": {
            "events": [
                {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": "l"}}},
                {"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": "ctrl"}}}
            ]
        }})
        time.sleep(0.3)
        
        # Type URL
        self.input.type_text(url, humanize=False)
        time.sleep(0.2)
        
        # Press Enter
        self.input._send_qmp({"execute": "input-send-event", "arguments": {
            "events": [{"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "ret"}}}]
        }})
        time.sleep(0.1)
        self.input._send_qmp({"execute": "input-send-event", "arguments": {
            "events": [{"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": "ret"}}}]
        }})
    
    def _upload_media(self, post: Dict):
        """Handle media upload in file dialog."""
        # Find job folder name from post ID
        # The Windows fetcher saves to: C:\PostQueue\pending\job_XXXXX_{post_id}\
        job_folder = f"job_*_{post['id']}"
        media_path = f"C:\\PostQueue\\pending\\{job_folder}\\media_1.jpg"
        
        # Click upload button
        upload_btn = self.vision.find_element(
            "The image/photo upload button in the post composer"
        )
        self.input.click(upload_btn[0], upload_btn[1])
        time.sleep(1)
        
        # File dialog should open - type the path
        # In Windows file dialog, we can type the full path
        self.input.type_text(media_path, humanize=False)
        time.sleep(0.5)
        
        # Press Enter to select file
        self.input._send_qmp({"execute": "input-send-event", "arguments": {
            "events": [{"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": "ret"}}}]
        }})
        time.sleep(2)  # Wait for upload
```

### 5. Main Loop (`main.py`)
```python
"""
Main entry point for Ubuntu Poster Controller.
"""

import time
import schedule
from api_monitor import APIMonitor
from vision_controller import VisionController
from input_controller import InputController
from playbook_executor import PlaybookExecutor

# Configuration
WINDOWS_VNC_HOST = "192.168.100.Y"  # Your Windows 10 VM IP
WINDOWS_VNC_PORT = 5900
QMP_SOCKET = "/path/to/qmp.sock"
POLL_INTERVAL = 5  # minutes

def main():
    print("=" * 60)
    print("  UBUNTU POSTER CONTROLLER")
    print("=" * 60)
    print(f"  Windows VM: {WINDOWS_VNC_HOST}:{WINDOWS_VNC_PORT}")
    print(f"  Poll Interval: {POLL_INTERVAL} minutes")
    print("=" * 60)
    
    # Initialize components
    api = APIMonitor()
    vision = VisionController(WINDOWS_VNC_HOST, WINDOWS_VNC_PORT)
    input_ctrl = InputController(QMP_SOCKET)
    executor = PlaybookExecutor(api, vision, input_ctrl)
    
    def check_and_post():
        """Check for pending posts and execute if found."""
        print(f"\n[{time.strftime('%H:%M:%S')}] Checking for pending posts...")
        
        posts = api.get_pending_posts()
        
        if not posts:
            print("  No pending posts. Waiting...")
            return
        
        for post in posts:
            platform = post.get('platform', 'unknown')
            post_id = post.get('id', 'unknown')
            
            print(f"\n  Found post: {post_id} for {platform}")
            
            if platform == 'skool':
                executor.execute_skool_post(post)
            else:
                print(f"  [SKIP] Platform '{platform}' not yet implemented")
    
    # Run immediately on start
    check_and_post()
    
    # Schedule regular checks
    schedule.every(POLL_INTERVAL).minutes.do(check_and_post)
    
    print(f"\nRunning... (checking every {POLL_INTERVAL} minutes)")
    print("Press Ctrl+C to stop\n")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    main()
```

---

## WHAT YOU NEED TO IMPLEMENT/VERIFY

1. **VNC Screen Capture** - Connect to Windows VM and grab screenshots
2. **QMP Input Injection** - Send mouse/keyboard via QEMU QMP socket
3. **OpenRouter Integration** - API calls to Qwen2.5-VL for vision analysis
4. **Skool.com Playbook** - Refine the posting steps based on actual UI

---

## TESTING APPROACH

### Phase 1: API Monitoring Only
```python
# Just test API monitoring without computer-use
api = APIMonitor()
posts = api.get_pending_posts()
print(f"Found {len(posts)} posts")
```

### Phase 2: Vision Capture Only
```python
# Test VNC capture and vision analysis
vision = VisionController("192.168.100.Y", 5900)
screenshot = vision.capture_screen()
analysis = vision.analyze_screen("Describe what you see on this Windows desktop")
print(analysis)
```

### Phase 3: Input Injection Only
```python
# Test mouse movement (move to center of screen)
input_ctrl = InputController("/path/to/qmp.sock")
input_ctrl.move_to(960, 540)
input_ctrl.click()
```

### Phase 4: Full Integration
```python
# Run the full posting workflow
main()
```

---

## SUCCESS CRITERIA

The Ubuntu Poster Controller is working when:

1. ✅ API monitoring detects pending posts correctly
2. ✅ VNC captures Windows screen successfully
3. ✅ Qwen2.5-VL analyzes screenshots and finds UI elements
4. ✅ QMP sends mouse/keyboard input to Windows VM
5. ✅ Skool.com post is successfully created
6. ✅ Success/failure reported back to API
7. ✅ Windows Fetcher sees post status change to 'published'

---

## REMEMBER

- **You do NOT download images** - Windows already has them
- **You only CHECK the API** to know when to act
- **You CONTROL Windows** via VNC (see) and QMP (act)
- **Start with Skool.com** - other platforms come later
- **Human-like input** is critical to avoid detection
- **Vision verification** confirms success before reporting

Good luck! 🚀