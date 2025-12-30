"""
Structured Logging Configuration

Provides consistent logging across all modules.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors to log output."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str] = None,
    log_dir: Optional[str] = None,
    colored: bool = True
) -> logging.Logger:
    """
    Set up logging configuration.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Specific log file path
        log_dir: Directory for log files (auto-generates filename)
        colored: Whether to use colored console output

    Returns:
        Root logger instance
    """
    # Get numeric level
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)

    if colored:
        console_format = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )

    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # File handler (if configured)
    if log_file or log_dir:
        if log_file:
            file_path = Path(log_file)
        else:
            log_dir = Path(log_dir or 'logs')
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = log_dir / f'agent_{timestamp}.log'

        file_handler = logging.FileHandler(file_path)
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file

        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {file_path}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class ActionLogger:
    """
    Specialized logger for tracking agent actions.

    Logs actions with structured data for later analysis.
    """

    def __init__(self, log_dir: str = 'logs/actions'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger('actions')

        # Create action-specific log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.action_file = self.log_dir / f'actions_{timestamp}.jsonl'

    def log_action(self, action_type: str, details: dict, screenshot_path: Optional[str] = None):
        """Log an action with structured data."""
        import json

        entry = {
            'timestamp': datetime.now().isoformat(),
            'action_type': action_type,
            'details': details,
            'screenshot': screenshot_path,
        }

        # Log to main logger
        self.logger.info(f"Action: {action_type} - {details}")

        # Write to JSONL file
        with open(self.action_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def log_click(self, x: int, y: int, button: str = 'left'):
        """Log a click action."""
        self.log_action('click', {'x': x, 'y': y, 'button': button})

    def log_type(self, text: str, masked: bool = False):
        """Log a typing action."""
        display_text = '*' * len(text) if masked else text
        self.log_action('type', {'text': display_text, 'length': len(text)})

    def log_scroll(self, amount: int, direction: str):
        """Log a scroll action."""
        self.log_action('scroll', {'amount': amount, 'direction': direction})

    def log_decision(self, reason: str, confidence: float):
        """Log a decision made by the agent."""
        self.log_action('decision', {'reason': reason, 'confidence': confidence})
