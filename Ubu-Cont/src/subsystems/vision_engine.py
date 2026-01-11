"""
Vision Engine Subsystem - Qwen2.5-VL interface for finding UI elements.

This is the "eyes" of the brain. It takes screenshots and answers questions like:
- "Where is the OPEN URL button?"
- "What are the coordinates of the green confirmation box?"
- "Do you see a login screen?"

It does NOT make decisions. It only reports what it sees and where things are.
"""

import asyncio
import json
import base64
import tempfile
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from PIL import Image
import aiohttp
import io

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FoundElement:
    """Represents a UI element found by vision."""
    description: str          # What was found
    x: int                    # X coordinate (center)
    y: int                    # Y coordinate (center)
    confidence: float         # How confident (0-1)
    raw_response: str         # Raw model response for debugging


@dataclass
class ScreenState:
    """Represents the analyzed state of the screen."""
    description: str          # What the screen shows
    is_match: bool            # Does it match expected state
    details: Dict[str, Any]   # Additional details


class VisionEngine:
    """
    Vision engine using Qwen2.5-VL via Ollama.
    
    This is the EYES of the system. It answers questions about what's on screen.
    It does NOT make decisions about what to do next.
    """
    
    def __init__(
        self,
        model: str = "qwen2.5-vl:7b",
        ollama_host: str = "localhost",
        ollama_port: int = 11434,
        timeout: int = 60
    ):
        """
        Initialize vision engine.
        
        Args:
            model: Ollama vision model name
            ollama_host: Ollama server host
            ollama_port: Ollama server port
            timeout: Request timeout in seconds
        """
        self.model = model
        self.base_url = f"http://{ollama_host}:{ollama_port}"
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Temp directory for images
        self.temp_dir = Path(tempfile.gettempdir()) / "vision_engine"
        self.temp_dir.mkdir(exist_ok=True)
    
    async def initialize(self) -> bool:
        """Initialize HTTP session and verify model is available."""
        self.session = aiohttp.ClientSession(timeout=self.timeout)
        
        # Check if model is available
        try:
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    
                    if any(self.model in m for m in models):
                        logger.info(f"Vision engine initialized with model: {self.model}")
                        return True
                    else:
                        logger.warning(f"Model {self.model} not found. Available: {models}")
                        logger.info(f"Pull model with: ollama pull {self.model}")
                        return False
                        
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            logger.info("Vision engine will work when Ollama is running on Ubuntu VM")
        
        return False
    
    async def shutdown(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode()
    
    async def _query_vision(self, image: Image.Image, prompt: str) -> str:
        """
        Send query to vision model.
        
        Args:
            image: Screenshot to analyze
            prompt: Question to ask
            
        Returns:
            Model's response text
        """
        image_b64 = self._image_to_base64(image)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "")
                else:
                    logger.error(f"Vision query failed: {response.status}")
                    return ""
                    
        except Exception as e:
            logger.exception(f"Vision query error: {e}")
            return ""
    
    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Extract and parse JSON from model response."""
        try:
            # Handle case where model adds extra text
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse vision response: {e}")
            logger.debug(f"Raw response: {response}")
        return None
    
    # ==================== ELEMENT FINDING ====================
    
    async def find_element(
        self,
        screenshot: Image.Image,
        element_description: str
    ) -> Optional[FoundElement]:
        """
        Find a UI element on the screen.
        
        Args:
            screenshot: Current screen capture
            element_description: What to find, e.g., "OPEN URL button on the right side"
            
        Returns:
            FoundElement with coordinates, or None if not found
        """
        prompt = f"""Look at this screenshot carefully.

I need you to find: {element_description}

If you find it, respond with ONLY this JSON format (no other text):
{{"found": true, "x": <center_x_coordinate>, "y": <center_y_coordinate>, "confidence": <0.0-1.0>}}

The x,y coordinates should be the CENTER of the element, suitable for clicking.
Coordinates should be in pixels from the top-left corner.
Image resolution is {screenshot.size[0]}x{screenshot.size[1]} pixels.

If you cannot find it, respond with ONLY:
{{"found": false, "reason": "<brief explanation>"}}

IMPORTANT: Respond with ONLY the JSON, no additional text or explanation."""

        logger.debug(f"Vision query: Find '{element_description}'")
        
        response = await self._query_vision(screenshot, prompt)
        logger.debug(f"Vision response: {response[:200]}...")
        
        result = self._parse_json_response(response)
        
        if result and result.get("found"):
            element = FoundElement(
                description=element_description,
                x=int(result["x"]),
                y=int(result["y"]),
                confidence=float(result.get("confidence", 0.8)),
                raw_response=response
            )
            logger.info(f"Found element at ({element.x}, {element.y})")
            return element
        else:
            reason = result.get("reason", "unknown") if result else "parse error"
            logger.warning(f"Element not found: {reason}")
        
        return None
    
    async def find_button_by_text(
        self,
        screenshot: Image.Image,
        button_text: str,
        location_hint: str = ""
    ) -> Optional[FoundElement]:
        """
        Find a button with specific text.
        
        Args:
            screenshot: Current screen capture
            button_text: Text on the button
            location_hint: Where to look, e.g., "on the right side", "at the bottom"
            
        Returns:
            FoundElement with coordinates
        """
        description = f"button that says '{button_text}'"
        if location_hint:
            description += f" {location_hint}"
        
        return await self.find_element(screenshot, description)
    
    async def find_input_field(
        self,
        screenshot: Image.Image,
        field_description: str
    ) -> Optional[FoundElement]:
        """
        Find an input field or text area.
        
        Args:
            screenshot: Current screen capture
            field_description: Description of the field
            
        Returns:
            FoundElement with coordinates
        """
        return await self.find_element(
            screenshot,
            f"text input field or text area for {field_description}"
        )
    
    # ==================== STATE VERIFICATION ====================
    
    async def verify_screen_state(
        self,
        screenshot: Image.Image,
        expected_state: str
    ) -> ScreenState:
        """
        Verify the screen shows an expected state.
        
        Args:
            screenshot: Current screen capture
            expected_state: Description of expected state
            
        Returns:
            ScreenState with match result
        """
        prompt = f"""Look at this screenshot carefully.

