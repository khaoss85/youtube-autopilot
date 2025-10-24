"""
Centralized logging module for yt_autopilot.
All modules should import logger from here.
"""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    name: str = "yt_autopilot",
    level: Optional[str] = None,
    log_file: Optional[Path] = None
) -> logging.Logger:
    """
    Creates and configures a logger instance.

    Args:
        name: Logger name (default: "yt_autopilot")
        level: Log level string ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
               If None, reads from config or defaults to INFO
        log_file: Optional path to log file. If provided, logs to both file and console.

    Returns:
        Configured logger instance
    """
    # Determine log level
    if level is None:
        # Avoid circular import by lazy loading
        try:
            from yt_autopilot.core.config import get_config
            config = get_config()
            level = config.get("LOG_LEVEL", "INFO")
        except ImportError:
            level = "INFO"

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Formatter with timestamp
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Global logger instance - import this from other modules
logger = setup_logger()
