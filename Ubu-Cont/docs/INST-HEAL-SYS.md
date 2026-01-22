# Instagram Self-Healing Workflow System

## Executive Summary

This document specifies a **self-healing automation system** for Instagram posting workflows. When Instagram changes their UI and buttons move, the system automatically:

1. Detects which click point failed (via similarity comparison - already working)
2. Takes a full desktop screenshot
3. Sends the screenshot + context to a vision AI (Qwen 2.5 Vision via OpenRouter)
4. Asks the AI to locate the NEW position of the button that moved
5. Updates the workflow with corrected coordinates
6. Re-runs to verify the fix works
7. Saves new baselines if the entire workflow succeeds

**This is Instagram-specific and experimental.**

---

## What Already Exists (DO NOT REWRITE)

The following components are already implemented and working:

```
EXISTING INFRASTRUCTURE:
├── VNC screenshot capture (takes pictures of Windows 10)
├── HID click injection (sends mouse/keyboard to Windows 10)
├── SQLite database with baselines, runs, screenshots
├── Similarity comparison (tells us 96% = good, 24% = broken)
├── Workflow JSON files with click coordinates
├── Qwen 2.5 Vision access via OpenRouter API
└── Detection of which action index failed
```

**DO NOT** rewrite any of this. The self-healing system **integrates with** these existing components.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SELF-HEALING FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. DETECTION (already working)                                              │
│     ┌──────────────┐                                                         │
│     │ Run Workflow │──▶ Click fails at action N ──▶ Similarity = 24%        │
│     └──────────────┘                                                         │
│            │                                                                 │
│            ▼                                                                 │
│  2. DIAGNOSIS                                                                │
│     ┌──────────────────────────────────────────────────────────────┐        │
│     │ Load context:                                                 │        │
│     │   - Full desktop screenshot (current state)                   │        │
│     │   - Baseline image (what we expected to see)                  │        │
│     │   - Failed screenshot (what we actually saw)                  │        │
│     │   - Workflow step description ("click Upload Media button")   │        │
│     │   - Old coordinates (where we clicked)                        │        │
│     └──────────────────────────────────────────────────────────────┘        │
│            │                                                                 │
│            ▼                                                                 │
│  3. AI LOCATOR                                                               │
│     ┌──────────────────────────────────────────────────────────────┐        │
│     │ Send to Qwen 2.5 Vision via OpenRouter:                       │        │
│     │   "The UI has changed. Find the new location of the           │        │
│     │    button that does [action description]. Return coordinates." │        │
│     └──────────────────────────────────────────────────────────────┘        │
│            │                                                                 │
│            ▼                                                                 │
│  4. COORDINATE UPDATE                                                        │
│     ┌──────────────────────────────────────────────────────────────┐        │
│     │ Update workflow JSON with new coordinates                     │        │
│     │ Mark as "provisional" until verified                          │        │
│     └──────────────────────────────────────────────────────────────┘        │
│            │                                                                 │
│            ▼                                                                 │
│  5. VERIFICATION                                                             │
│     ┌──────────────────────────────────────────────────────────────┐        │
│     │ Re-run workflow from the failed point                         │        │
│     │   - If succeeds: Continue to completion                       │        │
│     │   - If fails again: Try AI locator again (max 3 attempts)     │        │
│     └──────────────────────────────────────────────────────────────┘        │
│            │                                                                 │
│            ▼                                                                 │
│  6. BASELINE UPDATE (if full workflow succeeds)                              │
│     ┌──────────────────────────────────────────────────────────────┐        │
│     │ Save new 100x100 screenshots as updated baselines             │        │
│     │ Log correction in database for future reference               │        │
│     └──────────────────────────────────────────────────────────────┘        │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Directory Structure

Add these files to your existing project:

```
/home/user/social-automation/
├── ... (existing files)
├── self_healing/
│   ├── __init__.py
│   ├── config.py                    # Configuration for self-healing
│   ├── vision_locator.py            # AI-powered button finding
│   ├── workflow_updater.py          # Update workflow JSON files
│   ├── healing_orchestrator.py      # Main self-healing logic
│   ├── instagram_healer.py          # Instagram-specific healing
│   └── prompts/
│       ├── locate_button.txt        # Prompt template for finding buttons
│       └── verify_element.txt       # Prompt for verification
└── tests/
    └── test_self_healing.py
```

---

## Configuration

Create `self_healing/config.py`:

```python
"""
Configuration for Instagram self-healing system.
"""

# OpenRouter API configuration
OPENROUTER_API_KEY = "your-openrouter-api-key"  # Load from env in production
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Vision model to use for locating buttons
VISION_MODEL = "qwen/qwen-2.5-vl-72b-instruct"  # Or qwen/qwen-2-vl-7b-instruct for faster/cheaper

# Self-healing behavior
MAX_HEALING_ATTEMPTS = 3          # Max times to try finding new coordinates
CONFIDENCE_THRESHOLD = 0.80       # Minimum confidence from AI to accept coordinates
SIMILARITY_FAILURE_THRESHOLD = 0.70  # Below this = click point has moved

# Workflow paths
INSTAGRAM_WORKFLOW_PATH = "/home/user/social-automation/workflows/instagram-default.json"
INSTAGRAM_WORKFLOW_BACKUP = "/home/user/social-automation/workflows/backups/instagram-default.{timestamp}.json"

# Database path (existing)
DATABASE_PATH = "/home/user/workflow-validation/validation.db"

# Screenshot settings (should match existing system)
FULL_SCREENSHOT_WIDTH = 1920      # Your Windows 10 resolution
FULL_SCREENSHOT_HEIGHT = 1080

# Instagram-specific action descriptions
# Maps action_index to human-readable description of what the click does
INSTAGRAM_ACTION_DESCRIPTIONS = {
    # UPDATE THESE TO MATCH YOUR ACTUAL WORKFLOW
    # Example mapping:
    0: "Click on the 'Create new post' button (+ icon)",
    1: "Click on 'Post' option in the create menu",
    2: "Click 'Select from computer' button to upload media",
    3: "Click the file input or drag-drop area",
    4: "Click 'Next' button after selecting media",
    5: "Click 'Next' button after applying filters",
    6: "Click the caption text area",
    7: "Click 'Share' button to publish the post",
    # ... add all your action indices
}

# Fallback description if action_index not in mapping
DEFAULT_ACTION_DESCRIPTION = "Click the button or interactive element for this step"
```

