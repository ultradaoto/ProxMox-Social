"""
OpenRouter API Client

Provides access to Qwen Coder and Qwen Vision models via OpenRouter.
Used for decision making and screen understanding.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
import base64
import json
import logging
import os
import time

logger = logging.getLogger(__name__)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    logger.warning("httpx not available, install with: pip install httpx")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


@dataclass
class OpenRouterConfig:
    """OpenRouter configuration."""
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1"
    coder_model: str = "qwen/qwen-2.5-coder-32b-instruct"
    vision_model: str = "qwen/qwen-2-vl-72b-instruct"
    fallback_vision_model: str = "anthropic/claude-3-haiku"
    timeout: int = 120
    max_retries: int = 3
    retry_delay: float = 1.0

    @classmethod
    def from_env(cls) -> 'OpenRouterConfig':
        """Create config from environment variables."""
        api_key = os.environ.get('OPENROUTER_API_KEY', '')
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        return cls(
            api_key=api_key,
            coder_model=os.environ.get('OPENROUTER_CODER_MODEL', cls.coder_model),
            vision_model=os.environ.get('OPENROUTER_VISION_MODEL', cls.vision_model)
        )


@dataclass
class ChatMessage:
    """Chat message for API."""
    role: str  # 'system', 'user', 'assistant'
    content: Union[str, List[Dict[str, Any]]]  # Text or multimodal content

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format."""
        return {'role': self.role, 'content': self.content}


