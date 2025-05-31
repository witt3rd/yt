"""Logging setup for YouTube utilities.

This module provides centralized logging configuration using loguru,
following Python 3.13 best practices for clean, structured logging.
"""

import sys
from pathlib import Path
from typing import Optional
from loguru import logger


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str | Path] = None,
    format_string: Optional[str] = None
) -> None:
    """Set up logging configuration for YouTube utilities.

    Parameters
    ----------
    level : str, default "INFO"
        Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    log_file : str or Path, optional
        Path to log file. If provided, logs will be written to both
        console and file.
    format_string : str, optional
        Custom log format string. If None, uses a sensible default.

    Examples
    --------
    >>> setup_logger("DEBUG", "app.log")
    >>> logger.info("Application started")

    Notes
    -----
    This function removes all existing loguru handlers and sets up
    new ones according to the specified configuration.
    """
    # Remove all existing handlers
    logger.remove()

    # Default format with colors for console
    if format_string is None:
        format_string = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    # Add console handler
    logger.add(
        sys.stderr,
        level=level,
        format=format_string,
        colorize=True,
        backtrace=True,
        diagnose=True
    )

    # Add file handler if specified
    if log_file:
        file_format = (
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        )

        logger.add(
            log_file,
            level=level,
            format=file_format,
            rotation="10 MB",  # Rotate when file reaches 10MB
            retention="1 week",  # Keep logs for 1 week
            compression="zip",  # Compress rotated logs
            backtrace=True,
            diagnose=True
        )

    logger.info(f"Logging initialized at {level} level")
    if log_file:
        logger.info(f"File logging enabled: {log_file}")


def get_logger(name: str):
    """Get a logger instance for a specific module.

    Parameters
    ----------
    name : str
        Name for the logger, typically __name__ of the calling module.

    Returns
    -------
    loguru.Logger
        Configured logger instance.

    Examples
    --------
    >>> module_logger = get_logger(__name__)
    >>> module_logger.info("Module operation completed")

    Notes
    -----
    This function returns the same loguru logger instance but can be used
    to maintain consistency with standard logging patterns.
    """
    return logger.bind(name=name)
