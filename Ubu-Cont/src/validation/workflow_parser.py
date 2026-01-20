"""
Parse JSON workflow files and extract click actions.
"""
import json
from typing import List, Optional
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ClickAction:
    """Represents a click action in a workflow."""
    index: int
    action_type: str
    x: int
    y: int
    description: Optional[str]
    
    
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
    
    CLICK_ACTIONS = {'click', 'double_click', 'doubleclick', 'right_click', 'rightclick'}
    SKIP_ACTIONS = {'wait', 'key', 'type', 'scroll', 'delay', 'paste', 'wait_for_change'}
    
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
        
        name = path.stem
        platform = data.get('platform', name.split('_')[0] if '_' in name else name.split('-')[0])
        
        actions = data.get('actions', data.get('steps', []))
        click_actions = []
        
        for i, action in enumerate(actions):
            action_type = action.get('type', action.get('action', ''))
            
            if action_type.lower() in self.CLICK_ACTIONS:
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
    
    def get_click_coords(self, json_path: str) -> List[tuple]:
        """Get list of (action_index, x, y) for all clicks."""
        info = self.parse_file(json_path)
        return [(click.index, click.x, click.y) for click in info.click_actions]
