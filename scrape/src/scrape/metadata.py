"""Web metadata generation for enhanced scraping output.

This module provides functionality to extract metadata from scraped web content
and generate AI-powered filenames, tags, and frontmatter for Obsidian-compatible
markdown output.
"""

import re
from dataclasses import dataclass
from urllib.parse import urlparse
from typing import override

from loguru import logger

from common.config import Config
from common.ai_metadata import (
    AIMetadataGenerator,
    AIGeneratedContent,
    MetadataGenerationError,
    sanitize_filename,
)
from .scraper import ScrapedContent


@dataclass
class WebMetadata:
    """Web content metadata structure.

    Parameters
    ----------
    url : str
        Original URL of the scraped content.
    title : str, optional
        Page title extracted from content.
    description : str, optional
        Page description or meta description.
    author : str, optional
        Author name extracted from content.
    publish_date : str, optional
        Publication date in YYYY-MM-DD format if available.
    scrape_date : str
        Date when content was scraped in ISO format.
    content_type : str
        Type of content (article, blog, documentation, etc.).
    word_count : int
        Word count of the content.
    domain : str
        Domain name of the source website.
    """

    url: str
    title: str | None
    description: str | None
    author: str | None
    publish_date: str | None
    scrape_date: str
    content_type: str
    word_count: int
    domain: str


class OpenAIError(MetadataGenerationError):
    """Raised when OpenAI API operations fail."""

    pass


