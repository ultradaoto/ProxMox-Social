# Workflow Visual Validation System Specification

## Executive Summary

This document specifies a **visual validation system** for social media posting workflows that captures, stores, and compares screenshots around click points to detect failures before they propagate. The system uses SQLite for storage and runs on Ubuntu alongside the existing workflow automation.

**Problem Being Solved**: A single unexpected popup or UI change can cause the automation to click in the wrong context, leading to cascading failures across all subsequent posts. Currently, there's no way to detect this until manual inspection.

**Solution**: Before marking any workflow as "success", validate that every click landed on the expected visual context by comparing 100x100 pixel snapshots around each click coordinate against known-good baselines.

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UBUNTU CONTROLLER                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  Workflow Runner │───▶│ Visual Validator │───▶│  SQLite Database │  │
│  │  (existing)      │    │  (NEW)           │    │  (NEW)           │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│           │                       │                       │              │
│           │                       │                       │              │
│           ▼                       ▼                       ▼              │
│  ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│  │  JSON Workflow   │    │  VNC Screenshot  │    │  Baseline Images │  │
│  │  Definitions     │    │  Capture         │    │  + Run History   │  │
│  └──────────────────┘    └──────────────────┘    └──────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ VNC
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        WINDOWS 10 VM                                     │
│  (Facebook, LinkedIn, Instagram, Skool browsers)                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. SQLite Database Schema

Create database at: `/home/user/workflow-validation/validation.db`

```sql
-- Workflow definitions (maps to JSON files)
CREATE TABLE workflows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- e.g., 'facebook-default'
    json_path TEXT NOT NULL,             -- e.g., '/path/to/facebook-default.json'
    platform TEXT NOT NULL,              -- 'facebook', 'linkedin', 'instagram', 'skool'
    total_actions INTEGER NOT NULL,      -- Total actions in workflow (e.g., 36)
    click_count INTEGER NOT NULL,        -- Number of click actions specifically
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Baseline images for each click point in a workflow
CREATE TABLE click_baselines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    action_index INTEGER NOT NULL,       -- Position in workflow (0-indexed)
    action_type TEXT NOT NULL,           -- 'click', 'doubleClick', etc.
    click_x INTEGER NOT NULL,            -- X coordinate of click
    click_y INTEGER NOT NULL,            -- Y coordinate of click
    baseline_image BLOB NOT NULL,        -- 100x100 PNG image data
    image_hash TEXT NOT NULL,            -- SHA256 hash for quick comparison
    description TEXT,                    -- Optional: "Click post button"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confidence_threshold REAL DEFAULT 0.95,  -- Match threshold (0.0-1.0)
    FOREIGN KEY (workflow_id) REFERENCES workflows(id),
    UNIQUE(workflow_id, action_index)
);

-- Individual workflow execution runs
CREATE TABLE workflow_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    post_id TEXT,                        -- Reference to the post being processed
    status TEXT NOT NULL,                -- 'running', 'success', 'failed', 'validation_failed'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    failure_action_index INTEGER,        -- Which action failed (if any)
    failure_reason TEXT,                 -- Description of failure
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

-- Screenshots captured during each run
CREATE TABLE run_screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    action_index INTEGER NOT NULL,
    click_x INTEGER NOT NULL,
    click_y INTEGER NOT NULL,
    captured_image BLOB NOT NULL,        -- 100x100 PNG captured during run
    image_hash TEXT NOT NULL,
    baseline_match_score REAL,           -- Similarity to baseline (0.0-1.0)
    is_match BOOLEAN,                    -- Did it pass validation?
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES workflow_runs(id)
);

-- Future: Self-healing corrections
CREATE TABLE workflow_corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id INTEGER NOT NULL,
    action_index INTEGER NOT NULL,
    old_click_x INTEGER NOT NULL,
    old_click_y INTEGER NOT NULL,
    new_click_x INTEGER NOT NULL,
    new_click_y INTEGER NOT NULL,
    old_baseline_image BLOB,
    new_baseline_image BLOB,
    reason TEXT,                         -- Why correction was made
    consecutive_failures INTEGER,        -- How many failures before correction
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);

-- Indexes for performance
CREATE INDEX idx_baselines_workflow ON click_baselines(workflow_id);
CREATE INDEX idx_runs_workflow ON workflow_runs(workflow_id);
CREATE INDEX idx_runs_status ON workflow_runs(status);
CREATE INDEX idx_screenshots_run ON run_screenshots(run_id);
CREATE INDEX idx_corrections_workflow ON workflow_corrections(workflow_id);
```

---

### 2. Directory Structure

```
/home/user/workflow-validation/
├── validation.db                    # SQLite database
├── config.yaml                      # Configuration settings
├── workflows/                       # JSON workflow definitions
│   ├── facebook-default.json
│   ├── linkedin-default.json
│   ├── instagram-default.json
│   └── skool-default.json
├── src/
│   ├── __init__.py
│   ├── database.py                  # SQLite operations
│   ├── screenshot_capture.py        # VNC screenshot + crop
│   ├── image_comparator.py          # Fast image comparison
│   ├── workflow_parser.py           # Parse JSON workflows
│   ├── validator.py                 # Main validation logic
│   ├── baseline_manager.py          # Create/update baselines
│   └── run_tracker.py               # Track workflow runs
├── tests/
│   └── test_validation.py
└── logs/
    └── validation.log
```

