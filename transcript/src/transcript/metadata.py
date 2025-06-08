"""YouTube metadata generation for enhanced transcript output.

This module provides functionality to fetch YouTube video metadata using the
YouTube Data API and generate AI-powered filenames, tags, and frontmatter
for Obsidian-compatible markdown output.
"""

import os
from dataclasses import dataclass
from typing import override
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from loguru import logger

from common.config import Config
from common.ai_metadata import (
    AIMetadataGenerator,
    AIGeneratedContent,
    MetadataGenerationError,
    sanitize_filename,
)


@dataclass
class VideoMetadata:
    """YouTube video metadata structure.

    Parameters
    ----------
    video_id : str
        YouTube video identifier.
    title : str
        Video title.
    channel : str
        Channel name.
    publish_date : str
        Publication date in YYYY-MM-DD format.
    description : str
        Video description text.
    url : str
        Full YouTube URL.
    """

    video_id: str
    title: str
    channel: str
    publish_date: str
    description: str
    url: str


class YouTubeAPIError(MetadataGenerationError):
    """Raised when YouTube Data API operations fail."""

    pass


class OpenAIError(MetadataGenerationError):
    """Raised when OpenAI API operations fail."""

    pass


class MetadataGenerator(AIMetadataGenerator):
    """Generate YouTube video metadata and AI-powered content.

    Provides methods to fetch video metadata from YouTube Data API and
    generate AI-powered filenames, tags, and authors using OpenAI.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> generator = MetadataGenerator()
    >>> metadata = generator.fetch_video_metadata("dQw4w9WgXcQ")
    >>> metadata.title
    "Never Gonna Give You Up"
    """

    def __init__(self, config: Config | None = None):
        """Initialize metadata generator.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        super().__init__(config)
        self._youtube_api_key = os.getenv("YOUTUBE_API_KEY")

    @override
    def _get_content_context(self, metadata: VideoMetadata) -> str:
        """Get content context string for AI prompts.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.

        Returns
        -------
        str
            Context string for AI prompts.
        """
        return f"YouTube video '{metadata.title}' from channel '{metadata.channel}'"

    @override
    def _get_filename_context(self, metadata: VideoMetadata) -> tuple[str, str]:
        """Get title and source context for filename generation.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.

        Returns
        -------
        tuple[str, str]
            Tuple of (title, source_identifier) for filename generation.
        """
        return metadata.title, metadata.channel

    def fetch_video_metadata(self, video_id: str) -> VideoMetadata:
        """Fetch video metadata from YouTube Data API.

        Parameters
        ----------
        video_id : str
            YouTube video identifier.

        Returns
        -------
        VideoMetadata
            Complete video metadata structure.

        Raises
        ------
        YouTubeAPIError
            If unable to fetch video metadata from YouTube API.

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> metadata = generator.fetch_video_metadata("dQw4w9WgXcQ")
        >>> metadata.channel
        "RickAstleyVEVO"
        """
        if not self._youtube_api_key:
            raise YouTubeAPIError(
                "YouTube API key not found. Set YOUTUBE_API_KEY environment variable."
            )

        try:
            logger.info(f"Fetching metadata for video: {video_id}")
            youtube = build("youtube", "v3", developerKey=self._youtube_api_key)
            request = youtube.videos().list(part="snippet", id=video_id)
            response = request.execute()

            if not response["items"]:
                raise YouTubeAPIError(f"Video not found: {video_id}")

            snippet = response["items"][0]["snippet"]

            # Clean and format the data
            metadata = VideoMetadata(
                video_id=video_id,
                title=snippet["title"],
                channel=snippet["channelTitle"],
                publish_date=snippet["publishedAt"].split("T")[0],
                description=snippet["description"],
                url=f"https://www.youtube.com/watch?v={video_id}",
            )

            logger.info(f"Successfully fetched metadata for: {metadata.title}")
            return metadata

        except HttpError as e:
            error_msg = f"YouTube API error for video {video_id}: {e}"
            logger.error(error_msg)
            raise YouTubeAPIError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error fetching metadata for {video_id}: {e}"
            logger.error(error_msg)
            raise YouTubeAPIError(error_msg) from e

    def generate_ai_content_for_video(
        self, metadata: VideoMetadata
    ) -> AIGeneratedContent:
        """Generate AI-powered filename, tags, and authors for video.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata to analyze.

        Returns
        -------
        AIGeneratedContent
            AI-generated filename, tags, and authors.

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> metadata = VideoMetadata(...)
        >>> ai_content = generator.generate_ai_content_for_video(metadata)
        >>> ai_content.filename
        "Never-Gonna-Give-You-Up-RickAstleyVEVO"
        """
        # Use the base class method with description as content preview
        return super().generate_ai_content(metadata, metadata.description)

    def construct_frontmatter_for_video(
        self, metadata: VideoMetadata, ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Construct YAML frontmatter for YouTube video Obsidian note.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content. If None, only basic metadata is included.

        Returns
        -------
        str
            YAML frontmatter string.

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> frontmatter = generator.construct_frontmatter_for_video(metadata, ai_content)
        >>> "title:" in frontmatter
        True
        """
        # Extra fields specific to YouTube videos
        extra_fields = {
            "source": "YouTube",
            "channel": metadata.channel,
            "url": metadata.url,
            "date": metadata.publish_date,
        }

        return super().construct_frontmatter(metadata, ai_content, extra_fields)

    def generate_markdown_content_for_video(
        self,
        metadata: VideoMetadata,
        transcript_content: str,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Generate complete markdown content with frontmatter and transcript.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata.
        transcript_content : str
            Formatted transcript content.
        ai_content : AIGeneratedContent, optional
            AI-generated content for enhanced metadata.

        Returns
        -------
        str
            Complete markdown content with frontmatter.

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> content = generator.generate_markdown_content_for_video(metadata, transcript, ai_content)
        >>> content.startswith("---")
        True
        """
        # Extra fields specific to YouTube videos
        extra_fields = {
            "source": "YouTube",
            "channel": metadata.channel,
            "url": metadata.url,
            "date": metadata.publish_date,
        }

        return super().generate_markdown_content(
            metadata, transcript_content, ai_content, extra_fields
        )

    def get_suggested_filename_for_video(
        self, metadata: VideoMetadata, ai_content: AIGeneratedContent | None = None
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

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> filename = generator.get_suggested_filename_for_video(metadata, ai_content)
        >>> filename.endswith(".md")
        True
        """
        if ai_content and ai_content.filename:
            return f"{ai_content.filename}.md"
        else:
            # Fallback to sanitized title + channel
            safe_title = sanitize_filename(metadata.title)
            safe_channel = sanitize_filename(metadata.channel)
            return f"{safe_title}-{safe_channel}.md"
