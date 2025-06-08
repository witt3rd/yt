"""Web content extraction functionality using Firecrawl.

This module provides the core functionality for extracting content from
web pages using the Firecrawl API, with support for dynamic content
rendering, multiple output formats, and robust error handling.
"""

import os
import re
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass
from typing import Any

from firecrawl import FirecrawlApp
import validators
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    after_log,
)

from common.config import Config


@dataclass
class ScrapedContent:
    """Container for scraped web content and metadata.

    Parameters
    ----------
    url : str
        The original URL that was scraped.
    markdown : str
        Content converted to markdown format.
    html : str, optional
        Raw HTML content if requested.
    metadata : dict[str, Any]
        Firecrawl metadata including title, description, etc.
    screenshot : str, optional
        Base64 encoded screenshot if requested.
    status_code : int
        HTTP status code from the scraping request.
    scrape_date : str
        ISO format date when content was scraped.
    word_count : int
        Approximate word count of the markdown content.
    """
    url: str
    markdown: str
    html: str | None
    metadata: dict[str, Any]
    screenshot: str | None
    status_code: int
    scrape_date: str
    word_count: int


class FirecrawlAPIError(Exception):
    """Raised when Firecrawl API operations fail."""
    pass


def _should_retry_scraping(exception: BaseException) -> bool:
    """Determine if web scraping should be retried.

    Parameters
    ----------
    exception : BaseException
        The exception that occurred during scraping.

    Returns
    -------
    bool
        True if the operation should be retried, False otherwise.

    Notes
    -----
    This function identifies transient errors that may resolve with retry:
    - Network connection errors
    - Timeout errors
    - Server errors (5xx responses)
    - Rate limiting (429)

    Does not retry for permanent errors like:
    - Invalid URLs
    - Not found errors (404)
    - Forbidden errors (403)
    - Invalid API keys
    """
    error_msg = str(exception).lower()

    # Don't retry permanent errors
    permanent_error_indicators = [
        "invalid url",
        "not found",
        "404",
        "403",
        "forbidden",
        "unauthorized",
        "invalid api key",
        "api key not found",
    ]

    if any(indicator in error_msg for indicator in permanent_error_indicators):
        return False

    # Retry on transient errors
    transient_error_indicators = [
        "connection error",
        "timeout",
        "network",
        "503",  # Service unavailable
        "502",  # Bad gateway
        "500",  # Internal server error
        "429",  # Rate limiting
        "rate limit",
        "quota exceeded",
    ]

    if any(indicator in error_msg for indicator in transient_error_indicators):
        return True

    return False


def _log_retry_attempt(retry_state) -> None:
    """Log retry attempts with context information.

    Parameters
    ----------
    retry_state : RetryCallState
        The current retry state from tenacity.
    """
    if retry_state.attempt_number > 1:
        logger.info(
            f"Retrying web scraping (attempt {retry_state.attempt_number}) "
            f"after {retry_state.next_action}: {retry_state.outcome.exception()}"
        )


