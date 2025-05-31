"""YouTube transcript extraction utilities.

This package provides functionality to extract transcripts from YouTube videos
using the youtube-transcript-api library, with support for multiple languages
and structured output formats.
"""

from .extractor import TranscriptExtractor

__version__ = "0.1.0"
__all__ = ["TranscriptExtractor"]
