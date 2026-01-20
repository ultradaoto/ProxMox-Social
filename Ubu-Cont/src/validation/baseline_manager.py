"""
Manage baseline images - create, update, and maintain.
"""
import logging
from typing import List, Optional, Callable
from pathlib import Path

from .database import ValidationDatabase
from .screenshot_capture import ScreenshotCapture
from .workflow_parser import WorkflowParser, WorkflowInfo


class BaselineManager:
    """
    Manages baseline images for workflows.
    
    Usage:
        manager = BaselineManager(db, screenshot, parser)
        
        # Register workflow
        manager.register_workflow('/path/to/facebook_default.json')
        
        # Create baselines from successful run
        manager.create_baselines_from_screenshots('facebook_default', screenshots)
        
        # Update single baseline
        manager.update_baseline('facebook_default', action_index=5, new_image)
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
    
    def register_all_workflows(self, recordings_dir: str) -> List[int]:
        """
        Register all workflow JSON files in a directory.
        
        Args:
            recordings_dir: Directory containing workflow JSON files
            
        Returns:
            List of workflow IDs
        """
        recordings_path = Path(recordings_dir)
        workflow_ids = []
        
        for json_file in recordings_path.glob('*.json'):
            try:
                workflow_id = self.register_workflow(str(json_file))
                workflow_ids.append(workflow_id)
            except Exception as e:
                self.logger.error(f"Failed to register {json_file}: {e}")
        
        return workflow_ids
    
    def create_baselines_interactive(
        self,
        workflow_name: str,
        callback_before_click: Callable[[int, int, int], None] = None,
        callback_after_click: Callable[[int], None] = None
    ) -> int:
        """
        Create baselines by running workflow with human guidance.
        
        Args:
            workflow_name: Name of workflow
            callback_before_click: Called before each click with (action_index, x, y)
            callback_after_click: Called after each click with (action_index)
            
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
            if callback_before_click:
                callback_before_click(click.index, click.x, click.y)
            
            image_data, _ = self.screenshot.capture_before_click(click.x, click.y)
            
            if image_data:
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
            
            if callback_after_click:
                callback_after_click(click.index)
        
        self.logger.info(f"Created {created_count} baselines for '{workflow_name}'")
        return created_count
    
    def create_baselines_from_screenshots(
        self,
        workflow_name: str,
        screenshots: dict
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
    
    def create_baseline_from_run(
        self,
        workflow_name: str,
        run_id: int
    ) -> int:
        """
        Create baselines from a successful run's screenshots.
        
        Args:
            workflow_name: Name of workflow
            run_id: ID of the successful run
            
        Returns:
            Number of baselines created
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        screenshots = self.db.get_run_screenshots(run_id)
        if not screenshots:
            self.logger.warning(f"No screenshots found for run {run_id}")
            return 0
        
        info = self.parser.parse_file(workflow['json_path'])
        click_map = {c.index: c for c in info.click_actions}
        
        created_count = 0
        for ss in screenshots:
            action_index = ss['action_index']
            click = click_map.get(action_index)
            
            if click:
                self.db.save_baseline(
                    workflow_id=workflow['id'],
                    action_index=action_index,
                    action_type=click.action_type,
                    click_x=ss['click_x'],
                    click_y=ss['click_y'],
                    image_data=ss['captured_image'],
                    description=click.description
                )
                created_count += 1
        
        self.logger.info(f"Created {created_count} baselines from run {run_id}")
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
            info = self.parser.parse_file(workflow['json_path'])
            click = next((c for c in info.click_actions if c.index == action_index), None)
            if not click:
                raise ValueError(f"No click action at index {action_index}")
            
            self.db.save_baseline(
                workflow_id=workflow['id'],
                action_index=action_index,
                action_type=click.action_type,
                click_x=new_x or click.x,
                click_y=new_y or click.y,
                image_data=new_image,
                description=click.description
            )
        else:
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
            "missing_indices": sorted(missing),
            "covered_indices": sorted(covered)
        }
    
    def delete_baseline(self, workflow_name: str, action_index: int) -> bool:
        """Delete a specific baseline."""
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            return False
        
        # Would need to add a delete method to database.py
        self.logger.info(f"Deleted baseline for {workflow_name} action {action_index}")
        return True
    
    def export_baselines(self, workflow_name: str, output_dir: str) -> int:
        """
        Export baselines to PNG files for inspection.
        
        Args:
            workflow_name: Name of workflow
            output_dir: Directory to export to
            
        Returns:
            Number of files exported
        """
        workflow = self.db.get_workflow(workflow_name)
        if not workflow:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        baselines = self.db.get_baselines(workflow['id'])
        exported = 0
        
        for baseline in baselines:
            filename = f"{workflow_name}_action{baseline['action_index']:02d}_{baseline['click_x']}x{baseline['click_y']}.png"
            filepath = output_path / filename
            
            with open(filepath, 'wb') as f:
                f.write(baseline['baseline_image'])
            exported += 1
        
        self.logger.info(f"Exported {exported} baselines to {output_dir}")
        return exported
