"""Web content extraction utilities using Firecrawl.

This package provides functionality to extract content from web pages
using the Firecrawl API, with support for dynamic content rendering,
multiple output formats, and AI-powered metadata generation for
enhanced markdown output with intelligent filenames and frontmatter.
"""

from .scraper import WebScraper, ScrapedContent, FirecrawlAPIError
from .metadata import (
    WebMetadataGenerator,
    WebMetadata,
)

__version__ = "0.1.0"
__all__ = [
    "WebScraper",
    "WebMetadataGenerator",
    "WebMetadata",
    "ScrapedContent",
    "FirecrawlAPIError",
]