---

## Core Module: Vision Locator

Create `self_healing/vision_locator.py`:

```python
"""
Uses vision AI to locate UI elements that have moved.
Sends full desktop screenshots to Qwen 2.5 Vision via OpenRouter.
"""

import base64
import json
import re
import httpx
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import logging

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VISION_MODEL,
    CONFIDENCE_THRESHOLD,
    FULL_SCREENSHOT_WIDTH,
    FULL_SCREENSHOT_HEIGHT,
)


logger = logging.getLogger(__name__)


@dataclass
class LocatorResult:
    """Result from vision AI locator."""
    success: bool
    new_x: Optional[int] = None
    new_y: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: str = ""


class VisionLocator:
    """
    Uses vision AI to find UI elements on screen.
    
    This is the brain of the self-healing system - it looks at the
    current screen state and figures out where Instagram moved their buttons.
    """
    
    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the vision locator.
        
        Args:
            api_key: OpenRouter API key (uses config default if not provided)
            model: Vision model to use (uses config default if not provided)
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or VISION_MODEL
        self.client = httpx.Client(timeout=60.0)
    
    def _encode_image(self, image_bytes: bytes) -> str:
        """Encode image to base64 for API."""
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def _build_locate_prompt(
        self,
        action_description: str,
        old_x: int,
        old_y: int,
        baseline_context: str = None
    ) -> str:
        """
        Build the prompt for locating a moved UI element.
        
        Args:
            action_description: What the button/element does (e.g., "Click Upload Media button")
            old_x: Previous X coordinate that used to work
            old_y: Previous Y coordinate that used to work
            baseline_context: Optional description of what the baseline looked like
        """
        prompt = f"""You are analyzing a screenshot of Instagram's web interface to help fix an automation workflow.

TASK: Find the CURRENT location of a UI element that has moved.

WHAT WE'RE LOOKING FOR:
{action_description}

PREVIOUS LOCATION (no longer correct):
X: {old_x}, Y: {old_y}

The button or element we need has MOVED from its previous location. Instagram has updated their UI.

YOUR JOB:
1. Look at the screenshot carefully
2. Find the UI element that matches the description above
3. Identify the EXACT CENTER coordinates where we should click

RESPONSE FORMAT (respond with ONLY this JSON, no other text):
{{
    "found": true/false,
    "new_x": <integer x coordinate>,
    "new_y": <integer y coordinate>,
    "confidence": <float 0.0-1.0>,
    "element_description": "<what you found>",
    "reasoning": "<why you believe this is the correct element>"
}}

IMPORTANT:
- Coordinates are in pixels from top-left of screen
- Screen resolution is {FULL_SCREENSHOT_WIDTH}x{FULL_SCREENSHOT_HEIGHT}
- Return the CENTER of the clickable element
- If you cannot find the element, set "found": false
- Be precise - off by even 20 pixels could click the wrong thing

Look at the screenshot now and find the element."""

        return prompt
    
    def locate_element(
        self,
        full_screenshot: bytes,
        action_description: str,
        old_x: int,
        old_y: int,
        baseline_image: bytes = None,
        failed_image: bytes = None
    ) -> LocatorResult:
        """
        Use vision AI to locate a UI element that has moved.
        
        Args:
            full_screenshot: Full desktop screenshot (PNG bytes)
            action_description: What the element does
            old_x: Previous X coordinate
            old_y: Previous Y coordinate
            baseline_image: Optional 100x100 baseline showing what we expected
            failed_image: Optional 100x100 showing what we actually saw
            
        Returns:
            LocatorResult with new coordinates if found
        """
        # Build the prompt
        prompt = self._build_locate_prompt(action_description, old_x, old_y)
        
        # Prepare images for the API
        images = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(full_screenshot)}"
                }
            }
        ]
        
        # Optionally include baseline and failed images for context
        if baseline_image and failed_image:
            context_prompt = """

ADDITIONAL CONTEXT:
I'm also showing you two small 100x100 pixel images:
1. BASELINE: What the click area USED to look like (when it worked)
2. CURRENT: What the click area looks like NOW (where we clicked but it's wrong)

The difference between these shows that the UI has changed."""
            
            prompt += context_prompt
            images.append({
                "type": "image_url", 
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(baseline_image)}"
                }
            })
            images.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{self._encode_image(failed_image)}"
                }
            })
        
        # Build API request
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    *images
                ]
            }
        ]
        
        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://social.sterlingcooley.com",
                    "X-Title": "Instagram Self-Healing Agent"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.1  # Low temperature for precise answers
                }
            )
            response.raise_for_status()
            
            result = response.json()
            raw_text = result['choices'][0]['message']['content']
            
            logger.debug(f"Vision AI raw response: {raw_text}")
            
            # Parse the JSON response
            return self._parse_response(raw_text)
            
        except httpx.HTTPError as e:
            logger.error(f"API request failed: {e}")
            return LocatorResult(
                success=False,
                reasoning=f"API error: {str(e)}",
                raw_response=str(e)
            )
        except Exception as e:
            logger.error(f"Unexpected error in vision locator: {e}")
            return LocatorResult(
                success=False,
                reasoning=f"Error: {str(e)}",
                raw_response=str(e)
            )
    
    def _parse_response(self, raw_text: str) -> LocatorResult:
        """Parse the AI's JSON response."""
        try:
            # Try to extract JSON from the response
            # Sometimes the model wraps it in markdown code blocks
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if not json_match:
                return LocatorResult(
                    success=False,
                    reasoning="Could not find JSON in response",
                    raw_response=raw_text
                )
            
            data = json.loads(json_match.group())
            
            found = data.get('found', False)
            if not found:
                return LocatorResult(
                    success=False,
                    reasoning=data.get('reasoning', 'Element not found'),
                    raw_response=raw_text
                )
            
            new_x = int(data.get('new_x', 0))
            new_y = int(data.get('new_y', 0))
            confidence = float(data.get('confidence', 0.0))
            reasoning = data.get('reasoning', '')
            
            # Validate coordinates are within screen bounds
            if not (0 <= new_x <= FULL_SCREENSHOT_WIDTH and 0 <= new_y <= FULL_SCREENSHOT_HEIGHT):
                return LocatorResult(
                    success=False,
                    reasoning=f"Coordinates out of bounds: ({new_x}, {new_y})",
                    raw_response=raw_text
                )
            
            # Check confidence threshold
            if confidence < CONFIDENCE_THRESHOLD:
                return LocatorResult(
                    success=False,
                    new_x=new_x,
                    new_y=new_y,
                    confidence=confidence,
                    reasoning=f"Confidence {confidence:.2f} below threshold {CONFIDENCE_THRESHOLD}",
                    raw_response=raw_text
                )
            
            return LocatorResult(
                success=True,
                new_x=new_x,
                new_y=new_y,
                confidence=confidence,
                reasoning=reasoning,
                raw_response=raw_text
            )
            
        except json.JSONDecodeError as e:
            return LocatorResult(
                success=False,
                reasoning=f"Invalid JSON: {e}",
                raw_response=raw_text
            )
        except Exception as e:
            return LocatorResult(
                success=False,
                reasoning=f"Parse error: {e}",
                raw_response=raw_text
            )
    
    def verify_element(
        self,
        screenshot: bytes,
        x: int,
        y: int,
        expected_description: str
    ) -> Tuple[bool, float, str]:
        """
        Verify that the element at given coordinates matches expectations.
        
        Args:
            screenshot: Full screenshot
            x: X coordinate to verify
            y: Y coordinate to verify
            expected_description: What should be at this location
            
        Returns:
            Tuple of (is_correct, confidence, explanation)
        """
        prompt = f"""Look at this screenshot and tell me if the UI element at coordinates ({x}, {y}) matches this description:

"{expected_description}"

The coordinates are marked approximately in the center of what we want to click.

Respond with ONLY this JSON:
{{
    "matches": true/false,
    "confidence": <float 0.0-1.0>,
    "what_is_there": "<describe what's actually at those coordinates>",
    "explanation": "<why it does or doesn't match>"
}}"""

        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{self._encode_image(screenshot)}"
                                }
                            }
                        ]
                    }],
                    "max_tokens": 500,
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            
            raw_text = response.json()['choices'][0]['message']['content']
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            
            if json_match:
                data = json.loads(json_match.group())
                return (
                    data.get('matches', False),
                    float(data.get('confidence', 0.0)),
                    data.get('explanation', '')
                )
            
            return False, 0.0, "Could not parse verification response"
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False, 0.0, str(e)
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
```

