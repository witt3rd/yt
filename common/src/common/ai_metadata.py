"""Shared AI-powered metadata generation functionality.

This module provides base classes and utilities for generating AI-powered
metadata, filenames, tags, and frontmatter using OpenAI across different
content types (YouTube videos, web content, etc.).
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import openai
from loguru import logger

from .config import Config


@dataclass
class AIGeneratedContent:
    """AI-generated content for metadata enhancement.

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


class OpenAIError(MetadataGenerationError):
    """Raised when OpenAI API operations fail."""
    pass


class AIMetadataGenerator(ABC):
    """Base class for AI-powered metadata generation.

    Provides shared functionality for OpenAI integration and defines the interface
    that all content-specific metadata generators must implement.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> class VideoMetadataGenerator(AIMetadataGenerator):
    ...     def _get_content_context(self, metadata):
    ...         return f"Video: {metadata.title}"
    >>> generator = VideoMetadataGenerator()
    """

    def __init__(self, config: Config | None = None):
        """Initialize AI metadata generator.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        self.config: Config = config or Config()
        self._openai_api_key = os.getenv("OPENAI_API_KEY")

        # Initialize OpenAI client if API key is available
        if self._openai_api_key:
            self._openai_client = openai.OpenAI(api_key=self._openai_api_key)
        else:
            self._openai_client = None

    @abstractmethod
    def _get_content_context(self, metadata: Any) -> str:
        """Get content context string for AI prompts.

        Parameters
        ----------
        metadata : Any
            Content metadata (VideoMetadata, WebMetadata, etc.).

        Returns
        -------
        str
            Context string for AI prompts.
        """
        pass

    @abstractmethod
    def _get_filename_context(self, metadata: Any) -> tuple[str, str]:
        """Get title and source context for filename generation.

        Parameters
        ----------
        metadata : Any
            Content metadata.

        Returns
        -------
        tuple[str, str]
            Tuple of (title, source_identifier) for filename generation.
        """
        pass

    @abstractmethod
    def generate_markdown_content(
        self,
        metadata: Any,
        content: str,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Generate complete markdown content with frontmatter.

        Parameters
        ----------
        metadata : Any
            Content metadata.
        content : str
            Main content body.
        ai_content : AIGeneratedContent, optional
            AI-generated content for enhanced metadata.

        Returns
        -------
        str
            Complete markdown content with frontmatter.
        """
        pass

    @abstractmethod
    def get_suggested_filename(
        self,
        metadata: Any,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Get suggested filename for the markdown file.

        Parameters
        ----------
        metadata : Any
            Content metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content with filename suggestion.

        Returns
        -------
        str
            Suggested filename with .md extension.
        """
        pass

    @abstractmethod
    def construct_frontmatter(
        self,
        metadata: Any,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Construct YAML frontmatter for Obsidian note.

        Parameters
        ----------
        metadata : Any
            Content metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content. If None, only basic metadata is included.

        Returns
        -------
        str
            YAML frontmatter string.
        """
        pass

    def generate_ai_content(
        self,
        metadata: Any,
        content_preview: str | None = None
    ) -> AIGeneratedContent:
        """Generate AI-powered filename, tags, and authors.

        Parameters
        ----------
        metadata : Any
            Content metadata to analyze.
        content_preview : str, optional
            Content preview for enhanced AI analysis.

        Returns
        -------
        AIGeneratedContent
            AI-generated filename, tags, and authors.

        Raises
        ------
        OpenAIError
            If unable to generate AI content.
        """
        if not self._openai_client:
            raise OpenAIError(
                "OpenAI API key not found. Set OPENAI_API_KEY environment variable."
            )

        try:
            context = self._get_content_context(metadata)
            logger.info(f"Generating AI content for: {context}")

            # Generate filename
            filename = self._generate_filename(metadata)

            # Generate tags
            tags = self._generate_tags(metadata, content_preview)

            # Generate authors
            authors = self._generate_authors(metadata, content_preview)

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

    def _generate_filename(self, metadata: Any) -> str:
        """Generate a suitable filename using OpenAI.

        Parameters
        ----------
        metadata : Any
            Content metadata for filename generation.

        Returns
        -------
        str
            Generated filename without extension.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        title, source = self._get_filename_context(metadata)

        prompt = (
            f"Given content with title '{title}' from source '{source}', "
            f"suggest a suitable Markdown filename for Obsidian. Use hyphens instead "
            f"of spaces, keep it descriptive, and include the source identifier when helpful. "
            f"Example: for title 'Python Web Scraping Guide' from 'realpython.com', "
            f"use 'Python-Web-Scraping-Guide-Real-Python'. "
            f"Provide only the filename without extension."
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
        filename = sanitize_filename(filename)
        return filename

    def _generate_tags(self, metadata: Any, content_preview: str | None = None) -> list[str]:
        """Generate relevant tags using OpenAI.

        Parameters
        ----------
        metadata : Any
            Content metadata for context.
        content_preview : str, optional
            Content preview for analysis.

        Returns
        -------
        list[str]
            List of relevant tags without "#" prefixes.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        context = self._get_content_context(metadata)

        # Truncate content preview to avoid token limits
        preview = ""
        if content_preview:
            preview = content_preview[:1500] if len(content_preview) > 1500 else content_preview

        prompt = (
            f"Based on the content: {context}"
            + (f" and content preview: '{preview}'" if preview else "") +
            f", suggest relevant tags for an Obsidian note. "
            f"Provide a list of tags separated by commas. Keep tags concise and relevant. "
            f"Include technology, topic, and category tags as appropriate. "
            f"IMPORTANT: Do NOT include '#' prefixes - just the tag names themselves."
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

    def _generate_authors(self, metadata: Any, content_preview: str | None = None) -> list[str]:
        """Extract author names using OpenAI.

        Parameters
        ----------
        metadata : Any
            Content metadata that may contain author info.
        content_preview : str, optional
            Content preview for author extraction.

        Returns
        -------
        list[str]
            List of author names.
        """
        if not self._openai_client:
            raise OpenAIError("OpenAI client not initialized")

        # Start with any existing author info from metadata
        authors = []
        if hasattr(metadata, 'author') and metadata.author:
            authors.append(metadata.author)

        # Use AI to extract additional authors from content if available
        if content_preview:
            preview = content_preview[:1500] if len(content_preview) > 1500 else content_preview

            prompt = (
                f"From the content: '{preview}', extract the names of authors, "
                f"writers, or content creators. Look for bylines, author sections, or "
                f"clear attribution. Provide a list of names separated by commas. "
                f"If no clear authors are mentioned, return an empty response."
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
            if content:
                authors_text = content.strip()
                if authors_text and authors_text.lower() not in ["none", "no authors", "n/a"]:
                    ai_authors = [author.strip() for author in authors_text.split(",") if author.strip()]
                    # Add unique authors from AI analysis
                    for author in ai_authors:
                        if author not in authors:
                            authors.append(author)

        return authors

    def _construct_frontmatter_base(
        self,
        metadata: Any,
        ai_content: AIGeneratedContent | None = None,
        extra_fields: dict[str, Any] | None = None
    ) -> str:
        """Helper method to construct basic frontmatter fields.

        This provides shared frontmatter construction logic that subclasses can use.

        Parameters
        ----------
        metadata : Any
            Content metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content. If None, only basic metadata is included.
        extra_fields : dict[str, Any], optional
            Additional fields to include in frontmatter.

        Returns
        -------
        str
            YAML frontmatter string.
        """
        frontmatter_lines = ["---"]

        # Add basic fields that are common across content types
        if hasattr(metadata, 'title') and metadata.title:
            frontmatter_lines.append(f'title: "{metadata.title}"')
        elif hasattr(metadata, 'url'):
            frontmatter_lines.append('title: "Untitled"')

        # Add extra fields if provided
        if extra_fields:
            for key, value in extra_fields.items():
                if value is not None:
                    if isinstance(value, str):
                        frontmatter_lines.append(f'{key}: "{value}"')
                    else:
                        frontmatter_lines.append(f"{key}: {value}")

        # Add AI-generated authors
        if ai_content and ai_content.authors:
            authors_str = ', '.join(ai_content.authors)
            frontmatter_lines.append(f'authors: "{authors_str}"')
        elif hasattr(metadata, 'author') and metadata.author:
            frontmatter_lines.append(f'authors: "{metadata.author}"')

        # Add AI-generated tags
        if ai_content and ai_content.tags:
            # Sanitize tags to remove any "#" prefixes
            sanitized_tags = [tag.lstrip('#').strip() for tag in ai_content.tags]
            frontmatter_lines.append(f"tags: [{', '.join(sanitized_tags)}]")

        frontmatter_lines.append("---")
        return "\n".join(frontmatter_lines)

    def _get_suggested_filename_base(
        self,
        metadata: Any,
        ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Helper method for basic filename generation.

        This provides shared filename generation logic that subclasses can use.

        Parameters
        ----------
        metadata : Any
            Content metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content with filename suggestion.

        Returns
        -------
        str
            Suggested filename with .md extension.
        """
        if ai_content and ai_content.filename:
            return f"{ai_content.filename}.md"
        else:
            # Fallback to basic filename generation
            title, source = self._get_filename_context(metadata)
            safe_title = sanitize_filename(title)
            safe_source = sanitize_filename(source)
            return f"{safe_title}-{safe_source}.md"


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to ensure it's valid for file systems.

    Parameters
    ----------
    filename : str
        Raw filename.

    Returns
    -------
    str
        Sanitized filename.

    Examples
    --------
    >>> sanitize_filename("My File: Name?")
    "My-File-Name"
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