class WebScraper:
    """Extract content from web pages using Firecrawl.

    Provides methods to scrape web content with support for dynamic
    JavaScript rendering, multiple output formats, anti-bot mechanisms,
    and structured output.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> scraper = WebScraper()
    >>> content = scraper.scrape_content("https://example.com")
    >>> len(content.markdown)
    1234
    """

    def __init__(self, config: Config | None = None):
        """Initialize web scraper.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.

        Raises
        ------
        FirecrawlAPIError
            If Firecrawl API key is not found.
        """
        self.config: Config = config or Config()
        self._api_key = os.getenv("FIRECRAWL_API_KEY")

        if not self._api_key:
            raise FirecrawlAPIError(
                "Firecrawl API key not found. Set FIRECRAWL_API_KEY environment variable."
            )

        self._firecrawl = FirecrawlApp(api_key=self._api_key)

    def validate_url(self, url: str) -> str:
        """Validate and normalize URL.

        Parameters
        ----------
        url : str
            URL to validate and normalize.

        Returns
        -------
        str
            Validated and normalized URL.

        Raises
        ------
        ValueError
            If URL is invalid or malformed.

        Examples
        --------
        >>> scraper = WebScraper()
        >>> scraper.validate_url("https://example.com")
        'https://example.com'
        >>> scraper.validate_url("example.com")
        'https://example.com'
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url = url.strip()

        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Validate URL format
        if not validators.url(url):
            raise ValueError(f"Invalid URL format: {url}")

        # Parse URL to ensure it's well-formed
        try:
            parsed = urlparse(url)
            if not parsed.netloc:
                raise ValueError(f"Invalid URL - no domain found: {url}")
        except Exception as e:
            raise ValueError(f"Failed to parse URL: {url}") from e

        return url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=5, max=30),
        retry=retry_if_exception(_should_retry_scraping),
        after=_log_retry_attempt,
    )
    def scrape_content(
        self,
        url: str,
        formats: list[str] | None = None,
        only_main_content: bool = True,
        wait_for: int | None = None,
        timeout: int | None = None,
        include_screenshot: bool = False,
        include_links: bool = False,
        remove_base64_images: bool = True,
    ) -> ScrapedContent:
        """Scrape content from a web page.

        Parameters
        ----------
        url : str
            URL to scrape content from.
        formats : list[str], optional
            Content formats to extract. Options: ['markdown', 'html', 'rawHtml'].
            Defaults to ['markdown'].
        only_main_content : bool, default True
            Extract only main content, filtering out navigation, footers, etc.
        wait_for : int, optional
            Milliseconds to wait for dynamic content to load.
        timeout : int, optional
            Maximum time in seconds to wait for the page to load.
        include_screenshot : bool, default False
            Whether to include a screenshot in the response.
        include_links : bool, default False
            Whether to include extracted links in the response.
        remove_base64_images : bool, default True
            Whether to remove base64 encoded images from output.

        Returns
        -------
        ScrapedContent
            Scraped content with metadata and optional screenshot.

        Raises
        ------
        FirecrawlAPIError
            If scraping fails or API returns an error.
        ValueError
            If URL is invalid.

        Examples
        --------
        >>> scraper = WebScraper()
        >>> content = scraper.scrape_content("https://example.com")
        >>> content.status_code
        200
        >>> "Welcome" in content.markdown
        True
        """
        try:
            # Validate URL
            validated_url = self.validate_url(url)
            logger.info(f"Scraping content from: {validated_url}")

            # Prepare scraping parameters
            if formats is None:
                formats = ['markdown']

            # Add screenshot format if requested
            if include_screenshot:
                if 'screenshot' not in formats:
                    formats.append('screenshot')

            # Add links format if requested
            if include_links:
                if 'links' not in formats:
                    formats.append('links')

            # Perform scraping using the correct Firecrawl SDK format
            result = self._firecrawl.scrape_url(validated_url, formats=formats)

            # Check if scraping was successful
            if not result or not getattr(result, 'success', False):
                error_msg = getattr(result, 'error', 'Unknown error') if result else 'No response'
                raise FirecrawlAPIError(f"Firecrawl API error for {validated_url}: {error_msg}")

            # Extract content directly from the ScrapeResponse object
            markdown_content = getattr(result, 'markdown', '')
            html_content = getattr(result, 'html', '') or getattr(result, 'rawHtml', '')
            screenshot_data = getattr(result, 'screenshot', None)
            metadata = getattr(result, 'metadata', {})

            # Debug logging
            logger.debug(f"Extracted markdown length: {len(markdown_content)}")
            logger.debug(f"Extracted HTML length: {len(html_content) if html_content else 0}")
            logger.debug(f"Metadata: {metadata}")

            # Get status code
            status_code = metadata.get('statusCode', 200) if hasattr(metadata, 'get') else getattr(metadata, 'statusCode', 200)

            # Calculate word count
            word_count = len(markdown_content.split()) if markdown_content else 0

            # Create scraped content object
            scraped_content = ScrapedContent(
                url=validated_url,
                markdown=markdown_content,
                html=html_content,
                metadata=metadata,
                screenshot=screenshot_data,
                status_code=status_code,
                scrape_date=datetime.now().isoformat(),
                word_count=word_count,
            )

            logger.info(f"Successfully scraped content: {word_count} words, status {status_code}")

            # Check content length limit
            if word_count > getattr(self.config, 'max_content_length', 500000):
                logger.warning(
                    f"Content length ({word_count} words) exceeds recommended limit "
                    f"({getattr(self.config, 'max_content_length', 500000)} words)"
                )

            return scraped_content

        except ValueError:
            # URL validation errors - don't retry
            raise
        except Exception as e:
            error_msg = f"Failed to scrape content from {url}: {e}"
            logger.error(error_msg)
            raise FirecrawlAPIError(error_msg) from e

    def content_to_text(self, content: ScrapedContent) -> str:
        """Convert scraped content to plain text.

        Parameters
        ----------
        content : ScrapedContent
            Scraped content object.

        Returns
        -------
        str
            Plain text content extracted from markdown.

        Examples
        --------
        >>> scraper = WebScraper()
        >>> content = scraper.scrape_content("https://example.com")
        >>> text = scraper.content_to_text(content)
        >>> len(text) > 0
        True
        """
        if not content.markdown:
            return ""

        # Simple markdown to text conversion
        # Remove markdown formatting
        text = content.markdown

        # Remove headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)

        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove bold/italic formatting
        text = re.sub(r'\*+([^*]+)\*+', r'\1', text)
        text = re.sub(r'_+([^_]+)_+', r'\1', text)

        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()

        return text

    def content_to_markdown(self, content: ScrapedContent) -> str:
        """Get markdown content from scraped content.

        Parameters
        ----------
        content : ScrapedContent
            Scraped content object.

        Returns
        -------
        str
            Markdown formatted content.

        Examples
        --------
        >>> scraper = WebScraper()
        >>> content = scraper.scrape_content("https://example.com")
        >>> markdown = scraper.content_to_markdown(content)
        >>> len(markdown) > 0
        True
        """
        return content.markdown or ""