---

### 3. Configuration File

Create `/home/user/workflow-validation/config.yaml`:

```yaml
# Workflow Visual Validation Configuration

database:
  path: "/home/user/workflow-validation/validation.db"

vnc:
  host: "localhost"
  port: 5900
  # Or use existing VNC connection method

screenshot:
  box_size: 100                    # 100x100 pixel capture around click
  format: "PNG"                    # Storage format
  compression: 6                   # PNG compression level (0-9)

validation:
  default_threshold: 0.95          # 95% similarity required
  strict_threshold: 0.98           # For critical clicks
  lenient_threshold: 0.85          # For dynamic content areas
  
  # Actions that require validation (clicks on page)
  validate_actions:
    - "click"
    - "doubleClick"
    - "rightClick"
  
  # Actions that don't need validation
  skip_actions:
    - "wait"
    - "keyCombo"
    - "type"
    - "scroll"

comparison:
  algorithm: "structural_similarity"  # Options: 'hash', 'structural_similarity', 'pixel_diff'
  hash_size: 16                       # For perceptual hashing
  
failure_handling:
  max_consecutive_failures: 3        # Before flagging for self-healing
  report_to_api: true                # Send failure to dashboard
  api_endpoint: "https://social.sterlingcooley.com/api/workflow-failure"

logging:
  level: "INFO"
  file: "/home/user/workflow-validation/logs/validation.log"
  max_size_mb: 10
  backup_count: 5
```

---

## Implementation Modules

### Module 1: Database Operations (`database.py`)

```python
"""
SQLite database operations for workflow validation.
"""
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from contextlib import contextmanager


class ValidationDatabase:
    """Manages SQLite database for workflow validation."""
    
    def __init__(self, db_path: str):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _init_schema(self) -> None:
        """Initialize database schema if not exists."""
        schema = '''
        -- [Include full schema from above]
        '''
        with self._get_connection() as conn:
            conn.executescript(schema)
    
    # ========== Workflow Operations ==========
    
    def register_workflow(
        self,
        name: str,
        json_path: str,
        platform: str,
        total_actions: int,
        click_count: int
    ) -> int:
        """
        Register a new workflow or update existing.
        
        Returns:
            Workflow ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO workflows (name, json_path, platform, total_actions, click_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    json_path = excluded.json_path,
                    total_actions = excluded.total_actions,
                    click_count = excluded.click_count,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            ''', (name, json_path, platform, total_actions, click_count))
            return cursor.fetchone()[0]
    
    def get_workflow(self, name: str) -> Optional[Dict]:
        """Get workflow by name."""
        with self._get_connection() as conn:
            row = conn.execute(
                'SELECT * FROM workflows WHERE name = ?', (name,)
            ).fetchone()
            return dict(row) if row else None
    
    # ========== Baseline Operations ==========
    
    def save_baseline(
        self,
        workflow_id: int,
        action_index: int,
        action_type: str,
        click_x: int,
        click_y: int,
        image_data: bytes,
        description: str = None,
        threshold: float = 0.95
    ) -> int:
        """
        Save or update a baseline image for a click action.
        
        Args:
            workflow_id: ID of the workflow
            action_index: Position in workflow (0-indexed)
            action_type: Type of action ('click', 'doubleClick', etc.)
            click_x: X coordinate of click
            click_y: Y coordinate of click
            image_data: PNG image bytes (100x100)
            description: Optional description
            threshold: Match threshold for this baseline
            
        Returns:
            Baseline ID
        """
        image_hash = hashlib.sha256(image_data).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO click_baselines 
                    (workflow_id, action_index, action_type, click_x, click_y, 
                     baseline_image, image_hash, description, confidence_threshold)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(workflow_id, action_index) DO UPDATE SET
                    action_type = excluded.action_type,
                    click_x = excluded.click_x,
                    click_y = excluded.click_y,
                    baseline_image = excluded.baseline_image,
                    image_hash = excluded.image_hash,
                    description = excluded.description,
                    confidence_threshold = excluded.confidence_threshold
                RETURNING id
            ''', (workflow_id, action_index, action_type, click_x, click_y,
                  image_data, image_hash, description, threshold))
            return cursor.fetchone()[0]
    
    def get_baselines(self, workflow_id: int) -> List[Dict]:
        """Get all baselines for a workflow."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM click_baselines 
                WHERE workflow_id = ? 
                ORDER BY action_index
            ''', (workflow_id,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_baseline(self, workflow_id: int, action_index: int) -> Optional[Dict]:
        """Get specific baseline."""
        with self._get_connection() as conn:
            row = conn.execute('''
                SELECT * FROM click_baselines 
                WHERE workflow_id = ? AND action_index = ?
            ''', (workflow_id, action_index)).fetchone()
            return dict(row) if row else None
    
    # ========== Run Tracking ==========
    
    def start_run(self, workflow_id: int, post_id: str = None) -> int:
        """
        Start tracking a new workflow run.
        
        Returns:
            Run ID
        """
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO workflow_runs (workflow_id, post_id, status)
                VALUES (?, ?, 'running')
                RETURNING id
            ''', (workflow_id, post_id))
            return cursor.fetchone()[0]
    
    def save_run_screenshot(
        self,
        run_id: int,
        action_index: int,
        click_x: int,
        click_y: int,
        image_data: bytes,
        match_score: float = None,
        is_match: bool = None
    ) -> int:
        """Save screenshot captured during run."""
        image_hash = hashlib.sha256(image_data).hexdigest()
        
        with self._get_connection() as conn:
            cursor = conn.execute('''
                INSERT INTO run_screenshots 
                    (run_id, action_index, click_x, click_y, 
                     captured_image, image_hash, baseline_match_score, is_match)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
            ''', (run_id, action_index, click_x, click_y,
                  image_data, image_hash, match_score, is_match))
            return cursor.fetchone()[0]
    
    def complete_run(
        self,
        run_id: int,
        status: str,
        failure_index: int = None,
        failure_reason: str = None
    ) -> None:
        """Mark a run as complete."""
        with self._get_connection() as conn:
            conn.execute('''
                UPDATE workflow_runs SET
                    status = ?,
                    completed_at = CURRENT_TIMESTAMP,
                    failure_action_index = ?,
                    failure_reason = ?
                WHERE id = ?
            ''', (status, failure_index, failure_reason, run_id))
    
    def get_recent_failures(
        self,
        workflow_id: int,
        action_index: int,
        limit: int = 3
    ) -> List[Dict]:
        """Get recent failures for a specific action."""
        with self._get_connection() as conn:
            rows = conn.execute('''
                SELECT * FROM workflow_runs
                WHERE workflow_id = ?
                    AND status = 'validation_failed'
                    AND failure_action_index = ?
                ORDER BY completed_at DESC
                LIMIT ?
            ''', (workflow_id, action_index, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def count_consecutive_failures(
        self,
        workflow_id: int,
        action_index: int
    ) -> int:
        """Count consecutive failures at a specific action."""
        with self._get_connection() as conn:
            # Get most recent runs
            rows = conn.execute('''
                SELECT status, failure_action_index FROM workflow_runs
                WHERE workflow_id = ?
                ORDER BY completed_at DESC
                LIMIT 10
            ''', (workflow_id,)).fetchall()
            
            count = 0
            for row in rows:
                if row['status'] == 'validation_failed' and row['failure_action_index'] == action_index:
                    count += 1
                else:
                    break
            return count
```

