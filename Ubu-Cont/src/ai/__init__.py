"""
AI Module

Provides AI capabilities for the computer control system.

Modules:
    - openrouter_client: OpenRouter API client for Qwen models
"""

from .openrouter_client import OpenRouterClient, OpenRouterConfig

__all__ = ["OpenRouterClient", "OpenRouterConfig"]
