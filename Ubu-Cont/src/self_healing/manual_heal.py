"""
Manual healing trigger for testing and debugging.
Allows triggering heal attempts from the web UI.
"""
import os
import json
import time
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

from .events import get_healing_store
from .config import (
    SIMILARITY_FAILURE_THRESHOLD,
    RECORDINGS_DIR,
    DATABASE_PATH,
    WORKFLOW_ACTION_DESCRIPTIONS,
    OPENROUTER_API_KEY,
)
from .vision_locator import VisionLocator
from .workflow_updater import WorkflowUpdater


class ManualHealer:
    """
    Performs manual healing with detailed logging for UI monitoring.
    """
    
    def __init__(self):
        self.store = get_healing_store()
        self.locator = None
        self._init_locator()
    
    def _init_locator(self):
        """Initialize the vision locator."""
        api_key = OPENROUTER_API_KEY
        if not api_key:
            # Try config.json
            config_path = Path(__file__).parent.parent.parent / "config.json"
            if config_path.exists():
                try:
                    with open(config_path) as f:
                        config = json.load(f)
                        api_key = config.get("vision", {}).get("api_key", "")
                except Exception:
                    pass
        
        if api_key:
            self.locator = VisionLocator(api_key=api_key)
            self.store.log("INFO", "Vision locator initialized")
        else:
            self.store.log("ERROR", "No API key found - healing will fail")
    
    def _log(self, level: str, msg: str, workflow: str = None, click_index: int = None):
        """Log with store tracking."""
        self.store.log(level, msg, workflow, click_index)
    
    def get_workflow_clicks(self, workflow_name: str) -> List[Dict]:
        """Get all click actions from a workflow."""
        workflow_path = Path(RECORDINGS_DIR) / f"{workflow_name}.json"
        if not workflow_path.exists():
            return []
        
        with open(workflow_path) as f:
            data = json.load(f)
        
        clicks = []
        click_index = 0
        for i, action in enumerate(data.get('actions', [])):
            if action.get('type') in ('click', 'double_click', 'right_click'):
                clicks.append({
                    'action_index': i,
                    'click_index': click_index,
                    'x': action.get('x'),
                    'y': action.get('y'),
                    'type': action.get('type'),
                    'description': action.get('description', f'Click {click_index}')
                })
                click_index += 1
        
        return clicks
    
    def get_baselines(self, workflow_name: str) -> Dict[int, bytes]:
        """Get baseline images for a workflow."""
        baselines = {}
        try:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            
            # Get workflow ID
            workflow = conn.execute(
                'SELECT id FROM workflows WHERE name = ?',
                (workflow_name,)
            ).fetchone()
            
            if not workflow:
                return baselines
            
            rows = conn.execute('''
                SELECT action_index, baseline_image FROM click_baselines
                WHERE workflow_id = ?
            ''', (workflow['id'],)).fetchall()
            
            for row in rows:
                baselines[row['action_index']] = row['baseline_image']
            
            conn.close()
        except Exception as e:
            self._log("ERROR", f"Failed to get baselines: {e}", workflow_name)
        
        return baselines
    
    def capture_current_screenshot(self, x: int, y: int, box_size: int = 100) -> Optional[bytes]:
        """Capture current screenshot at coordinates."""
        from PIL import Image
        import io
        
        # Read from shared frame
        shared_path = "/dev/shm/vnc_latest.png"
        if not os.path.exists(shared_path):
            shared_path = "/tmp/vnc_latest.png"
        
        if not os.path.exists(shared_path):
            self._log("ERROR", f"No VNC frame available at {shared_path}")
            return None
        
        try:
            img = Image.open(shared_path)
            width, height = img.size
            
            half = box_size // 2
            left = max(0, x - half)
            top = max(0, y - half)
            right = min(width, x + half)
            bottom = min(height, y + half)
            
            cropped = img.crop((left, top, right, bottom))
            
            # Ensure exact size
            if cropped.size != (box_size, box_size):
                new_img = Image.new('RGB', (box_size, box_size), (0, 0, 0))
                paste_x = (box_size - cropped.size[0]) // 2
                paste_y = (box_size - cropped.size[1]) // 2
                new_img.paste(cropped, (paste_x, paste_y))
                cropped = new_img
            
            buffer = io.BytesIO()
            cropped.save(buffer, format='PNG')
            return buffer.getvalue()
            
        except Exception as e:
            self._log("ERROR", f"Failed to capture screenshot: {e}")
            return None
    
    def get_full_screenshot(self) -> Optional[bytes]:
        """Get full VNC screenshot."""
        shared_path = "/dev/shm/vnc_latest.png"
        if not os.path.exists(shared_path):
            shared_path = "/tmp/vnc_latest.png"
        
        if os.path.exists(shared_path):
            with open(shared_path, 'rb') as f:
                return f.read()
        return None
    
    def compare_images(self, img1: bytes, img2: bytes) -> float:
        """Compare two images and return similarity score."""
        from PIL import Image
        import io
        
        try:
            i1 = Image.open(io.BytesIO(img1)).convert('L')
            i2 = Image.open(io.BytesIO(img2)).convert('L')
            
            if i1.size != i2.size:
                i2 = i2.resize(i1.size)
            
            import numpy as np
            a1 = np.array(i1, dtype=np.float32)
            a2 = np.array(i2, dtype=np.float32)
            
            # Normalized cross-correlation
            a1_norm = (a1 - a1.mean()) / (a1.std() + 1e-10)
            a2_norm = (a2 - a2.mean()) / (a2.std() + 1e-10)
            
            correlation = np.mean(a1_norm * a2_norm)
            return float(correlation)
            
        except Exception as e:
            self._log("ERROR", f"Image comparison failed: {e}")
            return 0.0
    
    def scan_workflow(self, workflow_name: str) -> Dict[str, Any]:
        """
        Scan a workflow and identify clicks that need healing.
        Returns scan results with similarities.
        """
        self._log("INFO", f"=== Starting scan of {workflow_name} ===", workflow_name)
        
        clicks = self.get_workflow_clicks(workflow_name)
        if not clicks:
            self._log("ERROR", f"No clicks found in {workflow_name}", workflow_name)
            return {'error': 'No clicks found', 'clicks': []}
        
        self._log("INFO", f"Found {len(clicks)} click actions", workflow_name)
        
        baselines = self.get_baselines(workflow_name)
        self._log("INFO", f"Found {len(baselines)} baselines", workflow_name)
        
        results = []
        needs_healing = []
        
        for click in clicks:
            idx = click['click_index']
            x, y = click['x'], click['y']
            
            self._log("INFO", f"Checking click #{idx} at ({x}, {y})", workflow_name, idx)
            
            baseline = baselines.get(idx)
            if not baseline:
                self._log("WARN", f"No baseline for click #{idx}", workflow_name, idx)
                results.append({
                    **click,
                    'has_baseline': False,
                    'similarity': None,
                    'needs_healing': False
                })
                continue
            
            current = self.capture_current_screenshot(x, y)
            if not current:
                self._log("ERROR", f"Could not capture current screenshot for click #{idx}", workflow_name, idx)
                results.append({
                    **click,
                    'has_baseline': True,
                    'similarity': None,
                    'needs_healing': False,
                    'error': 'capture_failed'
                })
                continue
            
            similarity = self.compare_images(baseline, current)
            needs_heal = similarity < SIMILARITY_FAILURE_THRESHOLD
            
            status = "NEEDS HEALING" if needs_heal else "OK"
            self._log("INFO", f"Click #{idx}: similarity={similarity:.1%} - {status}", workflow_name, idx)
            
            result = {
                **click,
                'has_baseline': True,
                'similarity': similarity,
                'needs_healing': needs_heal
            }
            results.append(result)
            
            if needs_heal:
                needs_healing.append(result)
        
        self._log("INFO", f"=== Scan complete: {len(needs_healing)} clicks need healing ===", workflow_name)
        
        return {
            'workflow': workflow_name,
            'total_clicks': len(clicks),
            'with_baselines': len([r for r in results if r.get('has_baseline')]),
            'needs_healing': len(needs_healing),
            'threshold': SIMILARITY_FAILURE_THRESHOLD,
            'clicks': results
        }
    
    def heal_click(self, workflow_name: str, click_index: int, old_x: int, old_y: int, 
                   baseline: bytes, current: bytes, similarity: float) -> Dict[str, Any]:
        """
        Attempt to heal a single click using AI vision.
        """
        self._log("INFO", f"=== Healing click #{click_index} ===", workflow_name, click_index)
        self._log("INFO", f"Old coords: ({old_x}, {old_y}), Similarity: {similarity:.1%}", workflow_name, click_index)
        
        if not self.locator:
            self._log("ERROR", "Vision locator not initialized", workflow_name, click_index)
            return {'success': False, 'error': 'No vision locator'}
        
        # Get action description
        descriptions = WORKFLOW_ACTION_DESCRIPTIONS.get(workflow_name, {})
        description = descriptions.get(click_index, f"Click action #{click_index}")
        self._log("INFO", f"Action description: {description}", workflow_name, click_index)
        
        # Get full screenshot
        self._log("INFO", "Capturing full screenshot...", workflow_name, click_index)
        full_screenshot = self.get_full_screenshot()
        if not full_screenshot:
            self._log("ERROR", "Could not capture full screenshot", workflow_name, click_index)
            return {'success': False, 'error': 'No screenshot'}
        
        # Track event
        event_id = self.store.start_healing(workflow_name, click_index, similarity, (old_x, old_y))
        
        # Call AI
        self._log("INFO", "Sending to AI vision model...", workflow_name, click_index)
        self._log("INFO", f"Asking AI: Where is '{description}'?", workflow_name, click_index)
        self.store.update_ai_request(event_id)
        
        start_time = time.time()
        result = self.locator.locate_element(
            full_screenshot=full_screenshot,
            action_description=description,
            old_x=old_x,
            old_y=old_y,
            baseline_image=baseline,
            failed_image=current
        )
        elapsed = time.time() - start_time
        
        self._log("INFO", f"AI response received in {elapsed:.1f}s", workflow_name, click_index)
        
        if not result.success:
            self._log("ERROR", f"AI could not locate element: {result.reasoning}", workflow_name, click_index)
            self.store.complete_failed(event_id, result.reasoning, int(elapsed * 1000))
            return {
                'success': False,
                'error': result.reasoning,
                'raw_response': result.raw_response
            }
        
        new_x, new_y = result.new_x, result.new_y
        self._log("INFO", f"AI found element at ({new_x}, {new_y}) with {result.confidence:.1%} confidence", workflow_name, click_index)
        self._log("INFO", f"AI reasoning: {result.reasoning}", workflow_name, click_index)
        
        self.store.update_ai_response(event_id, (new_x, new_y), result.confidence, result.reasoning)
        
        # Update workflow
        self._log("INFO", f"Updating workflow: ({old_x}, {old_y}) -> ({new_x}, {new_y})", workflow_name, click_index)
        try:
            updater = WorkflowUpdater(workflow_name)
            updater.update_coordinates_by_click_index(click_index, new_x, new_y)
            self._log("INFO", "Workflow updated successfully!", workflow_name, click_index)
            self.store.complete_success(event_id, int(elapsed * 1000))
            
            return {
                'success': True,
                'old_coords': (old_x, old_y),
                'new_coords': (new_x, new_y),
                'confidence': result.confidence,
                'reasoning': result.reasoning
            }
        except Exception as e:
            self._log("ERROR", f"Failed to update workflow: {e}", workflow_name, click_index)
            self.store.complete_failed(event_id, str(e), int(elapsed * 1000))
            return {'success': False, 'error': str(e)}
    
    def heal_workflow(self, workflow_name: str, click_indices: List[int] = None) -> Dict[str, Any]:
        """
        Heal specified clicks or all clicks that need healing.
        """
        self._log("INFO", f"=== Starting full heal for {workflow_name} ===", workflow_name)
        
        # First scan
        scan_result = self.scan_workflow(workflow_name)
        if 'error' in scan_result:
            return scan_result
        
        # Determine which clicks to heal
        clicks_to_heal = []
        baselines = self.get_baselines(workflow_name)
        
        for click in scan_result['clicks']:
            if not click.get('needs_healing'):
                continue
            if click_indices and click['click_index'] not in click_indices:
                continue
            clicks_to_heal.append(click)
        
        if not clicks_to_heal:
            self._log("INFO", "No clicks need healing", workflow_name)
            return {
                'workflow': workflow_name,
                'healed': 0,
                'failed': 0,
                'results': [],
                'message': 'No clicks needed healing'
            }
        
        self._log("INFO", f"Healing {len(clicks_to_heal)} clicks...", workflow_name)
        
        results = []
        healed = 0
        failed = 0
        
        for click in clicks_to_heal:
            idx = click['click_index']
            baseline = baselines.get(idx)
            current = self.capture_current_screenshot(click['x'], click['y'])
            
            if not baseline or not current:
                self._log("WARN", f"Skipping click #{idx} - missing images", workflow_name, idx)
                continue
            
            result = self.heal_click(
                workflow_name=workflow_name,
                click_index=idx,
                old_x=click['x'],
                old_y=click['y'],
                baseline=baseline,
                current=current,
                similarity=click['similarity']
            )
            
            result['click_index'] = idx
            results.append(result)
            
            if result['success']:
                healed += 1
            else:
                failed += 1
        
        self._log("INFO", f"=== Heal complete: {healed} healed, {failed} failed ===", workflow_name)
        
        return {
            'workflow': workflow_name,
            'healed': healed,
            'failed': failed,
            'results': results
        }


# Singleton
_manual_healer: Optional[ManualHealer] = None

def get_manual_healer() -> ManualHealer:
    global _manual_healer
    if _manual_healer is None:
        _manual_healer = ManualHealer()
    return _manual_healer
