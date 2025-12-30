"""
Human-Like Input Module

Provides human-like mouse and keyboard input simulation:
- Bezier curve mouse trajectories
- Fitts's Law timing
- Variable typing speed with errors
- Personal profile learning
"""

from .human_mouse import HumanMouse
from .human_keyboard import HumanKeyboard
from .remote_sender import RemoteSender

__all__ = ['HumanMouse', 'HumanKeyboard', 'RemoteSender']
