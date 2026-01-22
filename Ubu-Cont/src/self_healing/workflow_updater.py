"""
Updates workflow JSON files with corrected coordinates.
"""
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
import logging

from .config import RECORDINGS_DIR, WORKFLOW_BACKUP_DIR

logger = logging.getLogger(__name__)


class WorkflowUpdater:
    """Manages updates to workflow JSON files."""
    
    def __init__(self, workflow_name: str):
        """
        Args:
            workflow_name: Name like 'instagram_default' (without .json)
        """
        self.workflow_name = workflow_name
        self.workflow_path = Path(RECORDINGS_DIR) / f"{workflow_name}.json"
        self.backup_dir = Path(WORKFLOW_BACKUP_DIR)
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
        """Create timestamped backup."""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"{self.workflow_name}.{timestamp}.json"
        shutil.copy2(self.workflow_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        return backup_path
    
    def get_action(self, workflow: Dict, action_index: int) -> Optional[Dict]:
        """Get specific action from workflow."""
        actions = workflow.get('actions', [])
        if 0 <= action_index < len(actions):
            return actions[action_index]
        return None
    
    def get_click_action_by_click_index(self, click_index: int) -> Tuple[Optional[int], Optional[Dict]]:
        """
        Get action by click index (not overall action index).
        Returns (action_index, action) or (None, None).
        """
        workflow = self.load_workflow()
        actions = workflow.get('actions', [])
        
        current_click = 0
        for i, action in enumerate(actions):
            action_type = action.get('type', '').lower()
            if action_type in ('click', 'double_click', 'right_click'):
                if current_click == click_index:
                    return i, action
                current_click += 1
        
        return None, None
    
    def update_coordinates(
        self,
        action_index: int,
        new_x: int,
        new_y: int,
        create_backup: bool = True
    ) -> Dict[str, Any]:
        """Update coordinates for a specific action."""
        if create_backup:
            self.create_backup()
        
        workflow = self.load_workflow()
        self._original_state = json.loads(json.dumps(workflow))
        
        actions = workflow.get('actions', [])
        if action_index >= len(actions):
            raise ValueError(f"Action index {action_index} out of range")
        
        action = actions[action_index]
        old_x = action.get('x')
        old_y = action.get('y')
        
        logger.info(f"Updating {self.workflow_name} action {action_index}: ({old_x}, {old_y}) -> ({new_x}, {new_y})")
        
        action['x'] = new_x
        action['y'] = new_y
        
        # Add healing history
        if '_healing_history' not in action:
            action['_healing_history'] = []
        action['_healing_history'].append({
            'timestamp': datetime.now().isoformat(),
            'old_x': old_x,
            'old_y': old_y,
            'new_x': new_x,
            'new_y': new_y
        })
        
        self.save_workflow(workflow)
        return workflow
    
    def update_coordinates_by_click_index(
        self,
        click_index: int,
        new_x: int,
        new_y: int,
        create_backup: bool = True
    ) -> bool:
        """Update coordinates using click index instead of action index."""
        action_index, action = self.get_click_action_by_click_index(click_index)
        if action_index is None:
            logger.error(f"Click index {click_index} not found in workflow")
            return False
        
        self.update_coordinates(action_index, new_x, new_y, create_backup)
        return True
    
    def rollback(self) -> bool:
        """Rollback to state before last update."""
        if self._original_state is None:
            logger.warning("No state to rollback to")
            return False
        
        self.save_workflow(self._original_state)
        logger.info("Rolled back to previous state")
        self._original_state = None
        return True
    
    def get_coordinates(self, action_index: int) -> Optional[Tuple[int, int]]:
        """Get current coordinates for an action."""
        workflow = self.load_workflow()
        action = self.get_action(workflow, action_index)
        if action and 'x' in action and 'y' in action:
            return (action['x'], action['y'])
        return None
    
    def get_coordinates_by_click_index(self, click_index: int) -> Optional[Tuple[int, int]]:
        """Get coordinates using click index."""
        action_index, action = self.get_click_action_by_click_index(click_index)
        if action and 'x' in action and 'y' in action:
            return (action['x'], action['y'])
        return None
    
    def list_click_actions(self) -> List[Dict]:
        """List all click actions with their indices."""
        workflow = self.load_workflow()
        actions = workflow.get('actions', [])
        
        click_actions = []
        click_index = 0
        for i, action in enumerate(actions):
            action_type = action.get('type', '').lower()
            if action_type in ('click', 'double_click', 'right_click'):
                click_actions.append({
                    'action_index': i,
                    'click_index': click_index,
                    'type': action_type,
                    'x': action.get('x'),
                    'y': action.get('y'),
                    'description': action.get('description', f'Click {click_index}')
                })
                click_index += 1
        
        return click_actions