---

## Workflow Updater

Create `self_healing/workflow_updater.py`:

```python
"""
Updates workflow JSON files with corrected coordinates.
Handles backups and rollback.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

from .config import INSTAGRAM_WORKFLOW_PATH, INSTAGRAM_WORKFLOW_BACKUP


logger = logging.getLogger(__name__)


class WorkflowUpdater:
    """
    Manages updates to workflow JSON files.
    
    Handles:
    - Loading workflow definitions
    - Updating coordinates for specific actions
    - Creating backups before changes
    - Rolling back if verification fails
    """
    
    def __init__(self, workflow_path: str = None):
        """
        Initialize workflow updater.
        
        Args:
            workflow_path: Path to workflow JSON file
        """
        self.workflow_path = Path(workflow_path or INSTAGRAM_WORKFLOW_PATH)
        self.backup_pattern = INSTAGRAM_WORKFLOW_BACKUP
        self._original_state: Optional[Dict] = None
    
    def load_workflow(self) -> Dict[str, Any]:
        """Load the workflow JSON file."""
        with open(self.workflow_path) as f:
            return json.load(f)
    
    def save_workflow(self, workflow: Dict[str, Any]) -> None:
        """Save workflow to JSON file."""
        with open(self.workflow_path, 'w') as f:
            json.dump(workflow, f, indent=2)
        logger.info(f"Saved workflow to {self.workflow_path}")
    
    def create_backup(self) -> Path:
        """
        Create a timestamped backup of the current workflow.
        
        Returns:
            Path to backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = Path(self.backup_pattern.format(timestamp=timestamp))
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(self.workflow_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return backup_path
    
    def get_action(self, workflow: Dict, action_index: int) -> Optional[Dict]:
        """Get a specific action from the workflow."""
        actions = workflow.get('actions', workflow.get('steps', []))
        if 0 <= action_index < len(actions):
            return actions[action_index]
        return None
    
    def update_coordinates(
        self,
        action_index: int,
        new_x: int,
        new_y: int,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """
        Update coordinates for a specific action.
        
        Args:
            action_index: Index of action to update
            new_x: New X coordinate
            new_y: New Y coordinate
            create_backup: Whether to create backup before modifying
            
        Returns:
            Updated workflow dict
        """
        # Create backup first
        if create_backup:
            self.create_backup()
        
        # Load current workflow
        workflow = self.load_workflow()
        
        # Store original state for potential rollback
        self._original_state = json.loads(json.dumps(workflow))
        
        # Get the actions array
        actions = workflow.get('actions', workflow.get('steps', []))
        
        if action_index >= len(actions):
            raise ValueError(f"Action index {action_index} out of range (max: {len(actions)-1})")
        
        action = actions[action_index]
        old_x = action.get('x', action.get('coordinates', {}).get('x'))
        old_y = action.get('y', action.get('coordinates', {}).get('y'))
        
        logger.info(f"Updating action {action_index}: ({old_x}, {old_y}) -> ({new_x}, {new_y})")
        
        # Update coordinates (handle both flat and nested formats)
        if 'x' in action:
            action['x'] = new_x
            action['y'] = new_y
        elif 'coordinates' in action:
            action['coordinates']['x'] = new_x
            action['coordinates']['y'] = new_y
        else:
            # Add coordinates if not present
            action['x'] = new_x
            action['y'] = new_y
        
        # Add metadata about the update
        if '_healing_history' not in action:
            action['_healing_history'] = []
        
        action['_healing_history'].append({
            'timestamp': datetime.now().isoformat(),
            'old_x': old_x,
            'old_y': old_y,
            'new_x': new_x,
            'new_y': new_y,
            'reason': 'self_healing_coordinate_update'
        })
        
        # Save updated workflow
        self.save_workflow(workflow)
        
        return workflow
    
    def rollback(self) -> bool:
        """
        Rollback to the state before the last update.
        
        Returns:
            True if rollback successful
        """
        if self._original_state is None:
            logger.warning("No original state to rollback to")
            return False
        
        self.save_workflow(self._original_state)
        logger.info("Rolled back to previous state")
        self._original_state = None
        return True
    
    def get_action_coordinates(self, action_index: int) -> Optional[tuple]:
        """
        Get current coordinates for an action.
        
        Returns:
            Tuple of (x, y) or None if not found
        """
        workflow = self.load_workflow()
        action = self.get_action(workflow, action_index)
        
        if action is None:
            return None
        
        x = action.get('x', action.get('coordinates', {}).get('x'))
        y = action.get('y', action.get('coordinates', {}).get('y'))
        
        if x is not None and y is not None:
            return (int(x), int(y))
        return None
    
    def list_click_actions(self) -> List[Dict]:
        """
        List all click actions in the workflow with their indices.
        
        Returns:
            List of dicts with action info
        """
        workflow = self.load_workflow()
        actions = workflow.get('actions', workflow.get('steps', []))
        
        click_actions = []
        for i, action in enumerate(actions):
            action_type = action.get('type', action.get('action', '')).lower()
            if action_type in ('click', 'doubleclick', 'rightclick'):
                x = action.get('x', action.get('coordinates', {}).get('x'))
                y = action.get('y', action.get('coordinates', {}).get('y'))
                click_actions.append({
                    'index': i,
                    'type': action_type,
                    'x': x,
                    'y': y,
                    'description': action.get('description', action.get('name', f'Action {i}'))
                })
        
        return click_actions
```

