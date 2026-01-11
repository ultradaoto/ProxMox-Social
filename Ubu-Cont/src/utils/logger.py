"""
Logger utilities - Wrapper for consistent logging across the brain.

This module wraps the existing logging module and provides
convenient functions for the brain agent.
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


_logging_initialized = False


def setup_logging(
    level: str = 'INFO',
    log_file: Optional[str] = None,
    log_dir: Optional[str] = 'logs',
    colored: bool = True,
    save_screenshots: bool = True
) -> logging.Logger:
    """
    Set up logging configuration for the brain.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Specific log file path (overrides log_dir)
        log_dir: Directory for log files
        colored: Whether to use colored console output
        save_screenshots: Whether to enable screenshot saving

    Returns:
        Root logger instance
    """
    global _logging_initialized
    
    if _logging_initialized:
        return logging.getLogger()
    
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

    if colored and sys.platform != 'win32':
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

    # File handler
    if log_dir or log_file:
        if log_file:
            file_path = Path(log_file)
            file_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            log_dir_path = Path(log_dir)
            log_dir_path.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_path = log_dir_path / f'brain_{timestamp}.log'

        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log everything to file

        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)
        root_logger.addHandler(file_handler)

        root_logger.info(f"Logging to file: {file_path}")

    # Create screenshots directory if needed
    if save_screenshots and log_dir:
        screenshots_dir = Path(log_dir) / 'screenshots'
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        root_logger.debug(f"Screenshots directory: {screenshots_dir}")

    _logging_initialized = True
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


def get_screenshots_dir() -> Path:
    """Get the screenshots directory path."""
    return Path('logs/screenshots')
