"""
Error Recovery Subroutine - Handles unexpected states and errors.

This subroutine is called when the brain encounters an unexpected
state or error that needs to be recovered from.
"""

import asyncio
from typing import TYPE_CHECKING, Optional, Tuple

from src.utils.logger import get_logger

if TYPE_CHECKING:
    from src.subsystems.vnc_capture import VNCCapture
    from src.subsystems.vision_engine import VisionEngine
    from src.subsystems.input_injector import InputInjector

logger = get_logger(__name__)


class ErrorRecoverySubroutine:
    """Handles error recovery and unexpected states."""
    
    def __init__(
        self,
        vnc: "VNCCapture",
        vision: "VisionEngine",
        input_injector: "InputInjector"
    ):
        """
        Initialize error recovery subroutine.
        
        Args:
            vnc: VNC capture instance
            vision: Vision engine instance
            input_injector: Input injector instance
        """
        self.vnc = vnc
        self.vision = vision
        self.input = input_injector
    
    async def analyze_current_state(self) -> Tuple[str, dict]:
        """
        Analyze the current screen state.
        
        Returns:
            Tuple of (state_type, details)
            state_type: "normal", "error", "popup", "login", "unknown"
        """
        screenshot = await self.vnc.capture()
        if not screenshot:
            return "unknown", {"reason": "Cannot capture screen"}
        
        # Check for login screen
        is_login = await self.vision.check_for_login_screen(screenshot)
        if is_login:
            return "login", {"message": "Windows login screen detected"}
        
        # Check for error dialogs
        error_msg = await self.vision.check_for_error_dialog(screenshot)
        if error_msg:
            return "error", {"message": error_msg}
        
        # Check for normal browser state
        state = await self.vision.verify_screen_state(
            screenshot,
            "Chrome browser with OSP panel visible on the right side"
        )
        if state.is_match:
            return "normal", {"description": state.description}
        
        # Check for popups
        state = await self.vision.verify_screen_state(
            screenshot,
            "popup dialog or modal window blocking the main content"
        )
        if state.is_match:
            return "popup", {"description": state.description}
        
        return "unknown", {"description": "Unrecognized screen state"}
    
    async def recover(self) -> bool:
        """
        Attempt to recover from current error state.
        
        Returns:
            True if recovery was successful
        """
        logger.info("Attempting error recovery")
        
        state_type, details = await self.analyze_current_state()
        logger.info(f"Current state: {state_type} - {details}")
        
        if state_type == "normal":
            logger.info("Already in normal state, no recovery needed")
            return True
        
        if state_type == "error":
            return await self._handle_error_dialog(details.get("message", ""))
        
        if state_type == "popup":
            return await self._close_popup()
        
        if state_type == "login":
            logger.warning("Login screen detected - caller should handle this")
            return False
        
        # Unknown state - try generic recovery
        return await self._generic_recovery()
    
    async def _handle_error_dialog(self, error_message: str) -> bool:
        """Handle an error dialog."""
        logger.info(f"Handling error dialog: {error_message}")
        
        screenshot = await self.vnc.capture()
        if not screenshot:
            return False
        
        # Try to find OK or Close button
        ok_button = await self.vision.find_element(
            screenshot,
            "OK button or Close button on the error dialog"
        )
        
        if ok_button:
            await self.input.click_at(ok_button.x, ok_button.y)
            await asyncio.sleep(0.5)
            return True
        
        # Try pressing Enter
        await self.input.enter()
        await asyncio.sleep(0.5)
        
        # Try pressing Escape
        await self.input.escape()
        await asyncio.sleep(0.5)
        
        return True
    
    async def _close_popup(self) -> bool:
        """Close a popup or modal dialog."""
        logger.info("Attempting to close popup")
        
        screenshot = await self.vnc.capture()
        if not screenshot:
            return False
        
        # Look for X button
        close_button = await self.vision.find_element(
            screenshot,
            "close button (X) or Cancel button on popup"
        )
        
        if close_button:
            await self.input.click_at(close_button.x, close_button.y)
            await asyncio.sleep(0.5)
            return True
        
        # Try clicking outside the popup
        # Usually popups are centered, so click in corner
        await self.input.click_at(50, 50)
        await asyncio.sleep(0.3)
        
        # Try Escape
        await self.input.escape()
        await asyncio.sleep(0.3)
        
        return True
    
    async def _generic_recovery(self) -> bool:
        """Generic recovery attempt for unknown states."""
        logger.info("Attempting generic recovery")
        
        # Step 1: Press Escape multiple times
        for _ in range(3):
            await self.input.escape()
            await asyncio.sleep(0.3)
        
        # Step 2: Click in the main content area
        await self.input.click_at(500, 400)
        await asyncio.sleep(0.5)
        
        # Step 3: Try refreshing the page
        await self.input.key_combo("ctrl", "r")
        await asyncio.sleep(3)
        
        # Check if we're back to normal
        state_type, _ = await self.analyze_current_state()
        return state_type in ["normal", "unknown"]
    
    async def refresh_page(self) -> bool:
        """Refresh the current page."""
        logger.info("Refreshing page")
        await self.input.key_combo("ctrl", "r")
        await asyncio.sleep(3)
        return True
    
    async def go_back(self) -> bool:
        """Go back to previous page."""
        logger.info("Going back to previous page")
        await self.input.key_combo("alt", "left")
        await asyncio.sleep(2)
        return True
    
    async def clear_and_retry(self) -> bool:
        """Clear any form fields and prepare for retry."""
        logger.info("Clearing form for retry")
        
        # Press Escape to dismiss any dropdowns
        await self.input.escape()
        await asyncio.sleep(0.3)
        
        # Select all and delete
        await self.input.select_all()
        await asyncio.sleep(0.1)
        await self.input.press_key("delete")
        await asyncio.sleep(0.3)
        
        return True
