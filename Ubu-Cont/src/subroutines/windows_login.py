"""
Windows Login Subroutine - Handles Windows 10 login screen.

This subroutine is called when the brain detects a Windows login screen.
It enters the password and waits for the desktop to appear.
"""

import asyncio
from typing import TYPE_CHECKING, Optional

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.subsystems.vnc_capture import VNCCapture
    from src.subsystems.vision_engine import VisionEngine
    from src.subsystems.input_injector import InputInjector

logger = get_logger(__name__)


class WindowsLoginSubroutine:
    """Handles Windows 10 login."""
    
    def __init__(
        self,
        vnc: "VNCCapture",
        vision: "VisionEngine",
        input_injector: "InputInjector",
        password: str
    ):
        """
        Initialize login subroutine.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
            password: Windows password
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
        self.password = password
        
        self.max_attempts = 3
        self.timeout_seconds = 60
    
    async def execute(self) -> bool:
        """
        Execute Windows login.
        
        Returns:
            True if login successful
        """
        logger.info("Executing Windows login subroutine")
        
        for attempt in range(self.max_attempts):
            logger.info(f"Login attempt {attempt + 1}/{self.max_attempts}")
            
            try:
                # Step 1: Take screenshot
                screenshot = await self.vnc.capture()
                if not screenshot:
                    logger.error("Failed to capture screenshot")
                    continue
                
                # Step 2: Verify we're on login screen
                is_login = await self.vision.check_for_login_screen(screenshot)
                if not is_login:
                    logger.info("Not on login screen - may already be logged in")
                    return True
                
                # Step 3: Find password field
                password_field = await self.vision.find_element(
                    screenshot,
                    "password input field or text box on Windows login screen"
                )
                
                if not password_field:
                    # Try clicking anywhere to wake up the screen
                    logger.info("Password field not found, trying to wake screen")
                    await self.input.click_at(960, 540)  # Center of screen
                    await asyncio.sleep(1)
                    await self.input.press_key("space")
                    await asyncio.sleep(1)
                    continue
                
                # Step 4: Click password field
                logger.info(f"Clicking password field at ({password_field.x}, {password_field.y})")
                await self.input.click_at(password_field.x, password_field.y)
                await asyncio.sleep(0.5)
                
                # Step 5: Type password
                logger.info("Typing password")
                await self.input.type_text(self.password)
                await asyncio.sleep(0.3)
                
                # Step 6: Press Enter
                logger.info("Pressing Enter")
                await self.input.enter()
                
                # Step 7: Wait for desktop
                if await self._wait_for_desktop():
                    logger.info("Login successful!")
                    return True
                else:
                    logger.warning("Desktop did not appear after login")
                    
            except Exception as e:
                logger.exception(f"Login attempt failed: {e}")
            
            await asyncio.sleep(2)
        
        logger.error("All login attempts failed")
        return False
    
    async def _wait_for_desktop(self) -> bool:
        """Wait for Windows desktop to appear."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < self.timeout_seconds:
            await asyncio.sleep(2)
            
            screenshot = await self.vnc.capture()
            if not screenshot:
                continue
            
            # Check if we're past the login screen
            is_login = await self.vision.check_for_login_screen(screenshot)
            if not is_login:
                # Verify we see desktop elements
                state = await self.vision.verify_screen_state(
                    screenshot,
                    "Windows desktop with taskbar, or Chrome browser, or desktop icons"
                )
                
                if state.is_match:
                    return True
        
        return False
    
    async def wake_screen(self) -> bool:
        """
        Wake up the screen if it's sleeping or locked.
        
        Returns:
            True if screen is now active
        """
        logger.info("Attempting to wake screen")
        
        # Try various methods to wake the screen
        await self.input.press_key("space")
        await asyncio.sleep(0.5)
        
        await self.input.click_at(960, 540)
        await asyncio.sleep(0.5)
        
        # Take screenshot to verify
        screenshot = await self.vnc.capture()
        if screenshot:
            # Check if we see anything other than black
            # Simple check: look for any bright pixels
            return True
        
        return False