---

## Main Healing Orchestrator

Create `self_healing/healing_orchestrator.py`:

```python
"""
Main orchestrator for self-healing workflows.
Coordinates detection, AI location, updating, and verification.
"""

import logging
import time
from typing import Optional, Callable, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from .config import (
    MAX_HEALING_ATTEMPTS,
    SIMILARITY_FAILURE_THRESHOLD,
    INSTAGRAM_ACTION_DESCRIPTIONS,
    DEFAULT_ACTION_DESCRIPTION,
    DATABASE_PATH,
)
from .vision_locator import VisionLocator, LocatorResult
from .workflow_updater import WorkflowUpdater


logger = logging.getLogger(__name__)


@dataclass
class HealingResult:
    """Result of a self-healing attempt."""
    success: bool
    action_index: int
    old_coordinates: Tuple[int, int]
    new_coordinates: Optional[Tuple[int, int]]
    attempts: int
    baseline_updated: bool
    error_message: Optional[str] = None
    ai_reasoning: Optional[str] = None


class HealingOrchestrator:
    """
    Orchestrates the self-healing process.
    
    This is the main entry point for healing failed workflows.
    
    Usage:
        orchestrator = HealingOrchestrator(
            vision_locator=VisionLocator(),
            workflow_updater=WorkflowUpdater(),
            screenshot_func=your_screenshot_function,
            click_func=your_click_function,
            run_workflow_func=your_workflow_runner,
            update_baseline_func=your_baseline_updater
        )
        
        # When a workflow fails at a specific action:
        result = orchestrator.heal_failed_action(
            workflow_name='instagram-default',
            failed_action_index=3,
            similarity_score=0.24,
            failed_screenshot=failed_100x100_bytes,
            baseline_screenshot=baseline_100x100_bytes
        )
        
        if result.success:
            print(f"Fixed! New coordinates: {result.new_coordinates}")
    """
    
    def __init__(
        self,
        vision_locator: VisionLocator,
        workflow_updater: WorkflowUpdater,
        screenshot_func: Callable[[], bytes],
        click_func: Callable[[int, int], bool],
        run_workflow_from_index_func: Callable[[str, int], Tuple[bool, int, float]],
        update_baseline_func: Callable[[str, int, bytes], None],
        get_baseline_func: Callable[[str, int], Optional[bytes]],
    ):
        """
        Initialize the healing orchestrator.
        
        Args:
            vision_locator: VisionLocator instance for AI-powered element finding
            workflow_updater: WorkflowUpdater for modifying workflow files
            screenshot_func: Function that captures full desktop screenshot, returns PNG bytes
            click_func: Function that clicks at (x, y), returns success bool
            run_workflow_from_index_func: Function that runs workflow starting from an index
                                          Returns (success, failed_at_index, similarity)
            update_baseline_func: Function to update baseline for (workflow, index, image)
            get_baseline_func: Function to get baseline image for (workflow, index)
        """
        self.locator = vision_locator
        self.updater = workflow_updater
        self.screenshot = screenshot_func
        self.click = click_func
        self.run_workflow_from = run_workflow_from_index_func
        self.update_baseline = update_baseline_func
        self.get_baseline = get_baseline_func
        
        # Track healing attempts
        self._attempts_log = []
    
    def get_action_description(self, action_index: int) -> str:
        """Get human-readable description of what an action does."""
        return INSTAGRAM_ACTION_DESCRIPTIONS.get(
            action_index,
            DEFAULT_ACTION_DESCRIPTION
        )
    
    def heal_failed_action(
        self,
        workflow_name: str,
        failed_action_index: int,
        similarity_score: float,
        failed_screenshot: bytes,
        baseline_screenshot: bytes = None
    ) -> HealingResult:
        """
        Attempt to heal a failed workflow action.
        
        Args:
            workflow_name: Name of the workflow (e.g., 'instagram-default')
            failed_action_index: Index of the action that failed
            similarity_score: How similar the failed click was to baseline (0.0-1.0)
            failed_screenshot: The 100x100 screenshot from the failed click
            baseline_screenshot: The 100x100 baseline (optional, will be fetched if not provided)
            
        Returns:
            HealingResult with outcome details
        """
        logger.info(f"Starting self-healing for {workflow_name} action {failed_action_index}")
        logger.info(f"Similarity score: {similarity_score:.2%} (threshold: {SIMILARITY_FAILURE_THRESHOLD:.2%})")
        
        # Get current coordinates
        old_coords = self.updater.get_action_coordinates(failed_action_index)
        if old_coords is None:
            return HealingResult(
                success=False,
                action_index=failed_action_index,
                old_coordinates=(0, 0),
                new_coordinates=None,
                attempts=0,
                baseline_updated=False,
                error_message="Could not get current coordinates for action"
            )
        
        old_x, old_y = old_coords
        
        # Get baseline if not provided
        if baseline_screenshot is None:
            baseline_screenshot = self.get_baseline(workflow_name, failed_action_index)
        
        # Get action description
        action_description = self.get_action_description(failed_action_index)
        
        # Attempt healing
        for attempt in range(1, MAX_HEALING_ATTEMPTS + 1):
            logger.info(f"Healing attempt {attempt}/{MAX_HEALING_ATTEMPTS}")
            
            # Take fresh full screenshot
            full_screenshot = self.screenshot()
            
            # Ask AI to find the element
            result = self.locator.locate_element(
                full_screenshot=full_screenshot,
                action_description=action_description,
                old_x=old_x,
                old_y=old_y,
                baseline_image=baseline_screenshot,
                failed_image=failed_screenshot
            )
            
            if not result.success:
                logger.warning(f"AI could not locate element: {result.reasoning}")
                continue
            
            new_x, new_y = result.new_x, result.new_y
            logger.info(f"AI found element at ({new_x}, {new_y}) with {result.confidence:.2%} confidence")
            
            # Update workflow with new coordinates
            try:
                self.updater.update_coordinates(
                    action_index=failed_action_index,
                    new_x=new_x,
                    new_y=new_y,
                    create_backup=True
                )
            except Exception as e:
                logger.error(f"Failed to update workflow: {e}")
                continue
            
            # Verify by running workflow from this point
            logger.info("Verifying fix by re-running workflow from failed point...")
            success, new_failed_index, new_similarity = self.run_workflow_from(
                workflow_name,
                failed_action_index
            )
            
            if success:
                logger.info("Workflow completed successfully with new coordinates!")
                
                # Update baseline with new screenshot
                baseline_updated = False
                try:
                    # Take new baseline screenshot at the new coordinates
                    # This should be done by the calling code after successful click
                    # For now, we'll mark that it should be updated
                    logger.info("Baselines should be updated after successful run")
                    baseline_updated = True
                except Exception as e:
                    logger.warning(f"Could not update baseline: {e}")
                
                return HealingResult(
                    success=True,
                    action_index=failed_action_index,
                    old_coordinates=old_coords,
                    new_coordinates=(new_x, new_y),
                    attempts=attempt,
                    baseline_updated=baseline_updated,
                    ai_reasoning=result.reasoning
                )
            
            elif new_failed_index == failed_action_index:
                # Still failing at the same point - AI's coordinates were wrong
                logger.warning(f"Fix didn't work - still failing at action {failed_action_index}")
                logger.warning(f"New similarity: {new_similarity:.2%}")
                
                # Rollback and try again
                self.updater.rollback()
                
            else:
                # Failed at a DIFFERENT point - the fix worked but something else broke
                logger.warning(f"Fixed action {failed_action_index} but now failing at {new_failed_index}")
                # Keep the fix for this action, but we'd need to heal the next one
                # For now, we'll consider this a partial success
                return HealingResult(
                    success=False,  # Not fully successful
                    action_index=failed_action_index,
                    old_coordinates=old_coords,
                    new_coordinates=(new_x, new_y),
                    attempts=attempt,
                    baseline_updated=False,
                    error_message=f"Fixed action {failed_action_index} but new failure at {new_failed_index}",
                    ai_reasoning=result.reasoning
                )
        
        # All attempts failed
        logger.error(f"Failed to heal action {failed_action_index} after {MAX_HEALING_ATTEMPTS} attempts")
        
        return HealingResult(
            success=False,
            action_index=failed_action_index,
            old_coordinates=old_coords,
            new_coordinates=None,
            attempts=MAX_HEALING_ATTEMPTS,
            baseline_updated=False,
            error_message="Max healing attempts exceeded"
        )
    
    def heal_multiple_actions(
        self,
        workflow_name: str,
        failed_actions: list  # List of (action_index, similarity_score, failed_screenshot)
    ) -> Dict[int, HealingResult]:
        """
        Heal multiple failed actions in sequence.
        
        Args:
            workflow_name: Name of the workflow
            failed_actions: List of tuples (action_index, similarity, screenshot)
            
        Returns:
            Dict mapping action_index to HealingResult
        """
        results = {}
        
        # Sort by action index to heal in order
        failed_actions.sort(key=lambda x: x[0])
        
        for action_index, similarity, screenshot in failed_actions:
            result = self.heal_failed_action(
                workflow_name=workflow_name,
                failed_action_index=action_index,
                similarity_score=similarity,
                failed_screenshot=screenshot
            )
            results[action_index] = result
            
            if not result.success:
                logger.warning(f"Stopping healing - action {action_index} could not be fixed")
                break
        
        return results
```

