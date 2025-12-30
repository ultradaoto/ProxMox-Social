"""
Qwen-VL Integration

Vision-Language model integration for complex screen understanding.
Uses Ollama for local inference.
"""

import base64
import logging
import json
from typing import Optional, Dict, Any, List
from pathlib import Path
from io import BytesIO

import numpy as np

logger = logging.getLogger(__name__)

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


class QwenVL:
    """
    Qwen-VL vision-language model interface via Ollama.

    Provides natural language understanding of screen contents.
    """

    def __init__(
        self,
        model: str = 'qwen2.5-vl:7b',
        ollama_host: str = 'http://localhost:11434',
        timeout: float = 60.0
    ):
        """
        Initialize Qwen-VL interface.

        Args:
            model: Ollama model name
            ollama_host: Ollama API endpoint
            timeout: Request timeout in seconds
        """
        self.model = model
        self.ollama_host = ollama_host.rstrip('/')
        self.timeout = timeout
        self._available = None

    def is_available(self) -> bool:
        """Check if Ollama and model are available."""
        if self._available is not None:
            return self._available

        if not HAS_REQUESTS:
            logger.error("requests library not installed")
            self._available = False
            return False

        try:
            # Check Ollama is running
            response = requests.get(
                f'{self.ollama_host}/api/tags',
                timeout=5
            )

            if response.status_code != 200:
                logger.warning("Ollama not responding")
                self._available = False
                return False

            # Check if model is available
            models = response.json().get('models', [])
            model_names = [m.get('name', '') for m in models]

            if not any(self.model in name for name in model_names):
                logger.warning(
                    f"Model {self.model} not found. "
                    f"Install with: ollama pull {self.model}"
                )
                self._available = False
                return False

            self._available = True
            return True

        except Exception as e:
            logger.error(f"Ollama check failed: {e}")
            self._available = False
            return False

    def _image_to_base64(self, image: np.ndarray) -> str:
        """Convert numpy image to base64 string."""
        try:
            import cv2
            _, buffer = cv2.imencode('.png', image)
            return base64.b64encode(buffer).decode('utf-8')
        except ImportError:
            from PIL import Image
            img = Image.fromarray(image[:, :, ::-1])  # BGR to RGB
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def analyze(
        self,
        image: np.ndarray,
        prompt: str = "Describe what you see on this screen.",
        max_tokens: int = 500
    ) -> str:
        """
        Analyze an image with a prompt.

        Args:
            image: Screen image (BGR numpy array)
            prompt: Question or instruction
            max_tokens: Maximum response tokens

        Returns:
            Model's response text
        """
        if not self.is_available():
            return "Vision model not available"

        try:
            image_b64 = self._image_to_base64(image)

            payload = {
                'model': self.model,
                'prompt': prompt,
                'images': [image_b64],
                'stream': False,
                'options': {
                    'num_predict': max_tokens,
                }
            }

            response = requests.post(
                f'{self.ollama_host}/api/generate',
                json=payload,
                timeout=self.timeout
            )

            if response.status_code != 200:
                logger.error(f"Ollama error: {response.status_code}")
                return f"Error: {response.status_code}"

            result = response.json()
            return result.get('response', '')

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return f"Error: {e}"

    def find_element(
        self,
        image: np.ndarray,
        description: str
    ) -> Optional[Dict[str, Any]]:
        """
        Find a UI element matching a description.

        Args:
            image: Screen image
            description: Natural language description of element

        Returns:
            Dict with element info or None
        """
        prompt = f"""Look at this screen and find the UI element that matches this description: "{description}"

If you find it, respond with JSON in this exact format:
{{"found": true, "type": "button/input/link/etc", "text": "visible text", "location": "general location description"}}

If not found, respond with:
{{"found": false, "reason": "why not found"}}

Respond only with JSON, no other text."""

        response = self.analyze(image, prompt, max_tokens=200)

        try:
            # Try to parse JSON from response
            # Handle potential markdown code blocks
            if '```' in response:
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]

            result = json.loads(response.strip())
            return result if result.get('found') else None

        except json.JSONDecodeError:
            logger.warning(f"Could not parse response as JSON: {response[:100]}")
            return None

    def describe_screen(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Get a structured description of the screen.

        Args:
            image: Screen image

        Returns:
            Dict with screen analysis
        """
        prompt = """Analyze this screen and provide a structured description.

Respond with JSON containing:
{
    "application": "name of application or website",
    "screen_type": "login/dashboard/settings/etc",
    "main_elements": ["list of visible UI elements"],
    "state": "what state/mode the application is in",
    "possible_actions": ["list of actions user could take"]
}

Respond only with JSON."""

        response = self.analyze(image, prompt, max_tokens=400)

        try:
            if '```' in response:
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]

            return json.loads(response.strip())

        except json.JSONDecodeError:
            return {
                'application': 'unknown',
                'screen_type': 'unknown',
                'main_elements': [],
                'state': 'unknown',
                'possible_actions': [],
                'raw_response': response
            }

    def get_next_action(
        self,
        image: np.ndarray,
        goal: str,
        history: List[str] = None
    ) -> Dict[str, Any]:
        """
        Determine the next action to take toward a goal.

        Args:
            image: Current screen image
            goal: What we're trying to accomplish
            history: List of previous actions taken

        Returns:
            Dict with recommended action
        """
        history_text = ""
        if history:
            history_text = "Previous actions taken:\n" + "\n".join(f"- {a}" for a in history[-5:])

        prompt = f"""Current goal: {goal}

{history_text}

Look at the current screen state and determine the next action to take.

Respond with JSON:
{{
    "action": "click/type/scroll/wait/done/error",
    "target": "description of element to interact with",
    "value": "text to type if action is type, otherwise null",
    "reasoning": "brief explanation of why this action",
    "confidence": 0.0-1.0
}}

Respond only with JSON."""

        response = self.analyze(image, prompt, max_tokens=300)

        try:
            if '```' in response:
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]

            return json.loads(response.strip())

        except json.JSONDecodeError:
            return {
                'action': 'error',
                'target': None,
                'value': None,
                'reasoning': f'Could not parse response: {response[:100]}',
                'confidence': 0.0
            }

    def verify_action_result(
        self,
        before_image: np.ndarray,
        after_image: np.ndarray,
        expected_change: str
    ) -> Dict[str, Any]:
        """
        Verify if an action had the expected result.

        Args:
            before_image: Screen before action
            after_image: Screen after action
            expected_change: Description of expected change

        Returns:
            Dict with verification result
        """
        # This would ideally use both images, but most VLMs take one image
        # We'll describe the expected change and check the after state
        prompt = f"""The expected change after the last action was: "{expected_change}"

Look at the current screen and determine if this change happened.

Respond with JSON:
{{
    "success": true/false,
    "observed_change": "what actually changed",
    "matches_expected": true/false,
    "confidence": 0.0-1.0
}}

Respond only with JSON."""

        response = self.analyze(after_image, prompt, max_tokens=200)

        try:
            if '```' in response:
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]

            return json.loads(response.strip())

        except json.JSONDecodeError:
            return {
                'success': False,
                'observed_change': 'Could not analyze',
                'matches_expected': False,
                'confidence': 0.0
            }
