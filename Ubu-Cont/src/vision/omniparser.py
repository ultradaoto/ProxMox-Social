"""
OmniParser Integration

UI element detection using OmniParser V2 or similar models.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False


@dataclass
class UIElement:
    """Detected UI element."""
    element_type: str  # button, text, input, image, icon, etc.
    label: str  # Text label or description
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    center: Tuple[int, int]  # Center point for clicking
    confidence: float  # Detection confidence (0-1)
    attributes: Dict[str, Any] = field(default_factory=dict)

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    @property
    def width(self) -> int:
        return self.bbox[2]

    @property
    def height(self) -> int:
        return self.bbox[3]

    @property
    def center_x(self) -> int:
        return self.center[0]

    @property
    def center_y(self) -> int:
        return self.center[1]

    @property
    def area(self) -> int:
        return self.width * self.height

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside this element."""
        return (self.x <= x <= self.x + self.width and
                self.y <= y <= self.y + self.height)


@dataclass
class ScreenAnalysis:
    """Complete analysis of a screen capture."""
    elements: List[UIElement]
    timestamp: float
    resolution: Tuple[int, int]
    text_content: str = ""
    dominant_colors: List[Tuple[int, int, int]] = field(default_factory=list)


class OmniParser:
    """
    UI element detection using OmniParser.

    OmniParser is a vision model specialized for detecting and
    understanding UI elements in screenshots.
    """

    def __init__(
        self,
        model_path: str = 'models/omniparser_v2.pt',
        confidence_threshold: float = 0.7,
        device: str = 'auto'
    ):
        """
        Initialize OmniParser.

        Args:
            model_path: Path to model weights
            confidence_threshold: Minimum confidence for detections
            device: Device to run on ('cpu', 'cuda', 'auto')
        """
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self.model = None

        # Determine device
        if device == 'auto':
            if HAS_TORCH and torch.cuda.is_available():
                self.device = 'cuda'
            else:
                self.device = 'cpu'
        else:
            self.device = device

        self._loaded = False

    def load_model(self) -> bool:
        """
        Load the OmniParser model.

        Returns:
            True if model loaded successfully
        """
        if not HAS_TORCH:
            logger.error("PyTorch not installed. Install with: pip install torch")
            return False

        if not self.model_path.exists():
            logger.warning(f"Model not found at {self.model_path}")
            logger.info("Using fallback detection. Download model with install_models.sh")
            self._loaded = False
            return False

        try:
            logger.info(f"Loading OmniParser from {self.model_path}")
            self.model = torch.load(self.model_path, map_location=self.device)
            self.model.eval()
            self._loaded = True
            logger.info(f"Model loaded on {self.device}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            return False

    def detect_elements(self, frame: np.ndarray) -> List[UIElement]:
        """
        Detect UI elements in a frame.

        Args:
            frame: BGR image as numpy array

        Returns:
            List of detected UIElement objects
        """
        import time
        start_time = time.time()

        if self._loaded and self.model is not None:
            elements = self._detect_with_model(frame)
        else:
            elements = self._detect_fallback(frame)

        # Filter by confidence
        elements = [e for e in elements if e.confidence >= self.confidence_threshold]

        elapsed = time.time() - start_time
        logger.debug(f"Detected {len(elements)} elements in {elapsed:.3f}s")

        return elements

    def _detect_with_model(self, frame: np.ndarray) -> List[UIElement]:
        """Detect elements using loaded model."""
        try:
            import cv2

            # Preprocess image
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (640, 640))

            # Convert to tensor
            tensor = torch.from_numpy(img).permute(2, 0, 1).float() / 255.0
            tensor = tensor.unsqueeze(0).to(self.device)

            # Run inference
            with torch.no_grad():
                outputs = self.model(tensor)

            # Parse outputs (format depends on specific model)
            # This is a placeholder for actual model output parsing
            elements = self._parse_model_outputs(outputs, frame.shape)

            return elements

        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return self._detect_fallback(frame)

    def _parse_model_outputs(self, outputs, original_shape) -> List[UIElement]:
        """Parse model outputs to UIElement objects."""
        # This would be customized based on actual OmniParser output format
        elements = []

        # Placeholder parsing logic
        if hasattr(outputs, 'boxes') and hasattr(outputs, 'labels'):
            h, w = original_shape[:2]
            scale_x, scale_y = w / 640, h / 640

            for box, label, score in zip(outputs.boxes, outputs.labels, outputs.scores):
                if score < self.confidence_threshold:
                    continue

                x1, y1, x2, y2 = [int(c) for c in box]
                x1, x2 = int(x1 * scale_x), int(x2 * scale_x)
                y1, y2 = int(y1 * scale_y), int(y2 * scale_y)

                elem = UIElement(
                    element_type=str(label),
                    label="",
                    bbox=(x1, y1, x2 - x1, y2 - y1),
                    center=((x1 + x2) // 2, (y1 + y2) // 2),
                    confidence=float(score),
                )
                elements.append(elem)

        return elements

    def _detect_fallback(self, frame: np.ndarray) -> List[UIElement]:
        """
        Fallback detection using basic CV techniques.

        This provides basic element detection when the ML model isn't available.
        """
        try:
            import cv2
        except ImportError:
            return []

        elements = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Edge detection
        edges = cv2.Canny(gray, 50, 150)

        # Find contours (potential UI elements)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)

            # Filter by size
            if area < 500 or area > frame.shape[0] * frame.shape[1] * 0.5:
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Skip very small or very elongated shapes
            aspect_ratio = w / h if h > 0 else 0
            if aspect_ratio < 0.1 or aspect_ratio > 10:
                continue

            # Guess element type based on shape
            if aspect_ratio > 2 and h < 50:
                elem_type = 'button'
            elif aspect_ratio > 3:
                elem_type = 'text_field'
            elif 0.8 < aspect_ratio < 1.2:
                elem_type = 'icon'
            else:
                elem_type = 'unknown'

            elem = UIElement(
                element_type=elem_type,
                label=f"element_{i}",
                bbox=(x, y, w, h),
                center=(x + w // 2, y + h // 2),
                confidence=0.5,  # Low confidence for fallback detection
            )
            elements.append(elem)

        return elements

    def analyze_screen(self, frame: np.ndarray) -> ScreenAnalysis:
        """
        Complete screen analysis including elements and text.

        Args:
            frame: BGR image as numpy array

        Returns:
            ScreenAnalysis with elements and metadata
        """
        import time

        elements = self.detect_elements(frame)

        return ScreenAnalysis(
            elements=elements,
            timestamp=time.time(),
            resolution=(frame.shape[1], frame.shape[0]),
        )

    def find_element_by_label(
        self,
        frame: np.ndarray,
        label: str,
        partial_match: bool = True
    ) -> Optional[UIElement]:
        """
        Find an element by its label text.

        Args:
            frame: Screen image
            label: Text to search for
            partial_match: Allow partial string matching

        Returns:
            Matching UIElement or None
        """
        elements = self.detect_elements(frame)

        for elem in elements:
            if partial_match:
                if label.lower() in elem.label.lower():
                    return elem
            else:
                if label.lower() == elem.label.lower():
                    return elem

        return None

    def find_elements_by_type(
        self,
        frame: np.ndarray,
        element_type: str
    ) -> List[UIElement]:
        """
        Find all elements of a specific type.

        Args:
            frame: Screen image
            element_type: Type to filter by (button, text, etc.)

        Returns:
            List of matching elements
        """
        elements = self.detect_elements(frame)
        return [e for e in elements if e.element_type == element_type]

    def find_clickable_elements(self, frame: np.ndarray) -> List[UIElement]:
        """Find all clickable elements (buttons, links, etc.)."""
        elements = self.detect_elements(frame)
        clickable_types = {'button', 'link', 'checkbox', 'radio', 'tab'}
        return [e for e in elements if e.element_type in clickable_types]
