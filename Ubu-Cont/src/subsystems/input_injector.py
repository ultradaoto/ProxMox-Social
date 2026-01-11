"""
Input Injector Subsystem - Send mouse/keyboard commands to Windows 10.

This module sends input commands to the Windows 10 VM via the Proxmox host.
The Proxmox host translates these commands to QMP for the VM.
"""

import asyncio
import aiohttp
from typing import Optional, List
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class MouseButton(Enum):
    """Mouse button types."""
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class InputInjector:
    """
    Injects mouse and keyboard input into Windows 10 VM.
    
    Commands are sent to Proxmox host which translates them to QMP
    commands for the virtual HID device.
    """
    
    def __init__(
        self,
        proxmox_host: str = "192.168.100.1",
        api_port: int = 8888,
        timeout: int = 10
    ):
        """
        Initialize input injector.
        
        Args:
            proxmox_host: Proxmox host IP
            api_port: Port for input API
            timeout: Request timeout in seconds
        """
        self.base_url = f"http://{proxmox_host}:{api_port}"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Default delays for human-like behavior
        self.move_duration_ms = 300      # Mouse movement duration
        self.click_delay_ms = 50         # Delay before click
        self.type_delay_ms = 30          # Delay between keystrokes
        self.action_delay_ms = 200       # Delay after actions
    
    async def initialize(self) -> bool:
        """Initialize HTTP session and verify connection."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Test connection
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    logger.info(f"Input injector connected to {self.base_url}")
                    return True
        except Exception as e:
            logger.warning(f"Input API not responding: {e}")
            logger.info("Input injector will work when running on Ubuntu VM")
        
        return False
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _post(self, endpoint: str, data: dict) -> bool:
        """Send POST request to input API."""
        try:
            async with self.session.post(
                f"{self.base_url}{endpoint}",
                json=data
            ) as response:
                success = response.status == 200
                if not success:
                    logger.warning(f"Input API returned {response.status} for {endpoint}")
                return success
        except Exception as e:
            logger.error(f"Input API error: {e}")
            return False
    
    # ==================== MOUSE OPERATIONS ====================
    
    async def move_mouse(
        self,
        x: int,
        y: int,
        duration_ms: Optional[int] = None
    ) -> bool:
        """
        Move mouse to absolute position.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate
            duration_ms: Movement duration (for human-like motion)
            
        Returns:
            True if successful
        """
        logger.debug(f"Moving mouse to ({x}, {y})")
        
        return await self._post("/mouse/move", {
            "x": x,
            "y": y,
            "duration": duration_ms or self.move_duration_ms
        })
    
    async def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT
    ) -> bool:
        """
        Click at position (or current position if x,y not specified).
        
        Args:
            x: Optional X coordinate
            y: Optional Y coordinate
            button: Mouse button to click
            
        Returns:
            True if successful
        """
        data = {"button": button.value}
        
        if x is not None and y is not None:
            data["x"] = x
            data["y"] = y
            logger.debug(f"Clicking at ({x}, {y}) with {button.value} button")
        else:
            logger.debug(f"Clicking at current position with {button.value} button")
        
        return await self._post("/mouse/click", data)
    
    async def click_at(self, x: int, y: int) -> bool:
        """
        Move to position and click.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        # Move first
        if not await self.move_mouse(x, y):
            return False
        
        # Small delay before click
        await asyncio.sleep(self.click_delay_ms / 1000)
        
        # Click
        return await self.click()
    
    async def double_click(self, x: int, y: int) -> bool:
        """
        Double-click at position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        logger.debug(f"Double-clicking at ({x}, {y})")
        
        return await self._post("/mouse/double_click", {
            "x": x,
            "y": y
        })
    
    async def right_click(self, x: int, y: int) -> bool:
        """Right-click at position."""
        if not await self.move_mouse(x, y):
            return False
        await asyncio.sleep(self.click_delay_ms / 1000)
        return await self.click(button=MouseButton.RIGHT)
    
    async def scroll(
        self,
        direction: str = "down",
        amount: int = 3
    ) -> bool:
        """
        Scroll the page.
        
        Args:
            direction: "up" or "down"
            amount: Number of scroll units
            
        Returns:
            True if successful
        """
        logger.debug(f"Scrolling {direction} by {amount}")
        
        return await self._post("/mouse/scroll", {
            "direction": direction,
            "amount": amount
        })
    
    # ==================== KEYBOARD OPERATIONS ====================
    
    async def type_text(
        self,
        text: str,
        delay_ms: Optional[int] = None
    ) -> bool:
        """
        Type a string of text.
        
        Args:
            text: Text to type
            delay_ms: Delay between keystrokes
            
        Returns:
            True if successful
        """
        logger.debug(f"Typing text: {text[:50]}{'...' if len(text) > 50 else ''}")
        
        return await self._post("/keyboard/type", {
            "text": text,
            "delay": delay_ms or self.type_delay_ms
        })
    
    async def press_key(
        self,
        key: str,
        modifiers: Optional[List[str]] = None
    ) -> bool:
        """
        Press a single key with optional modifiers.
        
        Args:
            key: Key name (e.g., "enter", "tab", "a", "1")
            modifiers: List of modifiers ["ctrl", "shift", "alt"]
            
        Returns:
            True if successful
        """
        mod_str = "+".join(modifiers) + "+" if modifiers else ""
        logger.debug(f"Pressing key: {mod_str}{key}")
        
        return await self._post("/keyboard/press", {
            "key": key,
            "modifiers": modifiers or []
        })
    
    async def key_combo(self, *keys: str) -> bool:
        """
        Press a key combination.
        
        Args:
            *keys: Keys to press together (e.g., "ctrl", "v")
            
        Returns:
            True if successful
        """
        if len(keys) == 1:
            return await self.press_key(keys[0])
        
        modifiers = list(keys[:-1])
        key = keys[-1]
        return await self.press_key(key, modifiers)
    
    # ==================== COMMON OPERATIONS ====================
    
    async def paste(self) -> bool:
        """Send Ctrl+V to paste from clipboard."""
        logger.debug("Pasting (Ctrl+V)")
        return await self.key_combo("ctrl", "v")
    
    async def copy(self) -> bool:
        """Send Ctrl+C to copy to clipboard."""
        logger.debug("Copying (Ctrl+C)")
        return await self.key_combo("ctrl", "c")
    
    async def select_all(self) -> bool:
        """Send Ctrl+A to select all."""
        logger.debug("Select all (Ctrl+A)")
        return await self.key_combo("ctrl", "a")
    
    async def enter(self) -> bool:
        """Press Enter key."""
        return await self.press_key("enter")
    
    async def tab(self) -> bool:
        """Press Tab key."""
        return await self.press_key("tab")
    
    async def escape(self) -> bool:
        """Press Escape key."""
        return await self.press_key("escape")
    
    async def backspace(self) -> bool:
        """Press Backspace key."""
        return await self.press_key("backspace")
    
    # ==================== COMPOUND OPERATIONS ====================
    
    async def click_and_type(self, x: int, y: int, text: str) -> bool:
        """
        Click at position and type text.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to type
            
        Returns:
            True if successful
        """
        if not await self.click_at(x, y):
            return False
        
        await asyncio.sleep(self.action_delay_ms / 1000)
        
        return await self.type_text(text)
    
    async def click_and_paste(self, x: int, y: int) -> bool:
        """
        Click at position and paste from clipboard.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        if not await self.click_at(x, y):
            return False
        
        await asyncio.sleep(self.action_delay_ms / 1000)
        
        return await self.paste()
    
    async def triple_click_select_all(self, x: int, y: int) -> bool:
        """
        Triple-click to select all text in a field.
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if successful
        """
        # Move to position
        if not await self.move_mouse(x, y):
            return False
        
        # Triple click (select all in text field)
        for _ in range(3):
            if not await self.click():
                return False
            await asyncio.sleep(0.05)
        
        return True
    
    async def clear_field_and_type(self, x: int, y: int, text: str) -> bool:
        """
        Click field, select all, and type new text.
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to type
            
        Returns:
            True if successful
        """
        if not await self.click_at(x, y):
            return False
        
        await asyncio.sleep(0.1)
        
        if not await self.select_all():
            return False
        
        await asyncio.sleep(0.1)
        
        return await self.type_text(text)