class WebMetadataGenerator(AIMetadataGenerator):
    """Generate web content metadata and AI-powered enhancements.

    Provides methods to extract metadata from scraped content and generate
    AI-powered filenames, tags, and authors using OpenAI for enhanced
    markdown output with Obsidian-compatible frontmatter.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> generator = WebMetadataGenerator()
    >>> content = ScrapedContent(...)
    >>> metadata = generator.extract_web_metadata(content)
    >>> metadata.title
    "Introduction to Web Scraping"
    """

    def __init__(self, config: Config | None = None):
        """Initialize web metadata generator.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        super().__init__(config)

    @override
    def _get_content_context(self, metadata: WebMetadata) -> str:
        """Get content context string for AI prompts.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata.

        Returns
        -------
        str
            Context string for AI prompts.
        """
        return (
            f"Web page '{metadata.title or 'Untitled'}' from domain '{metadata.domain}'"
        )

    @override
    def _get_filename_context(self, metadata: WebMetadata) -> tuple[str, str]:
        """Get title and source context for filename generation.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata.

        Returns
        -------
        tuple[str, str]
            Tuple of (title, source_identifier) for filename generation.
        """
        return metadata.title or "Untitled", metadata.domain

    def extract_web_metadata(self, content: ScrapedContent) -> WebMetadata:
        """Extract metadata from scraped web content.

        Parameters
        ----------
        content : ScrapedContent
            Scraped content object containing content and metadata.

        Returns
        -------
        WebMetadata
            Extracted web metadata structure.

        Examples
        --------
        >>> generator = WebMetadataGenerator()
        >>> content = ScrapedContent(...)
        >>> metadata = generator.extract_web_metadata(content)
        >>> metadata.domain
        "example.com"
        """
        try:
            logger.info(f"Extracting metadata from: {content.url}")

            # Extract domain from URL
            parsed_url = urlparse(content.url)
            domain = parsed_url.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]

            # Extract title from Firecrawl metadata or content
            title = None
            if content.metadata:
                title = content.metadata.get("title")
                if not title:
                    title = content.metadata.get("ogTitle")

            # If no title from metadata, try to extract from markdown
            if not title and content.markdown:
                # Look for first H1 heading
                h1_match = re.search(r"^#\s+(.+)", content.markdown, re.MULTILINE)
                if h1_match:
                    title = h1_match.group(1).strip()

            # Extract description
            description = None
            if content.metadata:
                description = content.metadata.get("description")
                if not description:
                    description = content.metadata.get("ogDescription")

            # Extract author from metadata
            author = None
            if content.metadata:
                author = content.metadata.get("author")

            # Extract publish date
            publish_date = None
            if content.metadata:
                publish_date = content.metadata.get("publishedTime")
                if publish_date and "T" in publish_date:
                    publish_date = publish_date.split("T")[0]  # Keep only date part

            # Determine content type based on URL patterns and content
            content_type = self._determine_content_type(content.url, content.markdown)

            metadata = WebMetadata(
                url=content.url,
                title=title,
                description=description,
                author=author,
                publish_date=publish_date,
                scrape_date=content.scrape_date,
                content_type=content_type,
                word_count=content.word_count,
                domain=domain,
            )

            logger.info(f"Extracted metadata: title='{title}', type='{content_type}'")
            return metadata

        except Exception as e:
            error_msg = f"Failed to extract metadata from {content.url}: {e}"
            logger.error(error_msg)
            raise MetadataGenerationError(error_msg) from e

    def _determine_content_type(self, url: str, content: str) -> str:
        """Determine content type based on URL patterns and content.

        Parameters
        ----------
        url : str
            URL of the content.
        content : str
            Content text for analysis.

        Returns
        -------
        str
            Content type classification.
        """
        url_lower = url.lower()

        # Check URL patterns
        if any(pattern in url_lower for pattern in ["/blog/", "/news/", "/article/"]):
            return "article"
        elif any(
            pattern in url_lower for pattern in ["/docs/", "/documentation/", "/guide/"]
        ):
            return "documentation"
        elif any(
            pattern in url_lower for pattern in ["/tutorial/", "/how-to/", "/learn/"]
        ):
            return "tutorial"
        elif any(
            pattern in url_lower for pattern in ["/about/", "/contact/", "/company/"]
        ):
            return "page"
        elif any(
            pattern in url_lower for pattern in ["/product/", "/service/", "/pricing/"]
        ):
            return "product"

        # Analyze content patterns
        if content:
            content_lower = content.lower()
            if any(
                indicator in content_lower
                for indicator in ["step 1", "tutorial", "how to"]
            ):
                return "tutorial"
            elif any(
                indicator in content_lower
                for indicator in ["api", "function", "class", "method"]
            ):
                return "documentation"
            elif len(content.split()) > 500:  # Longer content likely article
                return "article"

        return "page"  # Default fallback

    def generate_ai_content_for_web(
        self, metadata: WebMetadata, content_preview: str
    ) -> AIGeneratedContent:
        """Generate AI-powered filename, tags, and authors for web content.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata to analyze.
        content_preview : str
            First portion of content for AI analysis.

        Returns
        -------
        AIGeneratedContent
            AI-generated filename, tags, and authors.

        Examples
        --------
        >>> generator = WebMetadataGenerator()
        >>> metadata = WebMetadata(...)
        >>> ai_content = generator.generate_ai_content_for_web(metadata, preview)
        >>> ai_content.filename
        "Web-Scraping-Python-Guide-Real-Python"
        """
        # Use the base class method
        return super().generate_ai_content(metadata, content_preview)

    def construct_frontmatter_for_web(
        self, metadata: WebMetadata, ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Construct YAML frontmatter for web content Obsidian note.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content. If None, only basic metadata is included.

        Returns
        -------
        str
            YAML frontmatter string.

        Examples
        --------
        >>> generator = WebMetadataGenerator()
        >>> frontmatter = generator.construct_frontmatter_for_web(metadata, ai_content)
        >>> "title:" in frontmatter
        True
        """
        # Extra fields specific to web content
        extra_fields = {
            "source": "web",
            "url": metadata.url,
            "domain": metadata.domain,
            "scrape_date": metadata.scrape_date.split("T")[0],
            "word_count": metadata.word_count,
            "content_type": metadata.content_type,
        }

        if metadata.publish_date:
            extra_fields["publish_date"] = metadata.publish_date

        return super().construct_frontmatter(metadata, ai_content, extra_fields)

    def generate_markdown_content_for_web(
        self,
        metadata: WebMetadata,
        content: str,
        ai_content: AIGeneratedContent | None = None,
    ) -> str:
        """Generate complete markdown content with frontmatter.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata.
        content : str
            Scraped content.
        ai_content : AIGeneratedContent, optional
            AI-generated content for enhanced metadata.

        Returns
        -------
        str
            Complete markdown content with frontmatter.

        Examples
        --------
        >>> generator = WebMetadataGenerator()
        >>> markdown = generator.generate_markdown_content_for_web(metadata, content, ai_content)
        >>> markdown.startswith("---")
        True
        """
        # Extra fields specific to web content
        extra_fields = {
            "source": "web",
            "url": metadata.url,
            "domain": metadata.domain,
            "scrape_date": metadata.scrape_date.split("T")[0],
            "word_count": metadata.word_count,
            "content_type": metadata.content_type,
        }

        if metadata.publish_date:
            extra_fields["publish_date"] = metadata.publish_date

        return super().generate_markdown_content(
            metadata, content, ai_content, extra_fields
        )

    def get_suggested_filename_for_web(
        self, metadata: WebMetadata, ai_content: AIGeneratedContent | None = None
    ) -> str:
        """Get suggested filename for the markdown file.

        Parameters
        ----------
        metadata : WebMetadata
            Web metadata.
        ai_content : AIGeneratedContent, optional
            AI-generated content with filename suggestion.

        Returns
        -------
        str
            Suggested filename with .md extension.

        Examples
        --------
        >>> generator = WebMetadataGenerator()
        >>> filename = generator.get_suggested_filename_for_web(metadata, ai_content)
        >>> filename.endswith(".md")
        True
        """
        if ai_content and ai_content.filename:
            return f"{ai_content.filename}.md"
        else:
            # Fallback to sanitized title + domain
            safe_title = sanitize_filename(metadata.title or "Untitled")
            safe_domain = sanitize_filename(metadata.domain)
            return f"{safe_title}-{safe_domain}.md"
