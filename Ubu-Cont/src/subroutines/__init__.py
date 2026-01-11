"""
Subroutines package - Utility subroutines for the Ubuntu Brain.

Contains:
- WindowsLoginSubroutine: Handles Windows login screen
- BrowserFocusSubroutine: Ensures Chrome is focused
- ErrorRecoverySubroutine: Handles unexpected states
"""

from src.subroutines.windows_login import WindowsLoginSubroutine
from src.subroutines.browser_focus import BrowserFocusSubroutine
from src.subroutines.error_recovery import ErrorRecoverySubroutine

__all__ = ['WindowsLoginSubroutine', 'BrowserFocusSubroutine', 'ErrorRecoverySubroutine']