---

### Module 2: Screenshot Capture (`screenshot_capture.py`)

```python
"""
VNC screenshot capture with region cropping.
"""
import io
from typing import Tuple, Optional
from PIL import Image
import numpy as np


class ScreenshotCapture:
    """Captures and crops screenshots via VNC."""
    
    def __init__(self, vnc_connection, box_size: int = 100):
        """
        Initialize screenshot capture.
        
        Args:
            vnc_connection: Existing VNC connection object
            box_size: Size of square capture box (default 100x100)
        """
        self.vnc = vnc_connection
        self.box_size = box_size
    
    def capture_full_screen(self) -> Image.Image:
        """
        Capture full screen via VNC.
        
        Returns:
            PIL Image of full screen
        """
        # This should use your existing VNC screenshot method
        # Adapt to your actual VNC library
        screenshot_data = self.vnc.capture_screen()
        
        if isinstance(screenshot_data, bytes):
            return Image.open(io.BytesIO(screenshot_data))
        elif isinstance(screenshot_data, np.ndarray):
            return Image.fromarray(screenshot_data)
        else:
            return screenshot_data
    
    def capture_click_region(
        self,
        click_x: int,
        click_y: int,
        full_screen: Image.Image = None
    ) -> bytes:
        """
        Capture region around click coordinates.
        
        Args:
            click_x: X coordinate of click
            click_y: Y coordinate of click
            full_screen: Optional pre-captured full screen image
            
        Returns:
            PNG image bytes of the region
        """
        if full_screen is None:
            full_screen = self.capture_full_screen()
        
        # Calculate bounding box centered on click
        half_box = self.box_size // 2
        
        # Ensure we don't go outside screen bounds
        screen_width, screen_height = full_screen.size
        
        left = max(0, click_x - half_box)
        top = max(0, click_y - half_box)
        right = min(screen_width, click_x + half_box)
        bottom = min(screen_height, click_y + half_box)
        
        # Crop the region
        region = full_screen.crop((left, top, right, bottom))
        
        # Ensure consistent size (pad if near edge)
        if region.size != (self.box_size, self.box_size):
            padded = Image.new('RGB', (self.box_size, self.box_size), (0, 0, 0))
            paste_x = (self.box_size - region.size[0]) // 2
            paste_y = (self.box_size - region.size[1]) // 2
            padded.paste(region, (paste_x, paste_y))
            region = padded
        
        # Convert to PNG bytes
        buffer = io.BytesIO()
        region.save(buffer, format='PNG', compress_level=6)
        return buffer.getvalue()
    
    def capture_before_click(
        self,
        click_x: int,
        click_y: int
    ) -> Tuple[bytes, Image.Image]:
        """
        Capture screenshot before performing click.
        
        Returns:
            Tuple of (region_bytes, full_screen_image)
        """
        full_screen = self.capture_full_screen()
        region = self.capture_click_region(click_x, click_y, full_screen)
        return region, full_screen
```

---

### Module 3: Image Comparator (`image_comparator.py`)

