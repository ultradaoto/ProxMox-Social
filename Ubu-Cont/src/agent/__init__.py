"""
Agent Module

Provides the main AI agent orchestration:
- Main control loop
- Task management
- Decision engine
- State machine for workflows
"""

from .main_agent import AIComputerAgent
from .task_manager import TaskManager
from .decision_engine import DecisionEngine

__all__ = ['AIComputerAgent', 'TaskManager', 'DecisionEngine']