class OpenRouterClient:
    """
    Client for OpenRouter API.

    Provides access to:
        - Qwen 2.5 Coder: For decision making and code generation
        - Qwen 2 VL: For vision/screen understanding

    Features:
        - Synchronous and async support
        - Image encoding and multimodal messages
        - Retry logic with exponential backoff
        - Usage tracking
    """

    def __init__(self, config: Optional[OpenRouterConfig] = None):
        """
        Initialize OpenRouter client.

        Args:
            config: OpenRouter configuration, or loads from environment
        """
        if not HAS_HTTPX:
            raise ImportError("httpx required: pip install httpx")

        self.config = config or OpenRouterConfig.from_env()
        self._client: Optional[httpx.Client] = None
        self._async_client = None

        # Usage tracking
        self.total_tokens = 0
        self.total_requests = 0
        self.total_cost = 0.0

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "HTTP-Referer": "https://github.com/proxmox-computer-control",
                    "X-Title": "AI Computer Control System"
                },
                timeout=self.config.timeout
            )
        return self._client

    def chat(
        self,
        messages: List[Union[Dict[str, Any], ChatMessage]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False
    ) -> str:
        """
        Send chat completion request.

        Args:
            messages: List of message dicts or ChatMessage objects
            model: Model to use (defaults to coder model)
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            stream: Whether to stream response

        Returns:
            Assistant response text
        """
        model = model or self.config.coder_model

        # Convert messages to API format
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, ChatMessage):
                formatted_messages.append(msg.to_dict())
            else:
                formatted_messages.append(msg)

        payload = {
            "model": model,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        response = self._make_request("/chat/completions", payload)

        # Track usage
        usage = response.get('usage', {})
        self.total_tokens += usage.get('total_tokens', 0)
        self.total_requests += 1

        return response["choices"][0]["message"]["content"]

    def analyze_screen(
        self,
        image_path: str,
        query: str,
        context: Optional[str] = None,
        detail: str = "high"
    ) -> str:
        """
        Analyze screenshot using vision model.

        Args:
            image_path: Path to screenshot
            query: What to look for / analyze
            context: Optional context about current task
            detail: Image detail level ('low', 'high', 'auto')

        Returns:
            Analysis result
        """
        # Read and encode image
        image_data = self._encode_image(image_path)
        mime_type = self._get_mime_type(image_path)

        # Build messages
        messages = [
            {
                "role": "system",
                "content": """You are an expert at analyzing computer screenshots.
You identify UI elements, buttons, text fields, links, and describe what's on screen.
When asked to find elements, provide their approximate pixel coordinates.
Be precise and concise. Focus on actionable information."""
            }
        ]

        if context:
            messages.append({
                "role": "user",
                "content": f"Context: {context}"
            })

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{image_data}",
                        "detail": detail
                    }
                },
                {
                    "type": "text",
                    "text": query
                }
            ]
        })

        return self.chat(messages, model=self.config.vision_model)

    def find_element(
        self,
        image_path: str,
        element_description: str,
        screen_width: int = 1920,
        screen_height: int = 1080
    ) -> Optional[Dict[str, Any]]:
        """
        Find a specific element on screen.

        Args:
            image_path: Screenshot path
            element_description: What to find (e.g., "login button", "search box")
            screen_width: Screen width for coordinate reference
            screen_height: Screen height for coordinate reference

        Returns:
            Dict with element info and coordinates, or None if not found
        """
        query = f"""Find the "{element_description}" on this screen.

Screen dimensions: {screen_width}x{screen_height} pixels

If found, respond with ONLY this JSON format:
{{"found": true, "x": <center_x>, "y": <center_y>, "width": <width>, "height": <height>, "confidence": <0.0-1.0>, "description": "<brief description>"}}

If not found:
{{"found": false, "reason": "<explanation>"}}

IMPORTANT: Respond with ONLY valid JSON, no other text."""

        response = self.analyze_screen(image_path, query)

        try:
            # Find JSON in response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(response[start:end])
                return result
        except json.JSONDecodeError as e:
            logger.warning(f"Could not parse element location: {e}")

        return None

    def decide_next_action(
        self,
        screen_analysis: str,
        task_description: str,
        action_history: List[Dict[str, Any]],
        available_actions: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Decide what action to take next.

        Args:
            screen_analysis: Description of current screen state
            task_description: What we're trying to accomplish
            action_history: Previous actions taken
            available_actions: What actions are possible

        Returns:
            Dict with action type and parameters
        """
        if available_actions is None:
            available_actions = [
                "click(x, y): Click at coordinates",
                "double_click(x, y): Double-click at coordinates",
                "right_click(x, y): Right-click at coordinates",
                "type(text): Type text",
                "scroll(direction, amount): Scroll up/down",
                "wait(seconds): Wait for page to load",
                "hotkey(keys): Press keyboard shortcut",
                "done(): Task is complete"
            ]

        prompt = f"""You are controlling a computer to complete a task.

TASK: {task_description}

CURRENT SCREEN STATE:
{screen_analysis}

PREVIOUS ACTIONS (last 5):
{json.dumps(action_history[-5:], indent=2) if action_history else "None"}

AVAILABLE ACTIONS:
{chr(10).join(f'- {a}' for a in available_actions)}

Decide the next best action to progress toward completing the task.
Consider:
1. What is currently visible on screen
2. What actions have already been taken
3. What is the most logical next step

Respond with ONLY a JSON object in this format:
{{"action": "action_name", "params": {{"param1": value1, ...}}, "reasoning": "brief explanation"}}"""

        response = self.chat([
            {"role": "system", "content": "You are a precise computer control agent. Respond only with valid JSON."},
            {"role": "user", "content": prompt}
        ], temperature=0.3)  # Lower temperature for more deterministic actions

        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except json.JSONDecodeError:
            logger.warning(f"Could not parse action decision: {response}")

        return {"action": "wait", "params": {"seconds": 1}, "reasoning": "Parse error, waiting"}

    def describe_screen(
        self,
        image_path: str,
        focus_area: Optional[str] = None
    ) -> str:
        """
        Get a natural language description of what's on screen.

        Args:
            image_path: Screenshot path
            focus_area: Optional area to focus on (e.g., "center", "top menu")

        Returns:
            Description of screen contents
        """
        query = "Describe what's visible on this screen. "
        if focus_area:
            query += f"Focus particularly on the {focus_area}. "
        query += "Include any important UI elements, text, and the overall context."

        return self.analyze_screen(image_path, query)

    def extract_text(
        self,
        image_path: str,
        region: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Extract text from screen or region.

        Args:
            image_path: Screenshot path
            region: Optional region {x, y, width, height}

        Returns:
            Extracted text
        """
        if region:
            query = f"""Extract all visible text from this region of the screen:
            Position: ({region['x']}, {region['y']})
            Size: {region['width']}x{region['height']}

            Return only the text content, preserving line breaks."""
        else:
            query = "Extract all visible text from this screen. Return only the text content, preserving the layout as much as possible."

        return self.analyze_screen(image_path, query)

    def _make_request(
        self,
        endpoint: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make API request with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                response = self.client.post(endpoint, json=payload)
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Rate limited
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                elif e.response.status_code >= 500:  # Server error
                    wait_time = self.config.retry_delay * (2 ** attempt)
                    logger.warning(f"Server error, retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

            except httpx.RequestError as e:
                last_error = e
                wait_time = self.config.retry_delay * (2 ** attempt)
                logger.warning(f"Request error: {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)

        raise last_error

    def _encode_image(self, path: str) -> str:
        """Encode image file to base64."""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def _get_mime_type(self, path: str) -> str:
        """Get MIME type from file extension."""
        ext = Path(path).suffix.lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        return mime_types.get(ext, 'image/png')

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics."""
        return {
            'total_tokens': self.total_tokens,
            'total_requests': self.total_requests,
            'estimated_cost': self.total_cost
        }

    def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