```python
"""
Fast image comparison for validation.
Optimized for 100x100 pixel images.
"""
import io
import hashlib
from typing import Tuple
from PIL import Image
import numpy as np


class ImageComparator:
    """
    Compares images using multiple algorithms.
    Optimized for speed on small images.
    """
    
    def __init__(self, algorithm: str = 'structural_similarity'):
        """
        Initialize comparator.
        
        Args:
            algorithm: Comparison algorithm
                - 'hash': Perceptual hash (fastest)
                - 'pixel_diff': Mean pixel difference (fast)
                - 'structural_similarity': SSIM (most accurate)
        """
        self.algorithm = algorithm
    
    def compare(
        self,
        image1: bytes,
        image2: bytes,
        threshold: float = 0.95
    ) -> Tuple[bool, float]:
        """
        Compare two images.
        
        Args:
            image1: First image bytes (baseline)
            image2: Second image bytes (captured)
            threshold: Minimum similarity score to pass
            
        Returns:
            Tuple of (is_match, similarity_score)
        """
        # Quick hash check first
        if hashlib.sha256(image1).hexdigest() == hashlib.sha256(image2).hexdigest():
            return True, 1.0
        
        # Load images
        img1 = Image.open(io.BytesIO(image1)).convert('RGB')
        img2 = Image.open(io.BytesIO(image2)).convert('RGB')
        
        # Ensure same size
        if img1.size != img2.size:
            img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
        
        # Compare using selected algorithm
        if self.algorithm == 'hash':
            score = self._perceptual_hash_similarity(img1, img2)
        elif self.algorithm == 'pixel_diff':
            score = self._pixel_diff_similarity(img1, img2)
        else:  # structural_similarity
            score = self._ssim_similarity(img1, img2)
        
        return score >= threshold, score
    
    def _pixel_diff_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image
    ) -> float:
        """
        Calculate similarity using mean pixel difference.
        Very fast, good for near-identical images.
        """
        arr1 = np.array(img1, dtype=np.float32)
        arr2 = np.array(img2, dtype=np.float32)
        
        # Mean absolute difference normalized to 0-1
        diff = np.abs(arr1 - arr2).mean() / 255.0
        
        # Convert to similarity score
        return 1.0 - diff
    
    def _perceptual_hash_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image,
        hash_size: int = 16
    ) -> float:
        """
        Calculate similarity using perceptual hashing.
        Very fast, tolerant of minor changes.
        """
        def dhash(image: Image.Image) -> int:
            # Resize and convert to grayscale
            resized = image.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            grayscale = resized.convert('L')
            pixels = np.array(grayscale)
            
            # Compute difference hash
            diff = pixels[:, 1:] > pixels[:, :-1]
            return int(np.packbits(diff.flatten()).tobytes().hex(), 16)
        
        hash1 = dhash(img1)
        hash2 = dhash(img2)
        
        # Hamming distance
        xor = hash1 ^ hash2
        distance = bin(xor).count('1')
        max_distance = hash_size * hash_size
        
        return 1.0 - (distance / max_distance)
    
    def _ssim_similarity(
        self,
        img1: Image.Image,
        img2: Image.Image
    ) -> float:
        """
        Calculate Structural Similarity Index (SSIM).
        Most accurate, slightly slower.
        """
        # Convert to grayscale numpy arrays
        arr1 = np.array(img1.convert('L'), dtype=np.float64)
        arr2 = np.array(img2.convert('L'), dtype=np.float64)
        
        # Constants for stability
        C1 = (0.01 * 255) ** 2
        C2 = (0.03 * 255) ** 2
        
        # Compute means
        mu1 = arr1.mean()
        mu2 = arr2.mean()
        
        # Compute variances and covariance
        sigma1_sq = arr1.var()
        sigma2_sq = arr2.var()
        sigma12 = ((arr1 - mu1) * (arr2 - mu2)).mean()
        
        # SSIM formula
        numerator = (2 * mu1 * mu2 + C1) * (2 * sigma12 + C2)
        denominator = (mu1**2 + mu2**2 + C1) * (sigma1_sq + sigma2_sq + C2)
        
        return numerator / denominator


# Singleton for quick access
_comparator = None

def get_comparator(algorithm: str = 'structural_similarity') -> ImageComparator:
    """Get or create image comparator singleton."""
    global _comparator
    if _comparator is None or _comparator.algorithm != algorithm:
        _comparator = ImageComparator(algorithm)
    return _comparator


def quick_compare(
    baseline: bytes,
    captured: bytes,
    threshold: float = 0.95
) -> Tuple[bool, float]:
    """
    Quick comparison function.
    
    Returns:
        Tuple of (is_match, similarity_score)
    """
    return get_comparator().compare(baseline, captured, threshold)
```

---

### Module 4: Workflow Parser (`workflow_parser.py`)

