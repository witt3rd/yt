"""Common utilities for YouTube tools.

This package provides shared functionality including configuration management,
logging setup, common type definitions, and URL utilities used across all
YouTube utility packages.
"""

from .config import Config
from .logger import setup_logger
from .types import VideoInfo, TranscriptSegment
from .url_utils import (
    is_remote_pdf_url,
)

__version__ = "0.1.0"
__all__ = [
    "Config",
    "setup_logger",
    "VideoInfo",
    "TranscriptSegment",
    "is_remote_pdf_url",
]