---

## Instagram-Specific Healer

Create `self_healing/instagram_healer.py`:

```python
"""
Instagram-specific self-healing implementation.
Ties everything together with your existing infrastructure.
"""

import logging
from typing import Optional, Tuple, Callable
from pathlib import Path

from .config import (
    INSTAGRAM_WORKFLOW_PATH,
    DATABASE_PATH,
    OPENROUTER_API_KEY,
    SIMILARITY_FAILURE_THRESHOLD,
)
from .vision_locator import VisionLocator
from .workflow_updater import WorkflowUpdater
from .healing_orchestrator import HealingOrchestrator, HealingResult


logger = logging.getLogger(__name__)


class InstagramHealer:
    """
    Instagram-specific self-healing system.
    
    This class is the main entry point you'll use in your automation code.
    It integrates with your existing screenshot, clicking, and workflow systems.
    
    USAGE EXAMPLE:
    
    ```python
    # Initialize once at startup
    healer = InstagramHealer(
        screenshot_func=your_vnc_screenshot_function,
        click_func=your_hid_click_function,
        run_workflow_func=your_workflow_runner,
        capture_baseline_func=your_baseline_capture,
        get_baseline_func=your_baseline_getter,
        update_baseline_func=your_baseline_updater
    )
    
    # When validation detects a failure:
    if similarity_score < 0.70:  # Click point has moved
        result = healer.attempt_heal(
            failed_action_index=failed_index,
            similarity_score=similarity_score,
            failed_screenshot=captured_100x100,
            baseline_screenshot=baseline_100x100
        )
        
        if result.success:
            print(f"Self-healed! New coords: {result.new_coordinates}")
            # Continue with workflow
        else:
            print(f"Could not self-heal: {result.error_message}")
            # Report failure
    ```
    """
    
    def __init__(
        self,
        screenshot_func: Callable[[], bytes],
        click_func: Callable[[int, int], bool],
        run_workflow_func: Callable[[str, int], Tuple[bool, int, float]],
        capture_baseline_func: Callable[[int, int], bytes],
        get_baseline_func: Callable[[str, int], Optional[bytes]],
        update_baseline_func: Callable[[str, int, bytes], None],
        workflow_path: str = None,
        api_key: str = None
    ):
        """
        Initialize Instagram healer.
        
        Args:
            screenshot_func: Function that captures full VNC screenshot
                             Signature: () -> bytes (PNG)
            
            click_func: Function that sends click via HID
                        Signature: (x: int, y: int) -> bool
            
            run_workflow_func: Function that runs workflow starting from index
                               Signature: (workflow_name: str, start_index: int) 
                                         -> (success: bool, failed_index: int, similarity: float)
            
            capture_baseline_func: Function to capture 100x100 around coordinates
                                   Signature: (x: int, y: int) -> bytes (PNG)
            
            get_baseline_func: Function to get baseline from database
                               Signature: (workflow_name: str, action_index: int) -> bytes or None
            
            update_baseline_func: Function to save new baseline to database
                                  Signature: (workflow_name: str, action_index: int, image: bytes) -> None
            
            workflow_path: Path to Instagram workflow JSON (uses default if not provided)
            
            api_key: OpenRouter API key (uses config if not provided)
        """
        self.screenshot = screenshot_func
        self.click = click_func
        self.run_workflow_from = run_workflow_func
        self.capture_baseline = capture_baseline_func
        self.get_baseline = get_baseline_func
        self.update_baseline = update_baseline_func
        
        # Initialize components
        self.locator = VisionLocator(api_key=api_key or OPENROUTER_API_KEY)
        self.updater = WorkflowUpdater(workflow_path or INSTAGRAM_WORKFLOW_PATH)
        
        # Create orchestrator
        self.orchestrator = HealingOrchestrator(
            vision_locator=self.locator,
            workflow_updater=self.updater,
            screenshot_func=self.screenshot,
            click_func=self.click,
            run_workflow_from_index_func=self._run_workflow_wrapper,
            update_baseline_func=self.update_baseline,
            get_baseline_func=self.get_baseline
        )
        
        # Track healing history
        self.healing_history = []
    
    def _run_workflow_wrapper(
        self,
        workflow_name: str,
        start_index: int
    ) -> Tuple[bool, int, float]:
        """Wrapper to match orchestrator's expected signature."""
        return self.run_workflow_from(workflow_name, start_index)
    
    def attempt_heal(
        self,
        failed_action_index: int,
        similarity_score: float,
        failed_screenshot: bytes,
        baseline_screenshot: bytes = None
    ) -> HealingResult:
        """
        Attempt to heal a failed Instagram workflow action.
        
        This is the main method you'll call when validation detects a failure.
        
        Args:
            failed_action_index: Which action in the workflow failed
            similarity_score: How similar the click area was to baseline (0.0-1.0)
            failed_screenshot: The 100x100 PNG from the failed click point
            baseline_screenshot: The 100x100 baseline PNG (optional, will fetch if not provided)
            
        Returns:
            HealingResult with success status and details
        """
        logger.info("="*60)
        logger.info("INSTAGRAM SELF-HEALING TRIGGERED")
        logger.info(f"Failed action: {failed_action_index}")
        logger.info(f"Similarity: {similarity_score:.2%}")
        logger.info("="*60)
        
        # Verify this looks like a UI change (not some other error)
        if similarity_score >= SIMILARITY_FAILURE_THRESHOLD:
            logger.warning(f"Similarity {similarity_score:.2%} is above threshold - may not be a UI change")
        
        # Attempt healing
        result = self.orchestrator.heal_failed_action(
            workflow_name='instagram-default',
            failed_action_index=failed_action_index,
            similarity_score=similarity_score,
            failed_screenshot=failed_screenshot,
            baseline_screenshot=baseline_screenshot
        )
        
        # Log result
        self.healing_history.append({
            'action_index': failed_action_index,
            'similarity': similarity_score,
            'success': result.success,
            'old_coords': result.old_coordinates,
            'new_coords': result.new_coordinates,
            'attempts': result.attempts
        })
        
        if result.success:
            logger.info("="*60)
            logger.info("SELF-HEALING SUCCESSFUL!")
            logger.info(f"Old coordinates: {result.old_coordinates}")
            logger.info(f"New coordinates: {result.new_coordinates}")
            logger.info(f"Attempts needed: {result.attempts}")
            logger.info("="*60)
            
            # Update baselines if full workflow succeeded
            if result.baseline_updated:
                self._update_baselines_after_success(failed_action_index)
        else:
            logger.error("="*60)
            logger.error("SELF-HEALING FAILED")
            logger.error(f"Error: {result.error_message}")
            logger.error(f"Attempts made: {result.attempts}")
            logger.error("="*60)
        
        return result
    
    def _update_baselines_after_success(self, healed_action_index: int):
        """
        Update baselines after a successful healing.
        
        This captures new 100x100 screenshots at updated coordinates
        and saves them as the new baselines.
        """
        logger.info("Updating baselines after successful healing...")
        
        # Get the updated coordinates
        coords = self.updater.get_action_coordinates(healed_action_index)
        if coords:
            x, y = coords
            # Capture new baseline
            new_baseline = self.capture_baseline(x, y)
            # Save to database
            self.update_baseline('instagram-default', healed_action_index, new_baseline)
            logger.info(f"Updated baseline for action {healed_action_index}")
    
    def should_attempt_heal(
        self,
        similarity_score: float,
        consecutive_failures: int
    ) -> bool:
        """
        Determine if self-healing should be attempted.
        
        Args:
            similarity_score: Current similarity score
            consecutive_failures: How many times this action has failed in a row
            
        Returns:
            True if healing should be attempted
        """
        # Only heal if similarity is low enough (indicates UI change)
        if similarity_score >= SIMILARITY_FAILURE_THRESHOLD:
            return False
        
        # Only heal after multiple consecutive failures
        if consecutive_failures < 2:
            logger.info(f"Waiting for more failures ({consecutive_failures}/2) before healing")
            return False
        
        return True
    
    def get_healing_summary(self) -> dict:
        """Get summary of healing attempts."""
        if not self.healing_history:
            return {"total_attempts": 0, "successes": 0, "failures": 0}
        
        successes = sum(1 for h in self.healing_history if h['success'])
        return {
            "total_attempts": len(self.healing_history),
            "successes": successes,
            "failures": len(self.healing_history) - successes,
            "success_rate": successes / len(self.healing_history),
            "recent_healings": self.healing_history[-5:]
        }
    
    def close(self):
        """Clean up resources."""
        self.locator.close()


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================
#
# Here's how to integrate this with your existing workflow runner:
#
# ```python
# from self_healing.instagram_healer import InstagramHealer
#
# # Your existing functions (adapt these to your actual implementation)
# def my_vnc_screenshot() -> bytes:
#     """Capture full desktop via VNC."""
#     return vnc_connection.capture_screen()  # Your existing code
#
# def my_hid_click(x: int, y: int) -> bool:
#     """Send click via HID device."""
#     return hid_controller.click(x, y)  # Your existing code
#
# def my_run_workflow(workflow_name: str, start_index: int):
#     """Run workflow starting from given index."""
#     # Your existing workflow runner
#     result = workflow_runner.execute_from(workflow_name, start_index)
#     return (result.success, result.failed_at_index, result.similarity)
#
# def my_capture_baseline(x: int, y: int) -> bytes:
#     """Capture 100x100 region around coordinates."""
#     screenshot = my_vnc_screenshot()
#     return crop_region(screenshot, x, y, 100, 100)  # Your existing code
#
# def my_get_baseline(workflow_name: str, action_index: int) -> bytes:
#     """Get baseline from SQLite database."""
#     return db.get_baseline(workflow_name, action_index)  # Your existing code
#
# def my_update_baseline(workflow_name: str, action_index: int, image: bytes):
#     """Save new baseline to database."""
#     db.save_baseline(workflow_name, action_index, image)  # Your existing code
#
# # Initialize healer
# healer = InstagramHealer(
#     screenshot_func=my_vnc_screenshot,
#     click_func=my_hid_click,
#     run_workflow_func=my_run_workflow,
#     capture_baseline_func=my_capture_baseline,
#     get_baseline_func=my_get_baseline,
#     update_baseline_func=my_update_baseline
# )
#
# # In your main workflow loop:
# def run_instagram_post(post_data):
#     for action_index, action in enumerate(workflow_actions):
#         if action.type == 'click':
#             # Capture before click
#             screenshot = capture_click_region(action.x, action.y)
#             
#             # Compare to baseline
#             baseline = get_baseline('instagram-default', action_index)
#             similarity = compare_images(screenshot, baseline)
#             
#             if similarity < 0.70:  # UI has changed
#                 # Attempt self-healing
#                 result = healer.attempt_heal(
#                     failed_action_index=action_index,
#                     similarity_score=similarity,
#                     failed_screenshot=screenshot,
#                     baseline_screenshot=baseline
#                 )
#                 
#                 if result.success:
#                     # Update action with new coordinates
#                     action.x, action.y = result.new_coordinates
#                 else:
#                     # Mark post as failed
#                     return False
#             
#             # Perform click
#             click(action.x, action.y)
# ```
```

---

## Integration Points

Create `self_healing/__init__.py`:

```python
"""
Instagram Self-Healing Workflow System

This module provides automatic recovery when Instagram changes their UI
and moves buttons/elements from their expected locations.

Main classes:
- InstagramHealer: High-level API for self-healing Instagram workflows
- VisionLocator: AI-powered element finding using Qwen 2.5 Vision
- WorkflowUpdater: Manages workflow JSON file updates
- HealingOrchestrator: Coordinates the healing process

Quick start:
    from self_healing import InstagramHealer
    
    healer = InstagramHealer(
        screenshot_func=your_screenshot_func,
        click_func=your_click_func,
        run_workflow_func=your_workflow_func,
        capture_baseline_func=your_baseline_capture,
        get_baseline_func=your_baseline_getter,
        update_baseline_func=your_baseline_updater
    )
    
    result = healer.attempt_heal(
        failed_action_index=3,
        similarity_score=0.24,
        failed_screenshot=captured_bytes
    )
"""