```python
"""
Parse JSON workflow files and extract click actions.
"""
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ClickAction:
    """Represents a click action in a workflow."""
    index: int                  # Position in workflow
    action_type: str            # 'click', 'doubleClick', etc.
    x: int                      # X coordinate
    y: int                      # Y coordinate
    description: Optional[str]  # Optional description
    
    
@dataclass
class WorkflowInfo:
    """Parsed workflow information."""
    name: str
    json_path: str
    platform: str
    total_actions: int
    click_actions: List[ClickAction]
    

class WorkflowParser:
    """Parses JSON workflow files."""
    
    # Action types that require visual validation
    CLICK_ACTIONS = {'click', 'doubleClick', 'rightClick'}
    
    # Action types that don't need validation
    SKIP_ACTIONS = {'wait', 'keyCombo', 'type', 'scroll', 'delay'}
    
    def __init__(self, workflows_dir: str = None):
        """
        Initialize parser.
        
        Args:
            workflows_dir: Directory containing workflow JSON files
        """
        self.workflows_dir = Path(workflows_dir) if workflows_dir else None
    
    def parse_file(self, json_path: str) -> WorkflowInfo:
        """
        Parse a workflow JSON file.
        
        Args:
            json_path: Path to JSON workflow file
            
        Returns:
            WorkflowInfo with extracted click actions
        """
        path = Path(json_path)
        
        with open(path) as f:
            data = json.load(f)
        
        # Extract workflow name and platform from filename
        # e.g., 'facebook-default.json' -> name='facebook-default', platform='facebook'
        name = path.stem
        platform = name.split('-')[0] if '-' in name else name
        
        # Parse actions
        actions = data.get('actions', data.get('steps', []))
        click_actions = []
        
        for i, action in enumerate(actions):
            action_type = action.get('type', action.get('action', ''))
            
            if action_type.lower() in self.CLICK_ACTIONS:
                # Extract coordinates
                x = action.get('x', action.get('coordinates', {}).get('x', 0))
                y = action.get('y', action.get('coordinates', {}).get('y', 0))
                description = action.get('description', action.get('name', None))
                
                click_actions.append(ClickAction(
                    index=i,
                    action_type=action_type.lower(),
                    x=int(x),
                    y=int(y),
                    description=description
                ))
        
        return WorkflowInfo(
            name=name,
            json_path=str(path.absolute()),
            platform=platform,
            total_actions=len(actions),
            click_actions=click_actions
        )
    
    def parse_all(self) -> List[WorkflowInfo]:
        """Parse all workflow files in workflows directory."""
        if not self.workflows_dir:
            raise ValueError("No workflows directory specified")
        
        workflows = []
        for json_file in self.workflows_dir.glob('*.json'):
            try:
                workflows.append(self.parse_file(str(json_file)))
            except Exception as e:
                print(f"Error parsing {json_file}: {e}")
        
        return workflows
    
    def get_click_indices(self, json_path: str) -> List[int]:
        """Get list of action indices that are clicks."""
        info = self.parse_file(json_path)
        return [click.index for click in info.click_actions]
```

---

### Module 5: Main Validator (`validator.py`)

