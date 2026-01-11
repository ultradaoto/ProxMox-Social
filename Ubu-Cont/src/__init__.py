"""
Ubuntu Brain Agent - Main Package

This package provides AI-powered computer control capabilities:
- Screen capture via VNC from Windows 10 VM
- Vision AI (Qwen2.5-VL) for UI element detection
- Human-like mouse and keyboard input
- Social media posting workflow orchestration

Brain Architecture:
- Fetcher: Polls API for pending posts
- VNC Capture: Screenshots from Windows 10
- Vision Engine: Qwen2.5-VL interface (the eyes)
- Input Injector: Mouse/keyboard commands to Windows
- Orchestrator: Main brain loop
- Workflows: Platform-specific posting steps
"""

__version__ = '0.2.0'
__author__ = 'Proxmox Computer Control Team'
