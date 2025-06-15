"""Simplified metadata generation for yt-dlp based transcript extraction.

This module provides basic metadata functionality that works with yt-dlp
video information instead of the YouTube Data API.
"""

import re
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from common.config import Config
from common.types import VideoInfo


class MetadataGenerationError(Exception):
    """Base exception for metadata generation errors."""
    pass


class YouTubeAPIError(MetadataGenerationError):
    """Raised when YouTube operations fail (compatibility stub)."""
    pass


class OpenAIError(MetadataGenerationError):
    """Raised when OpenAI operations fail (compatibility stub)."""
    pass


@dataclass
class VideoMetadata:
    """YouTube video metadata structure (simplified for yt-dlp).

    Parameters
    ----------
    video_id : str
        YouTube video identifier.
    title : str
        Video title.
    channel : str
        Channel name.
    publish_date : str
        Publication date (may be empty if not available).
    description : str
        Video description (may be empty if not available).
    url : str
        Full YouTube URL.
    """

    video_id: str
    title: str
    channel: str
    publish_date: str
    description: str
    url: str


@dataclass
class AIGeneratedContent:
    """AI-generated content structure (compatibility stub).

    Parameters
    ----------
    filename : str
        Suggested filename.
    tags : list[str]
        Generated tags.
    authors : list[str]
        Identified authors.
    """

    filename: str
    tags: list[str]
    authors: list[str]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage.

    Parameters
    ----------
    filename : str
        Raw filename.

    Returns
    -------
    str
        Sanitized filename safe for file systems.
    """
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '-', filename)
    # Remove consecutive dashes and clean up
    sanitized = re.sub(r'-+', '-', sanitized).strip('-')
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200].rstrip('-')
    return sanitized


class MetadataGenerator:
    """Generate YouTube video metadata using yt-dlp video info.

    This is a simplified version that works with yt-dlp's get_video_info
    instead of requiring the YouTube Data API.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.
    """

    def __init__(self, config: Config | None = None):
        """Initialize metadata generator.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        self.config = config or Config()

    def fetch_video_metadata(self, video_id: str) -> VideoMetadata:
        """Fetch video metadata using yt-dlp video info.

        Parameters
        ----------
        video_id : str
            YouTube video identifier.

        Returns
        -------
        VideoMetadata
            Video metadata structure.

        Raises
        ------
        YouTubeAPIError
            If unable to fetch video metadata.
        """
        from .extractor import TranscriptExtractor

        try:
            logger.info(f"Fetching metadata for video: {video_id}")
            extractor = TranscriptExtractor(self.config)
            video_info = extractor.get_video_info(video_id)

            # Convert VideoInfo to VideoMetadata format
            metadata = VideoMetadata(
                video_id=video_id,
                title=video_info.title or f"Video {video_id}",
                channel=video_info.channel or "Unknown Channel",
                publish_date="",  # Not available from yt-dlp basic info
                description="",   # Not available from yt-dlp basic info
                url=f"https://www.youtube.com/watch?v={video_id}",
            )

            logger.info(f"Successfully fetched metadata for: {metadata.title}")
            return metadata

        except Exception as e:
            error_msg = f"Failed to fetch metadata for video {video_id}: {e}"
            logger.error(error_msg)
            raise YouTubeAPIError(error_msg) from e

    def generate_ai_content(self, metadata: VideoMetadata) -> AIGeneratedContent:
        """Generate AI content (simplified stub).

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.

        Returns
        -------
        AIGeneratedContent
            Basic AI content with simple filename generation.
        """
        # Simple filename generation based on title and channel
        title_part = sanitize_filename(metadata.title)[:100]
        channel_part = sanitize_filename(metadata.channel)[:50]

        # Create a reasonable filename
        if title_part and channel_part:
            filename = f"{title_part}-{channel_part}.md"
        elif title_part:
            filename = f"{title_part}.md"
        else:
            filename = f"{metadata.video_id}.md"

        # Basic tags from title
        tags = []
        if metadata.title:
            # Extract potential tags from title
            words = re.findall(r'\b\w+\b', metadata.title.lower())
            common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            tags = [word for word in words if len(word) > 3 and word not in common_words][:5]

        # Use channel as author
        authors = [metadata.channel] if metadata.channel != "Unknown Channel" else []

        return AIGeneratedContent(
            filename=filename,
            tags=tags,
            authors=authors,
        )

    def construct_frontmatter(
        self,
        metadata: VideoMetadata,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Construct YAML frontmatter for YouTube video.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content.

        Returns
        -------
        str
            YAML frontmatter string.
        """
        frontmatter_lines = ["---"]

        # Basic metadata
        frontmatter_lines.append(f'title: "{metadata.title}"')
        frontmatter_lines.append(f"source: YouTube")
        frontmatter_lines.append(f'channel: "{metadata.channel}"')
        frontmatter_lines.append(f"url: {metadata.url}")
        frontmatter_lines.append(f"video_id: {metadata.video_id}")

        if metadata.publish_date:
            frontmatter_lines.append(f"date: {metadata.publish_date}")

        # AI-generated content if available
        if ai_content:
            if ai_content.tags:
                tags_str = ", ".join(f'"{tag}"' for tag in ai_content.tags)
                frontmatter_lines.append(f"tags: [{tags_str}]")

            if ai_content.authors:
                authors_str = ", ".join(f'"{author}"' for author in ai_content.authors)
                frontmatter_lines.append(f"authors: [{authors_str}]")

        frontmatter_lines.append("---")
        return "\n".join(frontmatter_lines)

    def generate_markdown_content(
        self,
        metadata: VideoMetadata,
        content: str,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Generate complete markdown content with frontmatter.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.
        content : str
            Main content (transcript or summary).
        ai_content : AIGeneratedContent, optional
            AI-generated content for enhanced metadata.

        Returns
        -------
        str
            Complete markdown content with frontmatter.
        """
        frontmatter = self.construct_frontmatter(metadata, ai_content)
        return f"{frontmatter}\n\n{content}"

    def get_suggested_filename(
        self,
        metadata: VideoMetadata,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Get suggested filename for the markdown file.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content with filename suggestion.

        Returns
        -------
        str
            Suggested filename with .md extension.
        """
        if ai_content and ai_content.filename:
            return ai_content.filename

        # Fallback filename generation
        title_part = sanitize_filename(metadata.title)[:100] if metadata.title else metadata.video_id
        return f"{title_part}.md"
