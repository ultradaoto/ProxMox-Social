"""
Uses vision AI to locate UI elements that have moved.
"""
import base64
import json
import re
import httpx
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from .config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    VISION_MODEL,
    CONFIDENCE_THRESHOLD,
    SCREEN_WIDTH,
    SCREEN_HEIGHT,
)

logger = logging.getLogger(__name__)


@dataclass
class LocatorResult:
    """Result from vision AI locator."""
    success: bool
    new_x: Optional[int] = None
    new_y: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: str = ""


class VisionLocator:
    """Uses vision AI to find UI elements on screen."""
    
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or VISION_MODEL
        self.client = httpx.Client(timeout=60.0)
    
    def _encode_image(self, image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode('utf-8')
    
    def locate_element(
        self,
        full_screenshot: bytes,
        action_description: str,
        old_x: int,
        old_y: int,
        baseline_image: bytes = None,
        failed_image: bytes = None
    ) -> LocatorResult:
        """
        Use vision AI to locate a UI element that has moved.
        
        Args:
            full_screenshot: Full desktop screenshot (PNG bytes)
            action_description: What the element does
            old_x: Previous X coordinate
            old_y: Previous Y coordinate
            baseline_image: 100x100 baseline showing what we expected
            failed_image: 100x100 showing what we actually saw
        """
        prompt = f"""You are analyzing a screenshot to help fix an automation workflow.

TASK: Find the CURRENT location of a UI element that has moved.

WHAT WE'RE LOOKING FOR:
{action_description}

PREVIOUS LOCATION (no longer correct):
X: {old_x}, Y: {old_y}

The button/element has MOVED. Find its new location.

RESPONSE FORMAT (respond with ONLY this JSON):
{{
    "found": true/false,
    "new_x": <integer x coordinate>,
    "new_y": <integer y coordinate>,
    "confidence": <float 0.0-1.0>,
    "element_description": "<what you found>",
    "reasoning": "<why you believe this is correct>"
}}

IMPORTANT:
- Coordinates are pixels from top-left
- Screen is {SCREEN_WIDTH}x{SCREEN_HEIGHT}
- Return CENTER of clickable element
- If not found, set "found": false"""

        images = [{
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{self._encode_image(full_screenshot)}"}
        }]
        
        # Add context images if available
        if baseline_image and failed_image:
            prompt += """

CONTEXT IMAGES:
I'm also showing you two 100x100 images:
1. BASELINE: What it USED to look like (worked before)
2. CURRENT: What it looks like NOW (broken)"""
            
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{self._encode_image(baseline_image)}"}
            })
            images.append({
                "type": "image_url", 
                "image_url": {"url": f"data:image/png;base64,{self._encode_image(failed_image)}"}
            })
        
        try:
            response = self.client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://social.sterlingcooley.com",
                    "X-Title": "Workflow Self-Healing Agent"
                },
                json={
                    "model": self.model,
                    "messages": [{
                        "role": "user",
                        "content": [{"type": "text", "text": prompt}, *images]
                    }],
                    "max_tokens": 1000,
                    "temperature": 0.1
                }
            )
            response.raise_for_status()
            
            raw_text = response.json()['choices'][0]['message']['content']
            logger.debug(f"Vision AI response: {raw_text}")
            
            return self._parse_response(raw_text)
            
        except Exception as e:
            logger.error(f"Vision locator error: {e}")
            return LocatorResult(success=False, reasoning=str(e), raw_response=str(e))
    
    def _parse_response(self, raw_text: str) -> LocatorResult:
        try:
            json_match = re.search(r'\{[\s\S]*\}', raw_text)
            if not json_match:
                return LocatorResult(success=False, reasoning="No JSON in response", raw_response=raw_text)
            
            data = json.loads(json_match.group())
            
            if not data.get('found', False):
                return LocatorResult(success=False, reasoning=data.get('reasoning', 'Not found'), raw_response=raw_text)
            
            new_x = int(data.get('new_x', 0))
            new_y = int(data.get('new_y', 0))
            confidence = float(data.get('confidence', 0.0))
            reasoning = data.get('reasoning', '')
            
            # Validate bounds
            if not (0 <= new_x <= SCREEN_WIDTH and 0 <= new_y <= SCREEN_HEIGHT):
                return LocatorResult(success=False, reasoning=f"Out of bounds: ({new_x}, {new_y})", raw_response=raw_text)
            
            # Check confidence
            if confidence < CONFIDENCE_THRESHOLD:
                return LocatorResult(
                    success=False, new_x=new_x, new_y=new_y, confidence=confidence,
                    reasoning=f"Confidence {confidence:.2f} below {CONFIDENCE_THRESHOLD}", raw_response=raw_text
                )
            
            return LocatorResult(
                success=True, new_x=new_x, new_y=new_y, confidence=confidence,
                reasoning=reasoning, raw_response=raw_text
            )
            
        except Exception as e:
            return LocatorResult(success=False, reasoning=f"Parse error: {e}", raw_response=raw_text)
    
    def close(self):
        self.client.close()
