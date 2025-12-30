"""
Vision Processing Module

Provides computer vision and AI capabilities for screen analysis:
- OmniParser for UI element detection
- Qwen-VL for vision-language understanding
- OCR for text extraction
- Element tracking across frames
"""

from .omniparser import OmniParser
from .ocr import OCRProcessor
from .element_tracker import ElementTracker

__all__ = ['OmniParser', 'OCRProcessor', 'ElementTracker']
