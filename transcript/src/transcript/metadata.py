"""YouTube metadata generation for enhanced transcript output.

This module provides functionality to fetch YouTube video metadata using the
YouTube Data API and generate AI-powered filenames, tags, and frontmatter
for Obsidian-compatible markdown output.
"""

import os
import re
from dataclasses import dataclass

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import openai
from loguru import logger

from common.config import Config


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


@dataclass
class AIGeneratedContent:
    """AI-generated content for video metadata.

    Parameters
    ----------
    filename : str
        Suggested filename without extension.
    tags : list[str]
        List of relevant tags.
    authors : list[str]
        List of extracted author names.
    """
    filename: str
    tags: list[str]
    authors: list[str]


class MetadataGenerationError(Exception):
    """Base exception for metadata generation errors."""
    pass


class YouTubeAPIError(MetadataGenerationError):
    """Raised when YouTube Data API operations fail."""
    pass


class OpenAIError(MetadataGenerationError):
    """Raised when OpenAI API operations fail."""
    pass


class MetadataGenerator:
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
        self.config: Config = config or Config()
        self._youtube_api_key = os.getenv("YOUTUBE_API_KEY")
        self._openai_api_key = os.getenv("OPENAI_API_KEY")

        # Initialize OpenAI client if API key is available
        if self._openai_api_key:
            self._openai_client = openai.OpenAI(api_key=self._openai_api_key)
        else:
            self._openai_client = None

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
                url=f"https://www.youtube.com/watch?v={video_id}"
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

    def generate_ai_content(self, metadata: VideoMetadata) -> AIGeneratedContent:
        """Generate AI-powered filename, tags, and authors.

        Parameters
        ----------
        metadata : VideoMetadata
            Video metadata to analyze.

        Returns
        -------
        AIGeneratedContent
            AI-generated filename, tags, and authors.

        Raises
        ------
        OpenAIError
            If unable to generate AI content.

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> metadata = VideoMetadata(...)
        >>> ai_content = generator.generate_ai_content(metadata)
        >>> ai_content.filename
        "Never-Gonna-Give-You-Up-RickAstleyVEVO"
        """
        if not self._openai_client:
            raise OpenAIError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        try:
            logger.info(f"Generating AI content for: {metadata.title}")

            # Generate filename
            filename = self._generate_filename(metadata.title, metadata.channel)

            # Generate tags
            tags = self._generate_tags(metadata.title, metadata.description)

            # Generate authors
            authors = self._generate_authors(metadata.description)

            ai_content = AIGeneratedContent(
                filename=filename,
                tags=tags,
                authors=authors
            )

            logger.info(f"Generated AI content with filename: {filename}")
            return ai_content

        except Exception as e:
            error_msg = f"Failed to generate AI content: {e}"
            logger.error(error_msg)
            raise OpenAIError(error_msg) from e

    def _generate_filename(self, title: str, channel: str) -> str:
        """Generate a suitable filename using OpenAI.

        Parameters
        ----------
        title : str
            Video title.
        channel : str
            Channel name.

        Returns
        -------
        str
            Generated filename without extension.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        prompt = (
            f"Given the YouTube video title '{title}' from channel '{channel}', "
            "suggest a suitable Markdown filename for Obsidian. Use hyphens instead "
            "of spaces, keep it descriptive, and include the channel name if not in "
            "the title. Example: for title 'The Collapse of AI Reasoning (by Apple)' "
            "from 'Discover AI', use 'The-Collapse-of-AI-Reasoning-Discover-AI'. "
            "Provide only the filename without extension."
        )

        response = self._openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )

        content = response.choices[0].message.content
        if not content:
            raise OpenAIError("OpenAI returned empty content for filename generation")

        filename = content.strip()
        # Clean the filename to ensure it's valid
        filename = self._sanitize_filename(filename)
        return filename

    def _generate_tags(self, title: str, description: str) -> list[str]:
        """Generate relevant tags using OpenAI.

        Parameters
        ----------
        title : str
            Video title.
        description : str
            Video description.

        Returns
        -------
        list[str]
            List of relevant tags without "#" prefixes.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        # Truncate description to avoid token limits
        description_excerpt = description[:1000] if len(description) > 1000 else description

        prompt = (
            f"Based on the YouTube video title '{title}' and description "
            f"'{description_excerpt}', suggest relevant tags for an Obsidian note. "
            "Provide a list of tags separated by commas. Keep tags concise and relevant. "
            "IMPORTANT: Do NOT include '#' prefixes - just the tag names themselves."
        )

        response = self._openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=150
        )

        content = response.choices[0].message.content
        if not content:
            raise OpenAIError("OpenAI returned empty content for tag generation")

        tags_text = content.strip()
        # Split by comma and sanitize each tag to remove any "#" prefixes
        tags = [tag.strip().lstrip('#').strip() for tag in tags_text.split(",")
                if tag.strip().lstrip('#').strip()]
        return tags

    def _generate_authors(self, description: str) -> list[str]:
        """Extract author names from video description using OpenAI.

        Parameters
        ----------
        description : str
            Video description text.

        Returns
        -------
        list[str]
            List of author names.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        # Truncate description to avoid token limits
        description_excerpt = description[:1500] if len(description) > 1500 else description

        prompt = (
            f"From the YouTube video description: '{description_excerpt}', "
            "extract the names of authors or presenters. Provide a list of names "
            "separated by commas. If no clear authors are mentioned, return an empty response."
        )

        response = self._openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=100
        )

        content = response.choices[0].message.content
        if not content:
            return []

        authors_text = content.strip()
        if not authors_text or authors_text.lower() in ["none", "no authors", "n/a"]:
            return []

        authors = [author.strip() for author in authors_text.split(",") if author.strip()]
        return authors

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to ensure it's valid for file systems.

        Parameters
        ----------
        filename : str
            Raw filename.

        Returns
        -------
        str
            Sanitized filename.
        """
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', "", filename)
        # Replace multiple spaces/hyphens with single hyphens
        filename = re.sub(r'[-\s]+', "-", filename)
        # Remove leading/trailing hyphens
        filename = filename.strip("-")
        # Limit length
        if len(filename) > 200:
            filename = filename[:200].rstrip("-")

        return filename

    def construct_frontmatter(
        self,
        metadata: VideoMetadata,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Construct YAML frontmatter for Obsidian note.

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
        >>> frontmatter = generator.construct_frontmatter(metadata, ai_content)
        >>> "title:" in frontmatter
        True
        """
        frontmatter_lines = [
            "---",
            f"title: {metadata.title}",
            "source: YouTube",
            f"channel: {metadata.channel}",
            f"url: {metadata.url}",
            f"date: {metadata.publish_date}",
        ]

        if ai_content and ai_content.authors:
            frontmatter_lines.append(f"authors: {', '.join(ai_content.authors)}")

        if ai_content and ai_content.tags:
            # Sanitize tags to remove any "#" prefixes that break markdown rendering
            sanitized_tags = [tag.lstrip('#').strip() for tag in ai_content.tags]
            frontmatter_lines.append(f"tags: [{', '.join(sanitized_tags)}]")

        frontmatter_lines.append("---")
        return "\n".join(frontmatter_lines)

    def generate_markdown_content(
        self,
        metadata: VideoMetadata,
        transcript_content: str,
        ai_content: AIGeneratedContent | None = None
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
        >>> content = generator.generate_markdown_content(metadata, transcript, ai_content)
        >>> content.startswith("---")
        True
        """
        frontmatter = self.construct_frontmatter(metadata, ai_content)
        return f"{frontmatter}\n\n{transcript_content}"

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

        Examples
        --------
        >>> generator = MetadataGenerator()
        >>> filename = generator.get_suggested_filename(metadata, ai_content)
        >>> filename.endswith(".md")
        True
        """
        if ai_content and ai_content.filename:
            return f"{ai_content.filename}.md"
        else:
            # Fallback to sanitized title + channel
            safe_title = self._sanitize_filename(metadata.title)
            safe_channel = self._sanitize_filename(metadata.channel)
            return f"{safe_title}-{safe_channel}.md"
