"""
OCR (Optical Character Recognition) Module

Extracts text from screen captures using various OCR backends.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# OCR backend availability
try:
    import easyocr
    HAS_EASYOCR = True
except ImportError:
    HAS_EASYOCR = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


@dataclass
class TextRegion:
    """Detected text region with bounding box."""
    text: str
    bbox: Tuple[int, int, int, int]  # x, y, width, height
    confidence: float
    center: Tuple[int, int]

    @property
    def x(self) -> int:
        return self.bbox[0]

    @property
    def y(self) -> int:
        return self.bbox[1]

    def contains_point(self, x: int, y: int) -> bool:
        """Check if point is inside this region."""
        return (self.bbox[0] <= x <= self.bbox[0] + self.bbox[2] and
                self.bbox[1] <= y <= self.bbox[1] + self.bbox[3])


class OCRProcessor:
    """
    OCR processor for extracting text from screen images.

    Supports multiple backends:
    - EasyOCR (default, best for UI text)
    - Tesseract (faster, widely available)
    """

    def __init__(
        self,
        backend: str = 'auto',
        languages: List[str] = None,
        confidence_threshold: float = 0.5
    ):
        """
        Initialize OCR processor.

        Args:
            backend: 'easyocr', 'tesseract', or 'auto'
            languages: List of language codes (e.g., ['en', 'es'])
            confidence_threshold: Minimum confidence for text detection
        """
        self.languages = languages or ['en']
        self.confidence_threshold = confidence_threshold

        # Select backend
        if backend == 'auto':
            if HAS_EASYOCR:
                self.backend = 'easyocr'
            elif HAS_TESSERACT:
                self.backend = 'tesseract'
            else:
                logger.warning("No OCR backend available")
                self.backend = None
        else:
            self.backend = backend

        self._reader = None

    def _init_reader(self):
        """Initialize OCR reader lazily."""
        if self._reader is not None:
            return

        if self.backend == 'easyocr':
            try:
                self._reader = easyocr.Reader(
                    self.languages,
                    gpu=True,  # Use GPU if available
                    verbose=False
                )
                logger.info("EasyOCR reader initialized")
            except Exception as e:
                logger.error(f"Failed to initialize EasyOCR: {e}")
                # Fallback to Tesseract
                if HAS_TESSERACT:
                    self.backend = 'tesseract'
                    logger.info("Falling back to Tesseract")

    def extract_text(self, frame: np.ndarray) -> str:
        """
        Extract all text from an image.

        Args:
            frame: BGR image as numpy array

        Returns:
            Extracted text as single string
        """
        regions = self.extract_text_regions(frame)
        # Sort by position (top-to-bottom, left-to-right)
        regions.sort(key=lambda r: (r.y, r.x))
        return ' '.join(r.text for r in regions)

    def extract_text_regions(self, frame: np.ndarray) -> List[TextRegion]:
        """
        Extract text regions with bounding boxes.

        Args:
            frame: BGR image as numpy array

        Returns:
            List of TextRegion objects
        """
        if self.backend == 'easyocr':
            return self._extract_easyocr(frame)
        elif self.backend == 'tesseract':
            return self._extract_tesseract(frame)
        else:
            logger.warning("No OCR backend available")
            return []

    def _extract_easyocr(self, frame: np.ndarray) -> List[TextRegion]:
        """Extract text using EasyOCR."""
        self._init_reader()

        if self._reader is None:
            return []

        try:
            # EasyOCR expects RGB
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            results = self._reader.readtext(rgb)

            regions = []
            for bbox, text, confidence in results:
                if confidence < self.confidence_threshold:
                    continue

                # Convert bbox to x, y, w, h format
                # EasyOCR returns [[x1,y1], [x2,y1], [x2,y2], [x1,y2]]
                x1 = int(min(p[0] for p in bbox))
                y1 = int(min(p[1] for p in bbox))
                x2 = int(max(p[0] for p in bbox))
                y2 = int(max(p[1] for p in bbox))

                region = TextRegion(
                    text=text,
                    bbox=(x1, y1, x2 - x1, y2 - y1),
                    confidence=confidence,
                    center=((x1 + x2) // 2, (y1 + y2) // 2)
                )
                regions.append(region)

            return regions

        except Exception as e:
            logger.error(f"EasyOCR extraction failed: {e}")
            return []

    def _extract_tesseract(self, frame: np.ndarray) -> List[TextRegion]:
        """Extract text using Tesseract."""
        try:
            import cv2

            # Convert to grayscale for better OCR
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Get detailed output
            data = pytesseract.image_to_data(
                gray,
                lang='+'.join(self.languages),
                output_type=pytesseract.Output.DICT
            )

            regions = []
            n_boxes = len(data['text'])

            for i in range(n_boxes):
                text = data['text'][i].strip()
                conf = float(data['conf'][i]) / 100.0

                if not text or conf < self.confidence_threshold:
                    continue

                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]

                region = TextRegion(
                    text=text,
                    bbox=(x, y, w, h),
                    confidence=conf,
                    center=(x + w // 2, y + h // 2)
                )
                regions.append(region)

            return regions

        except Exception as e:
            logger.error(f"Tesseract extraction failed: {e}")
            return []

    def find_text(
        self,
        frame: np.ndarray,
        search_text: str,
        partial_match: bool = True
    ) -> Optional[TextRegion]:
        """
        Find a specific text in the image.

        Args:
            frame: Image to search
            search_text: Text to find
            partial_match: Allow partial matching

        Returns:
            TextRegion if found, None otherwise
        """
        regions = self.extract_text_regions(frame)

        search_lower = search_text.lower()
        for region in regions:
            if partial_match:
                if search_lower in region.text.lower():
                    return region
            else:
                if search_lower == region.text.lower():
                    return region

        return None

    def find_all_text(
        self,
        frame: np.ndarray,
        search_text: str
    ) -> List[TextRegion]:
        """
        Find all occurrences of text in the image.

        Args:
            frame: Image to search
            search_text: Text to find

        Returns:
            List of matching TextRegions
        """
        regions = self.extract_text_regions(frame)
        search_lower = search_text.lower()
        return [r for r in regions if search_lower in r.text.lower()]

    def get_text_at_point(
        self,
        frame: np.ndarray,
        x: int,
        y: int
    ) -> Optional[TextRegion]:
        """
        Get text at a specific screen coordinate.

        Args:
            frame: Image
            x: X coordinate
            y: Y coordinate

        Returns:
            TextRegion at that point, or None
        """
        regions = self.extract_text_regions(frame)

        for region in regions:
            if region.contains_point(x, y):
                return region

        return None


class TextMatcher:
    """
    Advanced text matching utilities.
    """

    @staticmethod
    def fuzzy_match(text: str, pattern: str, threshold: float = 0.8) -> bool:
        """
        Fuzzy string matching.

        Args:
            text: Text to check
            pattern: Pattern to match
            threshold: Similarity threshold (0-1)

        Returns:
            True if similar enough
        """
        try:
            from difflib import SequenceMatcher
            ratio = SequenceMatcher(None, text.lower(), pattern.lower()).ratio()
            return ratio >= threshold
        except Exception:
            return text.lower() == pattern.lower()

    @staticmethod
    def find_similar(
        regions: List[TextRegion],
        pattern: str,
        threshold: float = 0.8
    ) -> List[TextRegion]:
        """
        Find regions with similar text.

        Args:
            regions: Text regions to search
            pattern: Pattern to match
            threshold: Similarity threshold

        Returns:
            Matching regions sorted by similarity
        """
        from difflib import SequenceMatcher

        matches = []
        pattern_lower = pattern.lower()

        for region in regions:
            ratio = SequenceMatcher(
                None, region.text.lower(), pattern_lower
            ).ratio()

            if ratio >= threshold:
                matches.append((ratio, region))

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[0], reverse=True)
        return [m[1] for m in matches]
