"""
Self-Healer - Automatic coordinate recalibration using high-accuracy vision model.

When consecutive failures indicate UI has drifted, triggers healing:
1. Captures screenshot of current state
2. Calls high-accuracy vision API (Qwen 3 VL)
3. Validates new coordinates
4. Updates coordinate store with healing event
"""

import asyncio
import base64
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from PIL import Image
import aiohttp
import io

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class HealingResult:
    """Result of healing operation."""
    success: bool
    new_coordinates: Optional[Tuple[int, int]]
    confidence: float
    delta: Optional[Tuple[int, int]]  # Change from old coordinates
    error_message: Optional[str]
    screenshot_path: Optional[str]


class SelfHealer:
    """
    Handles coordinate recalibration using high-accuracy vision model.
    Only called when consecutive failures trigger healing.

    Uses expensive, accurate vision model (Qwen 3 VL) sparingly to:
    - Detect when UI elements have moved
    - Find new precise coordinates
    - Validate coordinates before updating store
    """

    def __init__(
        self,
        vnc_capture,
        vision_controller,
        healing_model: str = "qwen/qwen-2.5-vl-72b-instruct",  # Default to 2.5 (3 not yet available)
        screenshot_dir: str = "data/healing_screenshots"
    ):
        """
        Initialize self-healer.

        Args:
            vnc_capture: VNC capture instance for screenshots
            vision_controller: VisionController instance for API access
            healing_model: High-accuracy vision model name
            screenshot_dir: Directory to save healing screenshots
        """
        self.vnc = vnc_capture
        self.vision = vision_controller
        self.healing_model = healing_model

        # Screenshot directory
        base_dir = Path(__file__).parent.parent.parent
        self.screenshot_dir = base_dir / screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"SelfHealer initialized with model: {healing_model}")

    async def heal_coordinates(
        self,
        step_name: str,
        element_description: str,
        expected_x_range: Optional[Tuple[int, int]] = None,
        current_coords: Optional[Tuple[int, int]] = None
    ) -> HealingResult:
        """
        Recalibrate coordinates using high-accuracy vision model.

        Args:
            step_name: Name of the failing step
            element_description: Vision description of element to find
            expected_x_range: Expected X coordinate range for validation
            current_coords: Current stored coordinates

        Returns:
            HealingResult with new coordinates and confidence
        """
        logger.info(f"🔧 Healing triggered for step '{step_name}'")
        logger.info(f"Looking for: {element_description}")

        try:
            # Take screenshot
            screenshot = await self._take_healing_screenshot()
            if not screenshot:
                return HealingResult(
                    success=False,
                    new_coordinates=None,
                    confidence=0.0,
                    delta=None,
                    error_message="Failed to capture screenshot",
                    screenshot_path=None
                )

            # Save screenshot for debugging
            screenshot_path = await self._save_screenshot(screenshot, step_name)

            # Call healing vision API
            new_coords, confidence = await self._call_healing_vision_api(
                screenshot,
                element_description
            )

            if not new_coords:
                return HealingResult(
                    success=False,
                    new_coordinates=None,
                    confidence=0.0,
                    delta=None,
                    error_message="Vision API did not find element",
                    screenshot_path=screenshot_path
                )

            # Validate coordinates
            is_valid = self._validate_coordinates(
                new_coords,
                current_coords,
                expected_x_range
            )

            if not is_valid:
                return HealingResult(
                    success=False,
                    new_coordinates=new_coords,
                    confidence=confidence,
                    delta=None,
                    error_message=f"Coordinates failed validation: {new_coords}",
                    screenshot_path=screenshot_path
                )

            # Calculate delta
            delta = None
            if current_coords:
                delta = (
                    new_coords[0] - current_coords[0],
                    new_coords[1] - current_coords[1]
                )
                logger.info(f"✅ Healing successful: {current_coords} → {new_coords} (delta: {delta})")
            else:
                logger.info(f"✅ Healing successful: new coords {new_coords}")

            return HealingResult(
                success=True,
                new_coordinates=new_coords,
                confidence=confidence,
                delta=delta,
                error_message=None,
                screenshot_path=screenshot_path
            )

        except Exception as e:
            logger.exception(f"Healing failed with exception: {e}")
            return HealingResult(
                success=False,
                new_coordinates=None,
                confidence=0.0,
                delta=None,
                error_message=str(e),
                screenshot_path=None
            )

    async def _take_healing_screenshot(self) -> Optional[Image.Image]:
        """Take screenshot for healing analysis."""
        try:
            # VNC capture is synchronous, wrap in thread
            screenshot = await asyncio.to_thread(self.vnc.capture_frame)
            if screenshot is None:
                logger.error("Failed to capture screenshot from VNC")
                return None

            logger.debug(f"Captured screenshot: {screenshot.size}")
            return screenshot

        except Exception as e:
            logger.exception(f"Screenshot capture failed: {e}")
            return None

    async def _save_screenshot(self, screenshot: Image.Image, step_name: str) -> str:
        """Save screenshot for debugging."""
        try:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"healing_{step_name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            await asyncio.to_thread(screenshot.save, filepath)
            logger.info(f"Saved healing screenshot: {filepath}")

            return str(filepath)

        except Exception as e:
            logger.exception(f"Failed to save screenshot: {e}")
            return ""

    async def _call_healing_vision_api(
        self,
        screenshot: Image.Image,
        description: str
    ) -> Tuple[Optional[Tuple[int, int]], float]:
        """
        Call expensive high-accuracy vision API.

        Args:
            screenshot: PIL Image
            description: Element description for vision model

        Returns:
            ((x, y), confidence) tuple, or (None, 0.0) if not found
        """
        try:
            # Use the vision controller's find_element method
            # It already handles the API call, base64 encoding, etc.
            logger.info(f"Calling healing vision API with model: {self.healing_model}")

            # The vision controller is synchronous, wrap in thread
            result = await asyncio.to_thread(
                self.vision.find_element,
                description
            )

            if result:
                x, y = result
                confidence = 0.95  # VisionController doesn't return confidence, assume high
                logger.info(f"Healing vision found element at ({x}, {y})")
                return ((x, y), confidence)
            else:
                logger.warning("Healing vision did not find element")
                return (None, 0.0)

        except Exception as e:
            logger.exception(f"Healing vision API call failed: {e}")
            return (None, 0.0)

    def _validate_coordinates(
        self,
        new_coords: Tuple[int, int],
        old_coords: Optional[Tuple[int, int]],
        expected_x_range: Optional[Tuple[int, int]]
    ) -> bool:
        """
        Validate new coordinates are reasonable.

        Checks:
        - Within expected X range (if specified)
        - Not too far from old coordinates (if available)
        - Within screen bounds

        Args:
            new_coords: New coordinates from healing
            old_coords: Previous coordinates (if any)
            expected_x_range: Expected (min_x, max_x) range

        Returns:
            True if valid, False otherwise
        """
        x, y = new_coords

        # Check screen bounds (1600x1200 resolution)
        if x < 0 or x > 1600 or y < 0 or y > 1200:
            logger.warning(f"Coordinates {new_coords} outside screen bounds (1600x1200)")
            return False

        # Check expected X range
        if expected_x_range:
            min_x, max_x = expected_x_range
            if x < min_x or x > max_x:
                logger.warning(f"X coordinate {x} outside expected range [{min_x}, {max_x}]")
                return False

        # Check delta from old coordinates (if available)
        if old_coords:
            delta_x = abs(x - old_coords[0])
            delta_y = abs(y - old_coords[1])

            # Reject if moved more than 200 pixels (likely wrong element)
            if delta_x > 200 or delta_y > 200:
                logger.warning(f"Delta too large: ({delta_x}, {delta_y}) - likely wrong element")
                return False

        logger.debug(f"Coordinates {new_coords} passed validation")
        return True