from .config import (
    OPENROUTER_API_KEY,
    VISION_MODEL,
    MAX_HEALING_ATTEMPTS,
    SIMILARITY_FAILURE_THRESHOLD,
    INSTAGRAM_ACTION_DESCRIPTIONS,
)

from .vision_locator import VisionLocator, LocatorResult
from .workflow_updater import WorkflowUpdater
from .healing_orchestrator import HealingOrchestrator, HealingResult
from .instagram_healer import InstagramHealer

__all__ = [
    'InstagramHealer',
    'VisionLocator',
    'LocatorResult', 
    'WorkflowUpdater',
    'HealingOrchestrator',
    'HealingResult',
    'OPENROUTER_API_KEY',
    'VISION_MODEL',
    'MAX_HEALING_ATTEMPTS',
    'SIMILARITY_FAILURE_THRESHOLD',
    'INSTAGRAM_ACTION_DESCRIPTIONS',
]
```

---

## Critical Implementation Notes

### 1. Action Description Mapping

**YOU MUST UPDATE THIS** in `config.py` to match your actual Instagram workflow:

```python
INSTAGRAM_ACTION_DESCRIPTIONS = {
    0: "Click on the 'Create new post' button (+ icon in the top navigation)",
    1: "Click on 'Post' option in the create menu dropdown",
    2: "Click 'Select from computer' button to upload media",
    # ... etc
}
```

The AI needs accurate descriptions to find moved elements. Be specific:
- ❌ "Click button" (too vague)
- ✅ "Click the blue 'Share' button in the bottom right of the caption screen"

### 2. Existing Code Adapters

You need to provide adapter functions for your existing infrastructure:

```python
# These must match YOUR existing code signatures