```python
"""
Main validation logic - the core of the system.
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from .database import ValidationDatabase
from .screenshot_capture import ScreenshotCapture
from .image_comparator import quick_compare
from .workflow_parser import WorkflowParser, WorkflowInfo, ClickAction


@dataclass
class ValidationResult:
    """Result of validating a single click."""
    action_index: int
    click_x: int
    click_y: int
    is_valid: bool
    similarity_score: float
    baseline_exists: bool
    

@dataclass
class WorkflowValidationResult:
    """Result of validating entire workflow run."""
    run_id: int
    workflow_name: str
    success: bool
    click_results: List[ValidationResult]
    failure_index: Optional[int]
    failure_reason: Optional[str]


class WorkflowValidator:
    """
    Validates workflow runs against stored baselines.
    
    Usage:
        validator = WorkflowValidator(db, screenshot_capture, vnc)
        
        # During workflow execution, before each click:
        validator.capture_click(run_id, action_index, x, y)
        
        # Before marking success:
        result = validator.validate_run(run_id)
        if result.success:
            # Click success button
        else:
            # Click failed button, log failure_index
    """
    
    def __init__(
        self,
        database: ValidationDatabase,
        screenshot: ScreenshotCapture,
        default_threshold: float = 0.95,
        logger: logging.Logger = None
    ):
        """
        Initialize validator.
        
        Args:
            database: ValidationDatabase instance
            screenshot: ScreenshotCapture instance
            default_threshold: Default similarity threshold
            logger: Optional logger
        """
        self.db = database
        self.screenshot = screenshot
        self.default_threshold = default_threshold
        self.logger = logger or logging.getLogger(__name__)
        
        # Cache for current run
        self._current_run_id: Optional[int] = None
        self._current_workflow_id: Optional[int] = None
        self._captured_screenshots: Dict[int, bytes] = {}
    
    def start_run(
        self,
        workflow_name: str,
        post_id: str = None
    ) -> int:
        """
        Start tracking a new workflow run.
        
        Args:
            workflow_name: Name of workflow (e.g., 'facebook-default')
            post_id: Optional post identifier
            
        Returns:
            Run ID
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        self._current_workflow_id = workflow['id']
        self._current_run_id = self.db.start_run(workflow['id'], post_id)
        self._captured_screenshots = {}
        
        self.logger.info(f"Started run {self._current_run_id} for workflow {workflow_name}")
        return self._current_run_id
    
    def capture_click(
        self,
        action_index: int,
        click_x: int,
        click_y: int
    ) -> bytes:
        """
        Capture screenshot before performing a click.
        Call this BEFORE the click is executed.
        
        Args:
            action_index: Index of action in workflow
            click_x: X coordinate of click
            click_y: Y coordinate of click
            
        Returns:
            Captured image bytes
        """
        if self._current_run_id is None:
            raise ValueError("No active run. Call start_run() first.")
        
        # Capture the region
        image_data, _ = self.screenshot.capture_before_click(click_x, click_y)
        
        # Store for later validation
        self._captured_screenshots[action_index] = image_data
        
        # Save to database immediately (for recovery if crash)
        self.db.save_run_screenshot(
            run_id=self._current_run_id,
            action_index=action_index,
            click_x=click_x,
            click_y=click_y,
            image_data=image_data
        )
        
        self.logger.debug(f"Captured click {action_index} at ({click_x}, {click_y})")
        return image_data
    
    def validate_run(self) -> WorkflowValidationResult:
        """
        Validate all captured clicks against baselines.
        Call this BEFORE clicking the success button.
        
        Returns:
            WorkflowValidationResult with success/failure info
        """
        if self._current_run_id is None:
            raise ValueError("No active run. Call start_run() first.")
        
        results = []
        failure_index = None
        failure_reason = None
        
        # Get baselines for this workflow
        baselines = {b['action_index']: b for b in self.db.get_baselines(self._current_workflow_id)}
        
        # Validate each captured screenshot
        for action_index, captured_image in sorted(self._captured_screenshots.items()):
            baseline = baselines.get(action_index)
            
            if baseline is None:
                # No baseline exists - this is first run, can't validate
                results.append(ValidationResult(
                    action_index=action_index,
                    click_x=0,
                    click_y=0,
                    is_valid=True,  # Pass if no baseline (first run)
                    similarity_score=0.0,
                    baseline_exists=False
                ))
                continue
            
            # Compare against baseline
            threshold = baseline.get('confidence_threshold', self.default_threshold)
            is_match, score = quick_compare(
                baseline['baseline_image'],
                captured_image,
                threshold
            )
            
            results.append(ValidationResult(
                action_index=action_index,
                click_x=baseline['click_x'],
                click_y=baseline['click_y'],
                is_valid=is_match,
                similarity_score=score,
                baseline_exists=True
            ))
            
            # Track first failure
            if not is_match and failure_index is None:
                failure_index = action_index
                failure_reason = f"Click {action_index} mismatch: {score:.2%} similarity (need {threshold:.2%})"
                self.logger.warning(failure_reason)
        
        # Determine overall success
        success = all(r.is_valid for r in results)
        
        # Update run status
        status = 'success' if success else 'validation_failed'
        self.db.complete_run(
            run_id=self._current_run_id,
            status=status,
            failure_index=failure_index,
            failure_reason=failure_reason
        )
        
        # Get workflow name for result
        workflow = self.db.get_workflow_by_id(self._current_workflow_id)
        workflow_name = workflow['name'] if workflow else 'unknown'
        
        result = WorkflowValidationResult(
            run_id=self._current_run_id,
            workflow_name=workflow_name,
            success=success,
            click_results=results,
            failure_index=failure_index,
            failure_reason=failure_reason
        )
        
        # Clear run state
        self._current_run_id = None
        self._current_workflow_id = None
        self._captured_screenshots = {}
        
        return result
    
    def validate_single_click(
        self,
        workflow_name: str,
        action_index: int,
        captured_image: bytes
    ) -> Tuple[bool, float]:
        """
        Validate a single click against its baseline.
        Useful for real-time validation.
        
        Returns:
            Tuple of (is_valid, similarity_score)
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return True, 0.0  # No workflow = can't validate
        
        baseline = self.db.get_baseline(workflow['id'], action_index)
        if not baseline:
            return True, 0.0  # No baseline = can't validate
        
        threshold = baseline.get('confidence_threshold', self.default_threshold)
        return quick_compare(baseline['baseline_image'], captured_image, threshold)
    
    def should_trigger_self_healing(
        self,
        workflow_name: str,
        action_index: int,
        max_failures: int = 3
    ) -> bool:
        """
        Check if self-healing should be triggered for an action.
        
        Returns:
            True if consecutive failures exceed threshold
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return False
        
        count = self.db.count_consecutive_failures(workflow['id'], action_index)
        return count >= max_failures
```

---

### Module 6: Baseline Manager (`baseline_manager.py`)