Does this screen show: "{expected_state}"?

Respond with ONLY this JSON format (no other text):
{{"matches": true/false, "description": "<what you actually see>", "confidence": <0.0-1.0>}}

Be specific about what you see. Respond with ONLY the JSON."""

        logger.debug(f"Verifying state: '{expected_state}'")
        
        response = await self._query_vision(screenshot, prompt)
        result = self._parse_json_response(response)
        
        if result:
            return ScreenState(
                description=result.get("description", ""),
                is_match=result.get("matches", False),
                details={"confidence": result.get("confidence", 0.5)}
            )
        
        return ScreenState(
            description="Failed to parse response",
            is_match=False,
            details={"raw_response": response}
        )
    
    async def check_for_login_screen(self, screenshot: Image.Image) -> bool:
        """
        Check if Windows 10 is showing a login screen.
        
        Returns:
            True if login screen is visible
        """
        state = await self.verify_screen_state(
            screenshot,
            "Windows 10 login screen or lock screen with password field"
        )
        return state.is_match
    
    async def check_for_error_dialog(self, screenshot: Image.Image) -> Optional[str]:
        """
        Check if there's an error dialog on screen.
        
        Returns:
            Error message if found, None otherwise
        """
        prompt = """Look at this screenshot.

Is there any error dialog, error message, or warning popup visible?

Respond with ONLY this JSON format:
{"has_error": true/false, "error_message": "<the error text if visible>"}

Respond with ONLY the JSON."""

        response = await self._query_vision(screenshot, prompt)
        result = self._parse_json_response(response)
        
        if result and result.get("has_error"):
            return result.get("error_message", "Unknown error")
        
        return None
    
    async def check_for_confirmation(
        self,
        screenshot: Image.Image,
        confirmation_type: str = "success"
    ) -> bool:
        """
        Check for a confirmation message.
        
        Args:
            screenshot: Current screen capture
            confirmation_type: "success" or "failure"
            
        Returns:
            True if confirmation is visible
        """
        if confirmation_type == "success":
            state = await self.verify_screen_state(
                screenshot,
                "green success message, confirmation box, or 'post successful' notification"
            )
        else:
            state = await self.verify_screen_state(
                screenshot,
                "red error message, failure notification, or 'post failed' message"
            )
        
        return state.is_match
    
    # ==================== OSP-SPECIFIC QUERIES ====================
    
    async def find_osp_button(
        self,
        screenshot: Image.Image,
        button_name: str
    ) -> Optional[FoundElement]:
        """
        Find a button on the OSP panel (right side of screen).
        
        Args:
            screenshot: Current screen capture
            button_name: Button text (e.g., "OPEN URL", "COPY TITLE")
            
        Returns:
            FoundElement with coordinates
        """
        return await self.find_element(
            screenshot,
            f"button labeled '{button_name}' on the right side panel (OSP)"
        )
    
    async def check_osp_email_toggle(self, screenshot: Image.Image) -> bool:
        """
        Check if the OSP indicates email should be sent.
        
        Returns:
            True if email toggle is indicated/checked
        """
        prompt = """Look at the right side of this screenshot where the OSP panel is.

Is there an indication that an email should be sent? Look for:
- A checked checkbox for email
- Text indicating "send email" is enabled
- An active email toggle

Respond with ONLY: {"send_email": true/false}"""

        response = await self._query_vision(screenshot, prompt)
        result = self._parse_json_response(response)
        
        if result:
            return result.get("send_email", False)
        
        return False
    
    # ==================== PLATFORM-SPECIFIC QUERIES ====================
    
    async def find_skool_new_post_button(
        self,
        screenshot: Image.Image
    ) -> Optional[FoundElement]:
        """Find the 'Start a post' or 'New post' button on Skool."""
        return await self.find_element(
            screenshot,
            "button or area to start a new post on Skool, might say 'Start a post' or have a plus icon or 'Create' button"
        )
    
    async def find_platform_post_button(
        self,
        screenshot: Image.Image,
        platform: str
    ) -> Optional[FoundElement]:
        """Find the final 'Post' or 'Share' button on a platform."""
        platform_hints = {
            "skool": "Post button or Submit button on Skool",
            "instagram": "Share button on Instagram post creation",
            "facebook": "Post button on Facebook",
            "tiktok": "Post button on TikTok"
        }
        
        hint = platform_hints.get(platform.lower(), "Post or Share button")
        return await self.find_element(screenshot, hint)
    
    async def find_paste_target(
        self,
        screenshot: Image.Image,
        target_type: str,
        visual_hint: str = ""
    ) -> Optional[FoundElement]:
        """
        Find where to paste content.
        
        Args:
            screenshot: Current screen capture
            target_type: "title", "body", or "image"
            visual_hint: Visual hint like "green box" or "red area"
            
        Returns:
            FoundElement with coordinates
        """
        descriptions = {
            "title": "area to paste the title, possibly a green highlighted box or input field labeled for title",
            "body": "area to paste body content or description, possibly a red highlighted box or larger text area",
            "image": "area to paste or upload an image, possibly highlighted or showing an upload zone"
        }
        
        description = descriptions.get(target_type, f"area to paste {target_type}")
        if visual_hint:
            description = f"{visual_hint} where I should {description}"
        
        return await self.find_element(screenshot, description)