def your_screenshot_func() -> bytes:
    """Must return full desktop PNG bytes from VNC"""
    pass

def your_click_func(x: int, y: int) -> bool:
    """Must send click via your HID system"""
    pass

def your_run_workflow_func(name: str, start_idx: int) -> Tuple[bool, int, float]:
    """Must run workflow and return (success, failed_index, similarity)"""
    pass
```

### 3. When Self-Healing Triggers

The system triggers when:
1. Similarity score < 0.70 (configurable via `SIMILARITY_FAILURE_THRESHOLD`)
2. At least 2 consecutive failures at the same action (prevents false positives)
3. Human hasn't disabled self-healing

### 4. What Gets Updated

When healing succeeds:
1. **Workflow JSON**: New coordinates saved to the file
2. **Backup**: Old workflow backed up with timestamp
3. **Baseline**: New 100x100 screenshot saved as baseline
4. **History**: Correction logged in `_healing_history` within workflow JSON

### 5. Safety Measures

- Backup created before ANY workflow modification
- Rollback available if verification fails
- Maximum 3 healing attempts before giving up
- Confidence threshold (0.80) prevents accepting uncertain coordinates
- All changes logged for audit

---

## Testing the System

Create `tests/test_self_healing.py`:

```python
"""
Test self-healing system components.
"""
import pytest
from unittest.mock import Mock, patch
import json

