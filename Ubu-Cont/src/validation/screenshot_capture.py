"""
VNC screenshot capture with region cropping.
"""
import io
from typing import Tuple, Optional
from PIL import Image, ImageDraw
import numpy as np


class ScreenshotCapture:
    """Captures and crops screenshots via VNC."""
    
    def __init__(self, vnc_capture, box_size: int = 100):
        """
        Initialize screenshot capture.
        
        Args:
            vnc_capture: VNCCapture instance (from subsystems/vnc_capture.py)
            box_size: Size of square capture box (default 100x100)
        """
        self.vnc = vnc_capture
        self.box_size = box_size
    
    def capture_full_screen(self) -> Optional[Image.Image]:
        """
        Capture full screen via VNC.
        
        Returns:
            PIL Image of full screen or None if capture fails
        """
        import os
        
        # Primary method: Read from shared frame file (most reliable)
        # This is updated by vnc_stream_server's capture process
        shared_path = "/dev/shm/vnc_latest.png" if os.path.exists("/dev/shm") else "/tmp/vnc_latest.png"
        if os.path.exists(shared_path):
            try:
                return Image.open(shared_path).convert('RGB')
            except Exception as e:
                pass  # Fall through to other methods
        
        # Fallback: Try VNC object methods
        frame = None
        
        # Method 1: capture_frame() - used by vnc_stream_server shared frame
        if hasattr(self.vnc, 'capture_frame'):
            frame = self.vnc.capture_frame()
        # Method 2: capture() - used by VNCCapture class (async)
        elif hasattr(self.vnc, 'capture'):
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(asyncio.run, self.vnc.capture())
                        frame = future.result(timeout=5)
                else:
                    frame = asyncio.run(self.vnc.capture())
            except Exception:
                frame = None
        
        if frame is None:
            return None
        
        if isinstance(frame, bytes):
            return Image.open(io.BytesIO(frame))
        elif isinstance(frame, np.ndarray):
            return Image.fromarray(frame)
        elif isinstance(frame, Image.Image):
            return frame
        else:
            return frame
    
    def capture_click_region(
        self,
        click_x: int,
        click_y: int,
        full_screen: Image.Image = None,
        draw_crosshair: bool = True
    ) -> Optional[bytes]:
        """
        Capture region around click coordinates.
        
        Args:
            click_x: X coordinate of click
            click_y: Y coordinate of click
            full_screen: Optional pre-captured full screen image
            draw_crosshair: Whether to draw a + at the click point
            
        Returns:
            PNG image bytes of the region, or None if capture fails
        """
        if full_screen is None:
            full_screen = self.capture_full_screen()
        
        if full_screen is None:
            return None
        
        half_box = self.box_size // 2
        screen_width, screen_height = full_screen.size
        
        left = max(0, click_x - half_box)
        top = max(0, click_y - half_box)
        right = min(screen_width, click_x + half_box)
        bottom = min(screen_height, click_y + half_box)
        
        region = full_screen.crop((left, top, right, bottom))
        
        if region.size != (self.box_size, self.box_size):
            padded = Image.new('RGB', (self.box_size, self.box_size), (0, 0, 0))
            paste_x = (self.box_size - region.size[0]) // 2
            paste_y = (self.box_size - region.size[1]) // 2
            padded.paste(region, (paste_x, paste_y))
            region = padded
        
        # Draw crosshair at click point
        if draw_crosshair:
            region = self._draw_crosshair(region, click_x, click_y, left, top)
        
        buffer = io.BytesIO()
        region.save(buffer, format='PNG', compress_level=6)
        return buffer.getvalue()
    
    def _draw_crosshair(
        self,
        region: Image.Image,
        click_x: int,
        click_y: int,
        region_left: int,
        region_top: int
    ) -> Image.Image:
        """Draw a crosshair (+) at the click point."""
        region = region.copy()
        draw = ImageDraw.Draw(region)
        
        # Calculate click position within the region
        cx = click_x - region_left
        cy = click_y - region_top
        
        # Crosshair size
        size = 8
        thickness = 2
        
        # Draw red crosshair with white outline for visibility
        # White outline
        for offset in range(-1, 2):
            draw.line([(cx - size, cy + offset), (cx + size, cy + offset)], fill='white', width=1)
            draw.line([(cx + offset, cy - size), (cx + offset, cy + size)], fill='white', width=1)
        
        # Red cross
        draw.line([(cx - size + 1, cy), (cx + size - 1, cy)], fill='red', width=thickness)
        draw.line([(cx, cy - size + 1), (cx, cy + size - 1)], fill='red', width=thickness)
        
        return region
    
    def capture_before_click(
        self,
        click_x: int,
        click_y: int
    ) -> Tuple[Optional[bytes], Optional[Image.Image]]:
        """
        Capture screenshot before performing click.
        
        Returns:
            Tuple of (region_bytes, full_screen_image)
        """
        full_screen = self.capture_full_screen()
        if full_screen is None:
            return None, None
        
        region = self.capture_click_region(click_x, click_y, full_screen)
        return region, full_screen
    
    def capture_multiple_regions(
        self,
        click_coords: list,
        full_screen: Image.Image = None
    ) -> dict:
        """
        Capture multiple regions from a single screenshot.
        
        Args:
            click_coords: List of (action_index, x, y) tuples
            full_screen: Optional pre-captured screenshot
            
        Returns:
            Dict mapping action_index to image bytes
        """
        if full_screen is None:
            full_screen = self.capture_full_screen()
        
        if full_screen is None:
            return {}
        
        regions = {}
        for action_index, x, y in click_coords:
            region = self.capture_click_region(x, y, full_screen)
            if region:
                regions[action_index] = region
        
        return regions
