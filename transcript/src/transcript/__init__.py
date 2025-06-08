"""YouTube transcript extraction utilities.

This package provides functionality to extract transcripts from YouTube videos
using the youtube-transcript-api library, with support for multiple languages
and structured output formats. Includes metadata generation for enhanced
markdown output with AI-powered filenames and frontmatter.
"""

from .extractor import TranscriptExtractor
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
    "MetadataGenerator",
    "VideoMetadata",
    "AIGeneratedContent",
    "MetadataGenerationError",
    "YouTubeAPIError",
    "OpenAIError",
]