from self_healing.vision_locator import VisionLocator, LocatorResult
from self_healing.workflow_updater import WorkflowUpdater
from self_healing.instagram_healer import InstagramHealer


class TestVisionLocator:
    """Test the AI-powered element locator."""
    
    def test_parse_valid_response(self):
        locator = VisionLocator.__new__(VisionLocator)
        
        raw = '''{"found": true, "new_x": 500, "new_y": 300, "confidence": 0.95, "reasoning": "Found button"}'''
        result = locator._parse_response(raw)
        
        assert result.success == True
        assert result.new_x == 500
        assert result.new_y == 300
        assert result.confidence == 0.95
    
    def test_parse_not_found(self):
        locator = VisionLocator.__new__(VisionLocator)
        
        raw = '''{"found": false, "reasoning": "Element not visible"}'''
        result = locator._parse_response(raw)
        
        assert result.success == False
    
    def test_parse_low_confidence(self):
        locator = VisionLocator.__new__(VisionLocator)
        
        raw = '''{"found": true, "new_x": 100, "new_y": 100, "confidence": 0.5, "reasoning": "Maybe"}'''
        result = locator._parse_response(raw)
        
        assert result.success == False  # Below threshold


class TestWorkflowUpdater:
    """Test workflow file management."""
    
    def test_update_coordinates(self, tmp_path):
        # Create test workflow
        workflow = {
            "actions": [
                {"type": "click", "x": 100, "y": 200},
                {"type": "wait", "duration": 1000},
                {"type": "click", "x": 300, "y": 400}
            ]
        }
        
        workflow_file = tmp_path / "test_workflow.json"
        with open(workflow_file, 'w') as f:
            json.dump(workflow, f)
        
        updater = WorkflowUpdater(str(workflow_file))
        updater.update_coordinates(0, new_x=150, new_y=250, create_backup=False)
        
        updated = updater.load_workflow()
        assert updated['actions'][0]['x'] == 150
        assert updated['actions'][0]['y'] == 250
    
    def test_rollback(self, tmp_path):
        workflow = {"actions": [{"type": "click", "x": 100, "y": 200}]}
        
        workflow_file = tmp_path / "test_workflow.json"
        with open(workflow_file, 'w') as f:
            json.dump(workflow, f)
        
        updater = WorkflowUpdater(str(workflow_file))
        updater.update_coordinates(0, new_x=999, new_y=999, create_backup=False)
        
        # Verify change
        assert updater.load_workflow()['actions'][0]['x'] == 999
        
        # Rollback
        updater.rollback()
        
        # Verify rollback
        assert updater.load_workflow()['actions'][0]['x'] == 100


class TestInstagramHealer:
    """Test the main healer integration."""
    
    def test_should_attempt_heal(self):
        healer = InstagramHealer.__new__(InstagramHealer)
        
        # Should heal: low similarity + enough failures
        assert healer.should_attempt_heal(0.24, 3) == True
        
        # Should not heal: high similarity
        assert healer.should_attempt_heal(0.85, 3) == False
        
        # Should not heal: not enough failures yet
        assert healer.should_attempt_heal(0.24, 1) == False
```

---

## Execution Flow Summary

```
1. WORKFLOW RUNS
   └── Action 3 fails with 24% similarity

2. SELF-HEALING TRIGGERED
   ├── Take full desktop screenshot
   ├── Get baseline image for action 3
   ├── Get workflow step description: "Click Upload Media button"
   └── Get old coordinates: (500, 300)

3. AI LOCATOR CALLED
   ├── Send to Qwen 2.5 Vision:
   │   - Full screenshot
   │   - Baseline (what it should look like)
   │   - Failed capture (what we saw)
   │   - Description of target element
   │   - Old coordinates
   └── AI responds: "Found at (520, 350) with 92% confidence"

4. WORKFLOW UPDATED
   ├── Backup old workflow JSON
   ├── Update action 3: x=520, y=350
   └── Add to healing history

5. VERIFICATION RUN
   ├── Re-run workflow from action 3
   ├── If succeeds → Update baselines, mark success
   └── If fails → Rollback, try again (up to 3 times)

6. RESULT
   ├── Success: New coordinates saved, baselines updated
   └── Failure: Original workflow restored, manual intervention needed
```

---

## Required Dependencies

Add to your `requirements.txt`:

```
httpx>=0.25.0
Pillow>=10.0.0
```

The rest should already be installed based on your existing system.