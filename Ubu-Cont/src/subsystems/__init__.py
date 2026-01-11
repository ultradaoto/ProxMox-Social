"""
Subsystems package - Core components for the Ubuntu Brain.

Contains:
- VNCCapture: Screenshots from Windows 10
- VisionEngine: Qwen2.5-VL interface (the eyes)
- InputInjector: Mouse/keyboard commands to Windows
"""

from src.subsystems.vnc_capture import VNCCapture
from src.subsystems.vision_engine import VisionEngine
from src.subsystems.input_injector import InputInjector

__all__ = ['VNCCapture', 'VisionEngine', 'InputInjector']
