"""
Screen Capture Module

Provides VNC and Spice screen capture capabilities for the Windows VM.
"""

from .vnc_capturer import VNCCapturer
from .frame_buffer import FrameBuffer

__all__ = ['VNCCapturer', 'FrameBuffer']
