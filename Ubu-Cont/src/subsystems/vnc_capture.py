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
from datetime import datetime
import io
import logging

from src.utils.logger import get_logger

logger = get_logger(__name__)


class VNCCapture:
    """Captures screenshots from Windows 10 VM via VNC."""
    
    def __init__(
        self,
        host: str = "192.168.100.20",
        port: int = 5900,
        password: Optional[str] = None,
        display: int = 0
    ):
        """
        Initialize VNC capture.
        
        Args:
            host: Windows 10 VM IP address
            port: VNC port
            password: VNC password (if required)
            display: VNC display number
        """
        self.host = host
        self.port = port
        self.password = password
        self.display = display
        self.connected = False
        
        # Temp directory for screenshots
        self.temp_dir = Path(tempfile.gettempdir()) / "vnc_captures"
        self.temp_dir.mkdir(exist_ok=True)
        
        # Screenshots save directory
        self.screenshots_dir: Optional[Path] = None
    
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
                logger.info(f"Screen resolution: {screenshot.size}")
                return True
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
        
        logger.warning("VNC connection will be established when running on Ubuntu VM")
        return False
    
    async def capture(self) -> Optional[Image.Image]:
        """
        Capture current screen from Windows 10 VM.
        
        Returns:
            PIL Image of the screen, or None if capture failed
        """
        output_path = self.temp_dir / f"capture_{int(datetime.now().timestamp() * 1000)}.png"
        
        try:
            # Use vncsnapshot to capture screen
            cmd = [
                "vncsnapshot",
                f"{self.host}:{self.display}",
                str(output_path)
            ]
            
            if self.password:
                cmd.extend(["-passwd", self.password])
            
            # Run vncsnapshot
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=10
            )
            
            if process.returncode == 0 and output_path.exists():
                image = Image.open(output_path)
                # Make a copy so we can delete the file
                image_copy = image.copy()
                image.close()
                
                # Cleanup temp file
                try:
                    output_path.unlink()
                except:
                    pass
                
                logger.debug(f"Captured screen: {image_copy.size}")
                return image_copy
            else:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"vncsnapshot failed: {error_msg}")
                
        except asyncio.TimeoutError:
            logger.error("VNC capture timed out")
        except FileNotFoundError:
            logger.warning("vncsnapshot not found, trying vncdotool")
            return await self._capture_with_vncdotool()
        except Exception as e:
            logger.exception(f"VNC capture error: {e}")
        finally:
            # Cleanup temp file if exists
            if output_path.exists():
                try:
                    output_path.unlink()
                except:
                    pass
        
        return None
    
    async def _capture_with_vncdotool(self) -> Optional[Image.Image]:
        """Alternative capture using vncdotool library."""
        try:
            from vncdotool import api as vnc_api
            import socket
            
            output_path = self.temp_dir / f"capture_{int(datetime.now().timestamp() * 1000)}.png"
            
            # Set timeout for connection
            socket.setdefaulttimeout(5)
            
            # Run in executor to not block
            def do_capture():
                client = vnc_api.connect(
                    f"{self.host}::{self.port}",
                    password=self.password
                )
                client.captureScreen(str(output_path))
                client.disconnect()
                
                if output_path.exists():
                    img = Image.open(output_path)
                    img_copy = img.copy()
                    img.close()
                    output_path.unlink()
                    return img_copy
                return None
            
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, do_capture)
                
        except ImportError:
            logger.error("vncdotool not installed. Install with: pip install vncdotool")
        except Exception as e:
            logger.error(f"vncdotool capture failed: {e}")
        
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
    
    def save_screenshot(self, image: Image.Image, name: str) -> Optional[Path]:
        """
        Save screenshot for debugging.
        
        Args:
            image: PIL Image to save
            name: Filename (without extension)
            
        Returns:
            Path to saved file
        """
        if not self.screenshots_dir:
            return None
        
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        save_path = self.screenshots_dir / f"{name}.png"
        image.save(save_path)
        logger.debug(f"Screenshot saved: {save_path}")
        return save_path
    
    def set_screenshots_dir(self, path: str):
        """Set directory for saving debug screenshots."""
        self.screenshots_dir = Path(path)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
