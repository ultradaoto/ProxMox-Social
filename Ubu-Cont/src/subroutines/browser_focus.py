"""
Browser Focus Subroutine - Ensures Chrome is focused and ready.

This subroutine is called to ensure Chrome browser is in the foreground
and ready to receive input commands.
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.subsystems.vnc_capture import VNCCapture
    from src.subsystems.vision_engine import VisionEngine
    from src.subsystems.input_injector import InputInjector

logger = get_logger(__name__)


class BrowserFocusSubroutine:
    """Ensures Chrome browser is focused and ready."""
    
    def __init__(
        self,
        vnc: "VNCCapture",
        vision: "VisionEngine",
        input_injector: "InputInjector"
    ):
        """
        Initialize browser focus subroutine.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        
        self.max_attempts = 3
    
    async def execute(self) -> bool:
        """
        Ensure Chrome browser is focused.
        
        Returns:
            True if Chrome is focused and ready
        """
        logger.info("Ensuring Chrome browser is focused")
        
        for attempt in range(self.max_attempts):
            # Take screenshot
            screenshot = await self.vnc.capture()
            if not screenshot:
                logger.error("Failed to capture screenshot")
                await asyncio.sleep(1)
                continue
            
            # Check if Chrome is already focused
            state = await self.vision.verify_screen_state(
                screenshot,
                "Chrome browser window in the foreground with address bar visible"
            )
            
            if state.is_match:
                logger.info("Chrome is already focused")
                return True
            
            # Try to focus Chrome
            logger.info(f"Attempting to focus Chrome (attempt {attempt + 1})")
            
            # Method 1: Click on Chrome in taskbar
            chrome_taskbar = await self.vision.find_element(
                screenshot,
                "Chrome icon in the Windows taskbar at the bottom of the screen"
            )
            
            if chrome_taskbar:
                await self.input.click_at(chrome_taskbar.x, chrome_taskbar.y)
                await asyncio.sleep(1)
                continue
            
            # Method 2: Use Alt+Tab
            logger.info("Trying Alt+Tab to switch to Chrome")
            await self.input.key_combo("alt", "tab")
            await asyncio.sleep(1)
            
        # Final check
        screenshot = await self.vnc.capture()
        if screenshot:
            state = await self.vision.verify_screen_state(
                screenshot,
                "Chrome browser window in the foreground"
            )
            return state.is_match
        
        return False
    
    async def open_url(self, url: str) -> bool:
        """
        Open a URL in Chrome.
        
        Args:
            url: URL to open
            
        Returns:
            True if URL was opened
        """
        logger.info(f"Opening URL: {url}")
        
        # First ensure Chrome is focused
        if not await self.execute():
            logger.error("Failed to focus Chrome")
            return False
        
        # Use Ctrl+L to focus address bar
        await self.input.key_combo("ctrl", "l")
        await asyncio.sleep(0.3)
        
        # Select all in address bar
        await self.input.select_all()
        await asyncio.sleep(0.2)
        
        # Type URL
        await self.input.type_text(url)
        await asyncio.sleep(0.3)
        
        # Press Enter
        await self.input.enter()
        
        logger.info("URL opened")
        return True
    
    async def wait_for_page_load(self, expected_content: str, timeout: int = 30) -> bool:
        """
        Wait for page to load with expected content.
        
        Args:
            expected_content: Description of what to look for
            timeout: Maximum seconds to wait
            
        Returns:
            True if page loaded with expected content
        """
        logger.info(f"Waiting for page to load: {expected_content}")
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            screenshot = await self.vnc.capture()
            if not screenshot:
                await asyncio.sleep(1)
                continue
            
            state = await self.vision.verify_screen_state(
                screenshot,
                expected_content
            )
            
            if state.is_match:
                logger.info("Page loaded successfully")
                return True
            
            await asyncio.sleep(2)
        
        logger.warning(f"Page did not load within {timeout}s")
        return False
    
    async def close_popup_if_present(self) -> bool:
        """
        Close any popup dialogs that might be blocking.
        
        Returns:
            True if a popup was closed or no popup was present
        """
        screenshot = await self.vnc.capture()
        if not screenshot:
            return True
        
        # Look for common popup close buttons
        close_button = await self.vision.find_element(
            screenshot,
            "close button (X) on a popup dialog or modal"
        )
        
        if close_button:
            logger.info("Closing popup dialog")
            await self.input.click_at(close_button.x, close_button.y)
            await asyncio.sleep(0.5)
            return True
        
        # Try pressing Escape
        await self.input.escape()
        await asyncio.sleep(0.3)
        
        return True