```python
"""
Manage baseline images - create, update, and maintain.
"""
import logging
from typing import List, Optional
from pathlib import Path

from .database import ValidationDatabase
from .screenshot_capture import ScreenshotCapture
from .workflow_parser import WorkflowParser, WorkflowInfo


class BaselineManager:
    """
    Manages baseline images for workflows.
    
    Usage:
        manager = BaselineManager(db, screenshot, parser)
        
        # Create baselines from successful run
        manager.create_baselines_from_run('facebook-default')
        
        # Update single baseline
        manager.update_baseline('facebook-default', action_index=5, new_image)
    """
    
    def __init__(
        self,
        database: ValidationDatabase,
        screenshot: ScreenshotCapture,
        parser: WorkflowParser,
        logger: logging.Logger = None
    ):
        """
        Initialize baseline manager.
        
        Args:
            database: ValidationDatabase instance
            screenshot: ScreenshotCapture instance  
            parser: WorkflowParser instance
            logger: Optional logger
        """
        self.db = database
        self.screenshot = screenshot
        self.parser = parser
        self.logger = logger or logging.getLogger(__name__)
    
    def register_workflow(self, json_path: str) -> int:
        """
        Register a workflow from JSON file.
        
        Args:
            json_path: Path to workflow JSON
            
        Returns:
            Workflow ID
        """
        info = self.parser.parse_file(json_path)
        
        workflow_id = self.db.register_workflow(
            name=info.name,
            json_path=info.json_path,
            platform=info.platform,
            total_actions=info.total_actions,
            click_count=len(info.click_actions)
        )
        
        self.logger.info(f"Registered workflow '{info.name}' with {len(info.click_actions)} click actions")
        return workflow_id
    
    def create_baselines_interactive(
        self,
        workflow_name: str,
        callback_before_click=None,
        callback_after_click=None
    ) -> int:
        """
        Create baselines by running workflow with human guidance.
        
        This is the INITIAL SETUP process:
        1. Human runs through workflow manually
        2. Before each click, screenshot is captured
        3. Screenshots become baselines
        
        Args:
            workflow_name: Name of workflow
            callback_before_click: Called before each click with (action_index, x, y)
            callback_after_click: Called after each click
            
        Returns:
            Number of baselines created
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        info = self.parser.parse_file(workflow['json_path'])
        created_count = 0
        
        self.logger.info(f"Creating baselines for '{workflow_name}' ({len(info.click_actions)} clicks)")
        
        for click in info.click_actions:
            # Notify before click
            if callback_before_click:
                callback_before_click(click.index, click.x, click.y)
            
            # Capture screenshot
            image_data, _ = self.screenshot.capture_before_click(click.x, click.y)
            
            # Save as baseline
            self.db.save_baseline(
                workflow_id=workflow['id'],
                action_index=click.index,
                action_type=click.action_type,
                click_x=click.x,
                click_y=click.y,
                image_data=image_data,
                description=click.description
            )
            
            created_count += 1
            self.logger.debug(f"Created baseline for action {click.index}")
            
            # Notify after click
            if callback_after_click:
                callback_after_click(click.index)
        
        self.logger.info(f"Created {created_count} baselines for '{workflow_name}'")
        return created_count
    
    def create_baselines_from_screenshots(
        self,
        workflow_name: str,
        screenshots: dict  # {action_index: image_bytes}
    ) -> int:
        """
        Create baselines from pre-captured screenshots.
        
        Args:
            workflow_name: Name of workflow
            screenshots: Dict mapping action_index to image bytes
            
        Returns:
            Number of baselines created
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        info = self.parser.parse_file(workflow['json_path'])
        click_map = {c.index: c for c in info.click_actions}
        
        created_count = 0
        for action_index, image_data in screenshots.items():
            click = click_map.get(action_index)
            if not click:
                self.logger.warning(f"No click action at index {action_index}, skipping")
                continue
            
            self.db.save_baseline(
                workflow_id=workflow['id'],
                action_index=action_index,
                action_type=click.action_type,
                click_x=click.x,
                click_y=click.y,
                image_data=image_data,
                description=click.description
            )
            created_count += 1
        
        self.logger.info(f"Created {created_count} baselines from screenshots")
        return created_count
    
    def update_baseline(
        self,
        workflow_name: str,
        action_index: int,
        new_image: bytes,
        new_x: int = None,
        new_y: int = None
    ) -> None:
        """
        Update a single baseline with new image.
        
        Args:
            workflow_name: Name of workflow
            action_index: Action index to update
            new_image: New baseline image bytes
            new_x: New X coordinate (optional)
            new_y: New Y coordinate (optional)
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        existing = self.db.get_baseline(workflow['id'], action_index)
        if not existing:
            raise ValueError(f"No baseline exists at index {action_index}")
        
        self.db.save_baseline(
            workflow_id=workflow['id'],
            action_index=action_index,
            action_type=existing['action_type'],
            click_x=new_x or existing['click_x'],
            click_y=new_y or existing['click_y'],
            image_data=new_image,
            description=existing.get('description')
        )
        
        self.logger.info(f"Updated baseline for action {action_index}")
    
    def get_baseline_coverage(self, workflow_name: str) -> dict:
        """
        Get baseline coverage statistics for a workflow.
        
        Returns:
            Dict with coverage info
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return {"error": "Unknown workflow"}
        
        info = self.parser.parse_file(workflow['json_path'])
        baselines = self.db.get_baselines(workflow['id'])
        baseline_indices = {b['action_index'] for b in baselines}
        
        click_indices = {c.index for c in info.click_actions}
        covered = click_indices & baseline_indices
        missing = click_indices - baseline_indices
        
        return {
            "workflow": workflow_name,
            "total_clicks": len(click_indices),
            "baselines_exist": len(covered),
            "baselines_missing": len(missing),
            "coverage_percent": len(covered) / len(click_indices) * 100 if click_indices else 100,
            "missing_indices": sorted(missing)
        }
```

---

## Integration with Existing Workflow Runner

### How to Integrate

Your existing workflow runner needs to call the validator at specific points:

