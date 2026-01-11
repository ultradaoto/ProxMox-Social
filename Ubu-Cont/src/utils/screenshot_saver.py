"""
Screenshot Saver - Saves screenshots for debugging.

This module handles saving screenshots with proper naming
and directory organization for debugging purposes.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
from PIL import Image

from src.utils.logger import get_logger

logger = get_logger(__name__)


class ScreenshotSaver:
    """Handles saving screenshots for debugging."""
    
    def __init__(self, base_dir: str = "logs/screenshots"):
        """
        Initialize screenshot saver.
        
        Args:
            base_dir: Base directory for saving screenshots
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session directory with timestamp
        self.session_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.base_dir / self.session_timestamp
        self.session_dir.mkdir(exist_ok=True)
        
        self.screenshot_count = 0
    
    def save(
        self,
        image: Image.Image,
        step_name: str,
        post_id: Optional[str] = None,
        suffix: str = ""
    ) -> Path:
        """
        Save a screenshot.
        
        Args:
            image: PIL Image to save
            step_name: Name of the current step
            post_id: Optional post ID for organization
            suffix: Optional suffix for filename
            
        Returns:
            Path to saved file
        """
        self.screenshot_count += 1
        
        # Clean step name for filename
        clean_step = step_name.replace(" ", "_").replace("/", "_")
        
        # Build filename
        parts = [
            f"{self.screenshot_count:04d}",
            clean_step
        ]
        
        if post_id:
            parts.insert(1, post_id[:8])  # First 8 chars of post ID
        
        if suffix:
            parts.append(suffix)
        
        filename = "_".join(parts) + ".png"
        filepath = self.session_dir / filename
        
        # Save image
        image.save(filepath)
        logger.debug(f"Screenshot saved: {filepath}")
        
        return filepath
    
    def save_error(
        self,
        image: Image.Image,
        error_description: str,
        post_id: Optional[str] = None
    ) -> Path:
        """
        Save an error screenshot.
        
        Args:
            image: PIL Image to save
            error_description: Brief error description
            post_id: Optional post ID
            
        Returns:
            Path to saved file
        """
        return self.save(
            image,
            "ERROR",
            post_id,
            error_description[:30].replace(" ", "_")
        )
    
    def get_session_dir(self) -> Path:
        """Get the current session's screenshot directory."""
        return self.session_dir
    
    def get_screenshot_count(self) -> int:
        """Get the number of screenshots saved this session."""
        return self.screenshot_count
    
    def create_post_subdir(self, post_id: str) -> Path:
        """
        Create a subdirectory for a specific post.
        
        Args:
            post_id: Post ID
            
        Returns:
            Path to post directory
        """
        post_dir = self.session_dir / post_id[:16]
        post_dir.mkdir(exist_ok=True)
        return post_dir


# Global instance for convenience
_global_saver: Optional[ScreenshotSaver] = None


def get_screenshot_saver() -> ScreenshotSaver:
    """Get or create the global screenshot saver."""
    global _global_saver
    if _global_saver is None:
        _global_saver = ScreenshotSaver()
    return _global_saver


def save_screenshot(
    image: Image.Image,
    step_name: str,
    post_id: Optional[str] = None
) -> Path:
    """
    Convenience function to save a screenshot.
    
    Args:
        image: PIL Image to save
        step_name: Name of the current step
        post_id: Optional post ID
        
    Returns:
        Path to saved file
    """
    saver = get_screenshot_saver()
    return saver.save(image, step_name, post_id)
