"""YouTube transcript extraction utilities using yt-dlp.

This package provides functionality to extract transcripts from YouTube videos
using yt-dlp as the backend, with support for multiple languages
and structured output formats.
"""

from .extractor import (
    TranscriptExtractor,
    TranscriptExtractorError,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from .metadata import (
    MetadataGenerator,
    VideoMetadata,
    AIGeneratedContent,
    MetadataGenerationError,
    YouTubeAPIError,
    OpenAIError,
)

__version__ = "0.1.0"
__all__ = [
    "TranscriptExtractor",
    "TranscriptExtractorError",
    "TranscriptsDisabled",
    "NoTranscriptFound",
    "VideoUnavailable",
    "MetadataGenerator",
    "VideoMetadata",
    "AIGeneratedContent",
    "MetadataGenerationError",
    "YouTubeAPIError",
    "OpenAIError",
]