```python
# In your existing workflow runner (pseudocode)

from workflow_validation import (
    ValidationDatabase,
    ScreenshotCapture, 
    WorkflowValidator
)

# Initialize once at startup
db = ValidationDatabase('/home/user/workflow-validation/validation.db')
screenshot = ScreenshotCapture(vnc_connection, box_size=100)
validator = WorkflowValidator(db, screenshot)


async def run_workflow(workflow_name: str, post_id: str, actions: list):
    """
    Modified workflow runner with validation.
    """
    # 1. START: Begin tracking this run
    run_id = validator.start_run(workflow_name, post_id)
    
    try:
        for i, action in enumerate(actions):
            action_type = action.get('type', '')
            
            # 2. BEFORE CLICK: Capture screenshot
            if action_type in ('click', 'doubleClick', 'rightClick'):
                x, y = action['x'], action['y']
                validator.capture_click(action_index=i, click_x=x, click_y=y)
            
            # Execute the action (your existing code)
            await execute_action(action)
        
        # 3. BEFORE SUCCESS: Validate all clicks
        result = validator.validate_run()
        
        if result.success:
            # All clicks matched baselines - safe to mark success
            await click_success_button()
            return True
        else:
            # Validation failed - report failure
            await click_failed_button()
            log_failure(
                workflow=workflow_name,
                post_id=post_id,
                failed_at=result.failure_index,
                reason=result.failure_reason
            )
            return False
            
    except Exception as e:
        # Error during execution
        await click_failed_button()
        return False
```

---

## Initial Setup Process

### Step 1: Create Database and Register Workflows

```python
from workflow_validation import ValidationDatabase, WorkflowParser, BaselineManager

# Create database
db = ValidationDatabase('/home/user/workflow-validation/validation.db')

# Register workflows
parser = WorkflowParser('/home/user/workflow-validation/workflows')
manager = BaselineManager(db, screenshot, parser)

for json_file in ['facebook-default.json', 'linkedin-default.json', 
                   'instagram-default.json', 'skool-default.json']:
    manager.register_workflow(f'/path/to/workflows/{json_file}')
```

### Step 2: Create Initial Baselines

**Option A: From First Successful Run**
```python
# Run workflow once manually, capture screenshots
screenshots = {}
for action_index in workflow_click_indices:
    # Capture before each click
    screenshots[action_index] = capture_screenshot_at_click(action_index)
    # Perform click
    perform_click(action_index)

# Save as baselines
manager.create_baselines_from_screenshots('facebook-default', screenshots)
```

**Option B: Interactive Capture**
```python
# Human runs through workflow, system captures
manager.create_baselines_interactive(
    'facebook-default',
    callback_before_click=lambda idx, x, y: print(f"About to click {idx} at ({x},{y})"),
    callback_after_click=lambda idx: input("Press Enter when ready for next...")
)
```

---

## Future: Self-Healing Placeholder

The database schema includes a `workflow_corrections` table for future self-healing. Here's the intended workflow:

```
1. Validation fails 3 times in a row at action index N

2. System flags for self-healing:
   - Store the expected baseline
   - Store what was actually captured
   - Human reviews and either:
     a) Confirms UI changed → record new coordinates/baseline
     b) Identifies transient issue → retry without change

3. If coordinates changed:
   - Update workflow JSON with new coordinates
   - Create new baseline at new location
   - Log correction in workflow_corrections table

4. Future runs use corrected coordinates
```

This is NOT implemented yet, but the database structure supports it.

---

## Testing Checklist

Before deploying, verify:

- [ ] SQLite database created successfully
- [ ] Workflows registered from JSON files  
- [ ] Screenshot capture produces 100x100 PNG
- [ ] Image comparison returns reasonable scores
- [ ] Baselines can be created and retrieved
- [ ] Validation correctly identifies matching images
- [ ] Validation correctly identifies mismatching images
- [ ] Run tracking records all screenshots
- [ ] Failure detection identifies correct action index
- [ ] Integration with workflow runner works end-to-end

---

## File Listing Summary

Create these files:

```
/home/user/workflow-validation/
├── validation.db                     # Created by database.py
├── config.yaml                       # Configuration (copy from above)
├── src/
│   ├── __init__.py                   # Export all classes
│   ├── database.py                   # SQLite operations
│   ├── screenshot_capture.py         # VNC screenshot + crop
│   ├── image_comparator.py           # Fast image comparison
│   ├── workflow_parser.py            # Parse JSON workflows
│   ├── validator.py                  # Main validation logic
│   ├── baseline_manager.py           # Create/update baselines
│   └── run_tracker.py                # (optional) Additional tracking
└── tests/
    └── test_validation.py            # Unit tests
```

---

## Critical Implementation Notes

1. **Screenshot Timing**: Capture BEFORE the click executes, not after
2. **100x100 Box**: Centered on click coordinates
3. **Edge Handling**: Pad with black if click is near screen edge  
4. **Quick Comparison**: Hash check first, then pixel/SSIM only if hashes differ
5. **First Run**: No validation (no baselines exist yet)
6. **Failure Point**: Record the FIRST failing click, not all failures
7. **Database Writes**: Save screenshots immediately (crash recovery)
8. **Threshold**: Default 95%, adjustable per-baseline for dynamic areas

---

## Success Criteria

The system is working when:

1. Every workflow run captures screenshots at each click point
2. Screenshots are stored in SQLite (recoverable)
3. Before success button, all screenshots are compared to baselines
4. Mismatches are detected with exact action index
5. Failed workflows are reported (not marked as success)
6. System can identify when 3+ consecutive failures occur at same point
7. Performance: Validation adds <2 seconds to workflow runtime