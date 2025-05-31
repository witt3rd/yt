"""Common utilities for YouTube tools.

This package provides shared functionality including configuration management,
logging setup, and common type definitions used across all YouTube utility packages.
"""

from .config import Config
from .logger import setup_logger
from .types import VideoInfo, TranscriptSegment

__version__ = "0.1.0"
__all__ = ["Config", "setup_logger", "VideoInfo", "TranscriptSegment"]
