# UBUNTU-AGENT-INSTRUCTIONS.md
# Ubuntu Controller - Social Media Automation Brain

## Architectural Shift: What Changed

**Previous Approach (Flawed):**
We tried to use computer vision models to read on-screen instructions, understand context, and make decisions about what to do next. We hoped the AI could see "Click here to paste" overlays and act autonomously.

**New Approach (Correct):**
Computer vision is **eyes only** - it helps Python scripts see the screen to identify clickable elements and verify UI state. The **intelligence lives in Python code** - deterministic scripts that know exactly what steps to execute in what order. Vision assists navigation; it doesn't drive decision-making.

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEW ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   UBUNTU CONTROLLER (This Machine)                              │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  PYTHON ORCHESTRATOR (The Brain)                        │   │
│   │  - Knows all steps for each platform                    │   │
│   │  - Executes steps in deterministic order                │   │
│   │  - Calls vision model when it needs to "see"            │   │
│   │  - Sends mouse/keyboard commands to Windows             │   │
│   └──────────────────────┬──────────────────────────────────┘   │
│                          │                                      │
│   ┌──────────────────────▼──────────────────────────────────┐   │
│   │  VISION MODULE (The Eyes)                               │   │
│   │  - Takes VNC screenshots of Windows 10                  │   │
│   │  - Identifies UI elements (buttons, fields, etc.)       │   │
│   │  - Returns coordinates for clicking                     │   │
│   │  - Verifies expected UI state                           │   │
│   └──────────────────────┬──────────────────────────────────┘   │
│                          │                                      │
│   ┌──────────────────────▼──────────────────────────────────┐   │
│   │  INPUT INJECTOR                                         │   │
│   │  - Sends commands to Proxmox host (port 8888)           │   │
│   │  - Proxmox translates to QMP for Windows VM             │   │
│   │  - Mouse moves, clicks, keyboard input                  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   WINDOWS 10 VM (The Cockpit)                                   │
│   - Receives input commands (doesn't decide anything)           │
│   - Chrome browser open to social media platforms               │
│   - Screen is captured via VNC for Ubuntu to see                │
│   - No AI running locally - just a controlled desktop           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Your Role: Ubuntu Controller Agent

You are responsible for building the **Python orchestration system** that:

1. Retrieves pending posts from the Social Dashboard API
2. Executes platform-specific posting workflows step-by-step
3. Uses vision to locate UI elements and verify state
4. Sends precise input commands to the Windows 10 VM
5. Reports success/failure back to the API

---

## Core Components to Build

### 1. VNC Screen Capture Module

Captures the current state of the Windows 10 desktop.

```python
# src/vnc_capture.py
"""Capture Windows 10 screen via VNC for vision analysis."""
import socket
from PIL import Image
import io

class VNCCapture:
    """Captures screenshots from Windows 10 VM via VNC."""
    
    def __init__(self, host: str = "192.168.100.20", port: int = 5900):
        """
        Initialize VNC capture.
        
        Args:
            host: Windows 10 VM IP on vmbr1 bridge
            port: VNC port (typically 5900)
        """
        self.host = host
        self.port = port
        # VNC connection details will depend on your VNC server setup
        # Options: use vncdotool, or direct RFB protocol, or screenshot via API
    
    def capture(self) -> Image.Image:
        """
        Capture current screen.
        
        Returns:
            PIL Image of Windows 10 desktop
        """
        # Implementation depends on VNC library choice
        # Simplest: use subprocess to call vncsnapshot or similar
        pass
    
    def capture_region(self, x: int, y: int, width: int, height: int) -> Image.Image:
        """Capture specific region of screen."""
        full = self.capture()
        return full.crop((x, y, x + width, y + height))
```

**Recommended Libraries:**
- `vncdotool` - Python VNC client with screenshot capability
- `PIL/Pillow` - Image handling
- Alternative: Use Proxmox's built-in screenshot API if available

---

### 2. Vision Element Finder Module

Uses Qwen2.5-VL to identify UI elements on screenshots.

```python
# src/vision_finder.py
"""Use vision model to find UI elements on screen."""
import ollama
from PIL import Image
import json
from typing import Optional, Tuple, List
from dataclasses import dataclass

@dataclass
class UIElement:
    """Represents a found UI element."""
    element_type: str  # button, input, link, etc.
    text: str          # Text on/near element
    x: int             # Center X coordinate
    y: int             # Center Y coordinate
    confidence: float  # How confident the model is

class VisionFinder:
    """Finds UI elements using vision model."""
    
    def __init__(self, model: str = "qwen2.5vl:7b"):
        self.model = model
    
    def find_element(
        self, 
        screenshot: Image.Image, 
        description: str
    ) -> Optional[UIElement]:
        """
        Find a specific UI element on screen.
        
        Args:
            screenshot: PIL Image of current screen
            description: What to find, e.g., "blue Post button", 
                        "text input field for caption", "Upload button"
        
        Returns:
            UIElement with coordinates, or None if not found
        """
        # Save screenshot temporarily for Ollama
        temp_path = "/tmp/current_screen.png"
        screenshot.save(temp_path)
        
        prompt = f"""Look at this screenshot and find: {description}

If you find it, respond with JSON:
{{"found": true, "type": "button", "text": "Post", "x": 500, "y": 300, "confidence": 0.95}}

The x,y coordinates should be the CENTER of the element, suitable for clicking.
If not found, respond: {{"found": false, "reason": "description of why"}}

ONLY respond with JSON, no other text."""

        response = ollama.chat(
            model=self.model,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [temp_path]
            }]
        )
        
        # Parse response
        try:
            result = json.loads(response['message']['content'])
            if result.get('found'):
                return UIElement(
                    element_type=result.get('type', 'unknown'),
                    text=result.get('text', ''),
                    x=result['x'],
                    y=result['y'],
                    confidence=result.get('confidence', 0.5)
                )
        except json.JSONDecodeError:
            pass
        
        return None
    
    def verify_state(
        self, 
        screenshot: Image.Image, 
        expected_state: str
    ) -> Tuple[bool, str]:
        """
        Verify the screen shows expected state.
        
        Args:
            screenshot: Current screen
            expected_state: Description like "Instagram post creation page",
                           "Upload dialog is open", "Post was successful"
        
        Returns:
            (is_correct, explanation)
        """
        temp_path = "/tmp/current_screen.png"
        screenshot.save(temp_path)
        
        prompt = f"""Look at this screenshot and determine:
Does this screen show: "{expected_state}"?

Respond with JSON:
{{"matches": true/false, "explanation": "brief reason"}}

ONLY respond with JSON."""

        response = ollama.chat(
            model=self.model,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [temp_path]
            }]
        )
        
        try:
            result = json.loads(response['message']['content'])
            return result.get('matches', False), result.get('explanation', '')
        except:
            return False, "Failed to parse vision response"
    
    def find_all_buttons(self, screenshot: Image.Image) -> List[UIElement]:
        """Find all clickable buttons on screen."""
        temp_path = "/tmp/current_screen.png"
        screenshot.save(temp_path)
        
        prompt = """List ALL clickable buttons visible in this screenshot.

Respond with JSON array:
[
  {"type": "button", "text": "Post", "x": 500, "y": 300},
  {"type": "button", "text": "Cancel", "x": 400, "y": 300}
]

Include the center coordinates for each button. ONLY respond with JSON array."""

        response = ollama.chat(
            model=self.model,
            messages=[{
                'role': 'user',
                'content': prompt,
                'images': [temp_path]
            }]
        )
        
        try:
            buttons = json.loads(response['message']['content'])
            return [
                UIElement(
                    element_type=b.get('type', 'button'),
                    text=b.get('text', ''),
                    x=b['x'],
                    y=b['y'],
                    confidence=0.8
                )
                for b in buttons
            ]
        except:
            return []
```

---

### 3. Input Injector Module

Sends mouse/keyboard commands to Windows 10 via Proxmox.

```python
# src/input_injector.py
"""Send input commands to Windows 10 VM via Proxmox."""
import requests
import time
from typing import Optional

class InputInjector:
    """Injects mouse and keyboard input into Windows 10 VM."""
    
    def __init__(
        self, 
        proxmox_host: str = "192.168.100.1",  # Proxmox host on vmbr1
        api_port: int = 8888
    ):
        """
        Initialize input injector.
        
        Args:
            proxmox_host: Proxmox host IP
            api_port: Port where input translation service runs
        """
        self.base_url = f"http://{proxmox_host}:{api_port}"
    
    def move_mouse(self, x: int, y: int, duration_ms: int = 500) -> bool:
        """
        Move mouse to absolute position.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration_ms: Movement duration for human-like motion
        
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.base_url}/mouse/move",
                json={"x": x, "y": y, "duration": duration_ms}
            )
            return response.status_code == 200
        except:
            return False
    
    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> bool:
        """
        Click at position (or current position if x,y not specified).
        
        Args:
            x: Optional X coordinate
            y: Optional Y coordinate  
            button: "left", "right", or "middle"
        
        Returns:
            True if successful
        """
        payload = {"button": button}
        if x is not None and y is not None:
            payload["x"] = x
            payload["y"] = y
        
        try:
            response = requests.post(
                f"{self.base_url}/mouse/click",
                json=payload
            )
            return response.status_code == 200
        except:
            return False
    
    def double_click(self, x: int, y: int) -> bool:
        """Double click at position."""
        try:
            response = requests.post(
                f"{self.base_url}/mouse/double_click",
                json={"x": x, "y": y}
            )
            return response.status_code == 200
        except:
            return False
    
    def type_text(self, text: str, delay_ms: int = 50) -> bool:
        """
        Type text string.
        
        Args:
            text: Text to type
            delay_ms: Delay between keystrokes
        
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.base_url}/keyboard/type",
                json={"text": text, "delay": delay_ms}
            )
            return response.status_code == 200
        except:
            return False
    
    def press_key(self, key: str, modifiers: list = None) -> bool:
        """
        Press a single key with optional modifiers.
        
        Args:
            key: Key name ("enter", "tab", "escape", "a", "1", etc.)
            modifiers: List of modifiers ["ctrl", "shift", "alt"]
        
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.base_url}/keyboard/press",
                json={"key": key, "modifiers": modifiers or []}
            )
            return response.status_code == 200
        except:
            return False
    
    def paste_from_clipboard(self) -> bool:
        """Send Ctrl+V to paste."""
        return self.press_key("v", ["ctrl"])
    
    def scroll(self, direction: str = "down", amount: int = 3) -> bool:
        """
        Scroll the page.
        
        Args:
            direction: "up" or "down"
            amount: Number of scroll units
        
        Returns:
            True if successful
        """
        try:
            response = requests.post(
                f"{self.base_url}/mouse/scroll",
                json={"direction": direction, "amount": amount}
            )
            return response.status_code == 200
        except:
            return False
```

---

### 4. Platform Workflow Orchestrators

Deterministic scripts for each social media platform. **This is where the intelligence lives.**

```python
# src/workflows/instagram.py
"""Instagram posting workflow - deterministic step-by-step execution."""
import time
from dataclasses import dataclass
from typing import Optional
from enum import Enum

from src.vnc_capture import VNCCapture
from src.vision_finder import VisionFinder
from src.input_injector import InputInjector


class InstagramStep(Enum):
    """All steps in Instagram posting workflow."""
    NAVIGATE_TO_INSTAGRAM = "navigate_to_instagram"
    WAIT_FOR_PAGE_LOAD = "wait_for_page_load"
    CLICK_CREATE_POST = "click_create_post"
    WAIT_FOR_UPLOAD_DIALOG = "wait_for_upload_dialog"
    SELECT_MEDIA_FILE = "select_media_file"
    WAIT_FOR_MEDIA_LOAD = "wait_for_media_load"
    CLICK_NEXT_BUTTON = "click_next_button"
    WAIT_FOR_FILTER_PAGE = "wait_for_filter_page"
    CLICK_NEXT_AGAIN = "click_next_again"
    WAIT_FOR_CAPTION_PAGE = "wait_for_caption_page"
    ENTER_CAPTION = "enter_caption"
    CLICK_SHARE_BUTTON = "click_share_button"
    VERIFY_POST_SUCCESS = "verify_post_success"
    DONE = "done"


@dataclass
class PostContent:
    """Content to post."""
    media_path: str      # Path to image/video on Windows 10
    caption: str         # Caption text
    hashtags: list       # List of hashtags


class InstagramWorkflow:
    """Executes Instagram posting workflow step by step."""
    
    def __init__(self):
        self.capture = VNCCapture()
        self.vision = VisionFinder()
        self.input = InputInjector()
        
        self.current_step = InstagramStep.NAVIGATE_TO_INSTAGRAM
        self.max_retries = 3
        self.step_timeout = 30  # seconds
    
    def execute(self, content: PostContent) -> bool:
        """
        Execute full posting workflow.
        
        Args:
            content: What to post
            
        Returns:
            True if post succeeded
        """
        print(f"Starting Instagram post workflow")
        print(f"Media: {content.media_path}")
        print(f"Caption: {content.caption[:50]}...")
        
        while self.current_step != InstagramStep.DONE:
            success = self._execute_step(content)
            
            if not success:
                print(f"Step failed: {self.current_step.value}")
                return False
            
            # Brief pause between steps for stability
            time.sleep(1)
        
        print("Instagram post completed successfully!")
        return True
    
    def _execute_step(self, content: PostContent) -> bool:
        """Execute current step and advance to next."""
        step = self.current_step
        print(f"Executing step: {step.value}")
        
        for attempt in range(self.max_retries):
            try:
                if step == InstagramStep.NAVIGATE_TO_INSTAGRAM:
                    return self._step_navigate()
                
                elif step == InstagramStep.WAIT_FOR_PAGE_LOAD:
                    return self._step_wait_for_page()
                
                elif step == InstagramStep.CLICK_CREATE_POST:
                    return self._step_click_create()
                
                elif step == InstagramStep.WAIT_FOR_UPLOAD_DIALOG:
                    return self._step_wait_upload_dialog()
                
                elif step == InstagramStep.SELECT_MEDIA_FILE:
                    return self._step_select_media(content.media_path)
                
                elif step == InstagramStep.WAIT_FOR_MEDIA_LOAD:
                    return self._step_wait_media_load()
                
                elif step == InstagramStep.CLICK_NEXT_BUTTON:
                    return self._step_click_next()
                
                elif step == InstagramStep.WAIT_FOR_FILTER_PAGE:
                    return self._step_wait_filter_page()
                
                elif step == InstagramStep.CLICK_NEXT_AGAIN:
                    return self._step_click_next()
                
                elif step == InstagramStep.WAIT_FOR_CAPTION_PAGE:
                    return self._step_wait_caption_page()
                
                elif step == InstagramStep.ENTER_CAPTION:
                    return self._step_enter_caption(content.caption, content.hashtags)
                
                elif step == InstagramStep.CLICK_SHARE_BUTTON:
                    return self._step_click_share()
                
                elif step == InstagramStep.VERIFY_POST_SUCCESS:
                    return self._step_verify_success()
                
            except Exception as e:
                print(f"Step error (attempt {attempt + 1}): {e}")
                time.sleep(2)
        
        return False
    
    def _step_navigate(self) -> bool:
        """Navigate to Instagram in browser."""
        # Focus Chrome address bar
        self.input.press_key("l", ["ctrl"])
        time.sleep(0.3)
        
        # Type URL
        self.input.type_text("https://www.instagram.com/")
        time.sleep(0.2)
        
        # Press Enter
        self.input.press_key("enter")
        
        self.current_step = InstagramStep.WAIT_FOR_PAGE_LOAD
        return True
    
    def _step_wait_for_page(self) -> bool:
        """Wait for Instagram page to load."""
        start = time.time()
        
        while time.time() - start < self.step_timeout:
            screenshot = self.capture.capture()
            
            # Check if Instagram loaded (look for logo or create button)
            match, _ = self.vision.verify_state(
                screenshot, 
                "Instagram home page with navigation icons visible"
            )
            
            if match:
                self.current_step = InstagramStep.CLICK_CREATE_POST
                return True
            
            time.sleep(1)
        
        return False
    
    def _step_click_create(self) -> bool:
        """Click the Create/Plus button."""
        screenshot = self.capture.capture()
        
        # Find the create post button (plus icon)
        element = self.vision.find_element(
            screenshot,
            "Create new post button, plus sign icon in the left sidebar or top navigation"
        )
        
        if element:
            self.input.click(element.x, element.y)
            self.current_step = InstagramStep.WAIT_FOR_UPLOAD_DIALOG
            return True
        
        return False
    
    def _step_wait_upload_dialog(self) -> bool:
        """Wait for upload dialog to appear."""
        start = time.time()
        
        while time.time() - start < self.step_timeout:
            screenshot = self.capture.capture()
            
            match, _ = self.vision.verify_state(
                screenshot,
                "Create new post dialog with drag and drop area or Select from computer button"
            )
            
            if match:
                self.current_step = InstagramStep.SELECT_MEDIA_FILE
                return True
            
            time.sleep(1)
        
        return False
    
    def _step_select_media(self, media_path: str) -> bool:
        """Select media file to upload."""
        screenshot = self.capture.capture()
        
        # Find "Select from computer" button
        element = self.vision.find_element(
            screenshot,
            "Select from computer button, blue button to choose files"
        )
        
        if element:
            self.input.click(element.x, element.y)
            time.sleep(1)  # Wait for file dialog
            
            # Type the file path in the file dialog
            self.input.type_text(media_path)
            time.sleep(0.5)
            self.input.press_key("enter")
            
            self.current_step = InstagramStep.WAIT_FOR_MEDIA_LOAD
            return True
        
        return False
    
    def _step_wait_media_load(self) -> bool:
        """Wait for media to load in editor."""
        start = time.time()
        
        while time.time() - start < self.step_timeout:
            screenshot = self.capture.capture()
            
            match, _ = self.vision.verify_state(
                screenshot,
                "Image or video preview showing with Next button visible"
            )
            
            if match:
                self.current_step = InstagramStep.CLICK_NEXT_BUTTON
                return True
            
            time.sleep(1)
        
        return False
    
    def _step_click_next(self) -> bool:
        """Click Next button."""
        screenshot = self.capture.capture()
        
        element = self.vision.find_element(
            screenshot,
            "Next button, usually blue text in top right"
        )
        
        if element:
            self.input.click(element.x, element.y)
            
            # Advance based on current step
            if self.current_step == InstagramStep.CLICK_NEXT_BUTTON:
                self.current_step = InstagramStep.WAIT_FOR_FILTER_PAGE
            elif self.current_step == InstagramStep.CLICK_NEXT_AGAIN:
                self.current_step = InstagramStep.WAIT_FOR_CAPTION_PAGE
            
            return True
        
        return False
    
    def _step_wait_filter_page(self) -> bool:
        """Wait for filter/edit page."""
        time.sleep(2)  # Filters page usually loads quickly
        self.current_step = InstagramStep.CLICK_NEXT_AGAIN
        return True
    
    def _step_wait_caption_page(self) -> bool:
        """Wait for caption entry page."""
        start = time.time()
        
        while time.time() - start < self.step_timeout:
            screenshot = self.capture.capture()
            
            match, _ = self.vision.verify_state(
                screenshot,
                "Caption entry page with Write a caption text field and Share button"
            )
            
            if match:
                self.current_step = InstagramStep.ENTER_CAPTION
                return True
            
            time.sleep(1)
        
        return False
    
    def _step_enter_caption(self, caption: str, hashtags: list) -> bool:
        """Enter caption text."""
        screenshot = self.capture.capture()
        
        # Find caption input field
        element = self.vision.find_element(
            screenshot,
            "Write a caption text input area"
        )
        
        if element:
            self.input.click(element.x, element.y)
            time.sleep(0.3)
            
            # Type caption
            full_caption = caption
            if hashtags:
                full_caption += "\n\n" + " ".join(f"#{tag}" for tag in hashtags)
            
            self.input.type_text(full_caption)
            
            self.current_step = InstagramStep.CLICK_SHARE_BUTTON
            return True
        
        return False
    
    def _step_click_share(self) -> bool:
        """Click Share button to post."""
        screenshot = self.capture.capture()
        
        element = self.vision.find_element(
            screenshot,
            "Share button, blue button to publish the post"
        )
        
        if element:
            self.input.click(element.x, element.y)
            self.current_step = InstagramStep.VERIFY_POST_SUCCESS
            return True
        
        return False
    
    def _step_verify_success(self) -> bool:
        """Verify post was created successfully."""
        # Wait for posting to complete
        time.sleep(5)
        
        screenshot = self.capture.capture()
        
        match, explanation = self.vision.verify_state(
            screenshot,
            "Post was shared successfully, or returned to Instagram feed, or showing the new post"
        )
        
        if match:
            self.current_step = InstagramStep.DONE
            return True
        
        # Check for error state
        error_match, _ = self.vision.verify_state(
            screenshot,
            "Error message or posting failed notification"
        )
        
        if error_match:
            print(f"Post failed: {explanation}")
            return False
        
        # Assume success if no error detected
        self.current_step = InstagramStep.DONE
        return True
```

---

### 5. Main Orchestrator

Pulls everything together and processes the post queue.

```python
# src/main_orchestrator.py
"""Main orchestrator - processes post queue and dispatches to platform workflows."""
import requests
import time
from typing import Optional, Dict, Any
from datetime import datetime

from src.workflows.instagram import InstagramWorkflow, PostContent
# from src.workflows.facebook import FacebookWorkflow
# from src.workflows.tiktok import TikTokWorkflow
# from src.workflows.skool import SkoolWorkflow


class MainOrchestrator:
    """Orchestrates social media posting across all platforms."""
    
    def __init__(
        self,
        api_base_url: str = "https://social.sterlingcooley.com/api",
        poll_interval: int = 60
    ):
        """
        Initialize orchestrator.
        
        Args:
            api_base_url: Social Dashboard API URL
            poll_interval: Seconds between queue checks
        """
        self.api_url = api_base_url
        self.poll_interval = poll_interval
        
        # Platform workflows
        self.workflows = {
            "instagram": InstagramWorkflow(),
            # "facebook": FacebookWorkflow(),
            # "tiktok": TikTokWorkflow(),
            # "skool": SkoolWorkflow(),
        }
    
    def run(self):
        """Main loop - continuously process post queue."""
        print("Starting main orchestrator...")
        print(f"Polling {self.api_url} every {self.poll_interval} seconds")
        
        while True:
            try:
                self._process_queue()
            except Exception as e:
                print(f"Queue processing error: {e}")
            
            time.sleep(self.poll_interval)
    
    def _process_queue(self):
        """Check for and process pending posts."""
        # Fetch next pending post
        post = self._fetch_next_post()
        
        if not post:
            return
        
        print(f"\n{'='*50}")
        print(f"Processing post ID: {post['id']}")
        print(f"Platform: {post['platform']}")
        print(f"{'='*50}\n")
        
        # Get workflow for platform
        platform = post['platform'].lower()
        workflow = self.workflows.get(platform)
        
        if not workflow:
            print(f"No workflow for platform: {platform}")
            self._report_failure(post['id'], f"Unsupported platform: {platform}")
            return
        
        # Prepare content
        content = PostContent(
            media_path=post.get('media_path', ''),
            caption=post.get('caption', ''),
            hashtags=post.get('hashtags', [])
        )
        
        # Execute workflow
        try:
            success = workflow.execute(content)
            
            if success:
                self._report_success(post['id'])
            else:
                self._report_failure(post['id'], "Workflow failed")
                
        except Exception as e:
            self._report_failure(post['id'], str(e))
    
    def _fetch_next_post(self) -> Optional[Dict[str, Any]]:
        """Fetch next pending post from API."""
        try:
            response = requests.get(
                f"{self.api_url}/gui_post_queue/pending",
                timeout=10
            )
            
            if response.status_code == 200:
                posts = response.json()
                if posts and len(posts) > 0:
                    return posts[0]
            
        except Exception as e:
            print(f"API fetch error: {e}")
        
        return None
    
    def _report_success(self, post_id: str):
        """Report successful post to API."""
        try:
            requests.post(
                f"{self.api_url}/gui_post_queue/{post_id}/complete",
                json={"status": "success", "completed_at": datetime.now().isoformat()}
            )
            print(f"Reported success for post {post_id}")
        except Exception as e:
            print(f"Failed to report success: {e}")
    
    def _report_failure(self, post_id: str, reason: str):
        """Report failed post to API."""
        try:
            requests.post(
                f"{self.api_url}/gui_post_queue/{post_id}/failed",
                json={"status": "failed", "reason": reason}
            )
            print(f"Reported failure for post {post_id}: {reason}")
        except Exception as e:
            print(f"Failed to report failure: {e}")


if __name__ == "__main__":
    orchestrator = MainOrchestrator()
    orchestrator.run()
```

---

## Project Structure for Ubuntu Controller

```
/home/ubuntu/social-automation/
├── src/
│   ├── __init__.py
│   ├── vnc_capture.py          # VNC screenshot capture
│   ├── vision_finder.py        # Vision model element finding
│   ├── input_injector.py       # Mouse/keyboard to Windows
│   ├── main_orchestrator.py    # Main loop
│   └── workflows/
│       ├── __init__.py
│       ├── instagram.py        # Instagram posting steps
│       ├── facebook.py         # Facebook posting steps
│       ├── tiktok.py           # TikTok posting steps
│       └── skool.py            # Skool posting steps
├── config/
│   └── settings.yaml           # Configuration
├── tests/
│   ├── test_vnc_capture.py
│   ├── test_vision_finder.py
│   └── test_workflows.py
├── logs/
│   └── orchestrator.log
└── requirements.txt
```

---

## Key Principles

1. **Python decides, Vision sees** - All logic about what to do next is in Python code. Vision only answers "where is X" and "is this screen showing Y".

2. **Deterministic workflows** - Each platform has a step-by-step workflow with explicit state transitions. No AI "deciding" what step comes next.

3. **Retry with vision** - If a click doesn't work, take a new screenshot and try to find the element again. Vision handles dynamic UI.

4. **Fail fast, report clearly** - If a step fails after retries, stop and report. Don't try to "figure out" what went wrong with AI reasoning.

5. **One thing at a time** - Process one post completely before starting the next. Simpler to debug.

---

## Dependencies

```
# requirements.txt
ollama>=0.1.0          # Vision model API
Pillow>=10.0.0         # Image handling
requests>=2.31.0       # HTTP client
pyyaml>=6.0.0          # Configuration
vncdotool>=1.0.0       # VNC client (or alternative)
```

---

## Next Steps

1. **Implement VNC capture** - Get reliable screenshots from Windows 10 VM
2. **Test vision finder** - Verify Qwen2.5-VL can find UI elements accurately
3. **Build input injector** - Ensure commands reach Windows 10 via Proxmox
4. **Complete Instagram workflow** - All steps with proper error handling
5. **Add remaining platforms** - Facebook, TikTok, Skool workflows
6. **Integration testing** - End-to-end post flow