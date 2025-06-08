"""PDF to markdown conversion functionality using PyMuPDF with Marker fallback.

This module provides the core functionality for converting PDF documents
to markdown format using PyMuPDF (fitz) as the primary conversion method with
Marker library as fallback, with support for downloading PDFs from URLs,
arXiv papers, and robust error handling.
"""

import re
import tempfile
from datetime import datetime
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import validators
from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
)

from common.config import Config
from common.url_utils import is_remote_pdf_url


@dataclass
class ConvertedContent:
    """Container for converted PDF content and metadata.

    Parameters
    ----------
    url : str
        The original URL or file path that was processed.
    markdown : str
        Content converted to markdown format.
    metadata : dict[str, Any]
        Marker metadata including title, page count, etc.
    conversion_date : str
        ISO format date when content was converted.
    word_count : int
        Approximate word count of the markdown content.
    source_type : str
        Type of source: 'url', 'arxiv', or 'file'.
    """

    url: str
    markdown: str
    metadata: dict[str, Any]
    conversion_date: str
    word_count: int
    source_type: str


class PdfConversionError(Exception):
    """Raised when PDF conversion operations fail."""

    pass


class PdfDownloadError(PdfConversionError):
    """Raised when PDF download fails."""

    pass


def _should_retry_conversion(exception: BaseException) -> bool:
    """Determine if PDF conversion should be retried.

    Parameters
    ----------
    exception : BaseException
        The exception that occurred during conversion.

    Returns
    -------
    bool
        True if the operation should be retried, False otherwise.

    Notes
    -----
    This function identifies transient errors that may resolve with retry:
    - Network connection errors
    - Temporary file system errors
    - Memory pressure errors

    Does not retry for permanent errors like:
    - Invalid PDF format
    - Corrupted files
    - Missing dependencies
    """
    error_msg = str(exception).lower()

    # Don't retry permanent errors
    permanent_error_indicators = [
        "invalid pdf",
        "corrupted",
        "not a pdf",
        "permission denied",
        "no such file",
        "invalid format",
    ]

    if any(indicator in error_msg for indicator in permanent_error_indicators):
        return False

    # Retry on transient errors
    transient_error_indicators = [
        "connection error",
        "timeout",
        "network",
        "temporary failure",
        "memory",
        "disk space",
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
            f"Retrying PDF conversion (attempt {retry_state.attempt_number}) "
            f"after {retry_state.next_action}: {retry_state.outcome.exception()}"
        )


class PdfConverter:
    """Convert PDF documents to markdown using PyMuPDF with Marker fallback.

    Provides methods to convert local PDF files and download/convert
    PDFs from URLs with support for arXiv papers, dynamic content,
    and structured output. Uses PyMuPDF (fitz) as the primary conversion method
    for speed and reliability, with Marker as fallback for enhanced quality.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> converter = PdfConverter()
    >>> content = converter.convert_pdf("paper.pdf")
    >>> len(content.markdown)
    1234
    """

    def __init__(self, config: Config | None = None):
        """Initialize PDF converter.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        self.config: Config = config or Config()

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
        >>> converter = PdfConverter()
        >>> converter.validate_url("https://arxiv.org/pdf/2506.05296")
        'https://arxiv.org/pdf/2506.05296.pdf'
        """
        if not url or not url.strip():
            raise ValueError("URL cannot be empty")

        url = url.strip()

        # Add protocol if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        # Handle arXiv URLs - ensure .pdf extension
        if "arxiv.org/pdf/" in url and not url.endswith(".pdf"):
            url = f"{url}.pdf"

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

    def is_pdf_url(self, url: str) -> bool:
        """Check if URL points to a PDF document.

        Uses intelligent content-type detection via HTTP HEAD request
        instead of simple pattern matching.

        Parameters
        ----------
        url : str
            URL to check.

        Returns
        -------
        bool
            True if URL points to a PDF document, False otherwise.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> converter.is_pdf_url("https://example.com/paper.pdf")
        True
        >>> converter.is_pdf_url("https://arxiv.org/pdf/2506.05296")
        True
        """
        return is_remote_pdf_url(url)

    def determine_source_type(self, source: str) -> str:
        """Determine the type of PDF source.

        Parameters
        ----------
        source : str
            Source path or URL.

        Returns
        -------
        str
            Source type: 'file', 'arxiv', or 'url'.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> converter.determine_source_type("paper.pdf")
        'file'
        >>> converter.determine_source_type("https://arxiv.org/pdf/2506.05296")
        'arxiv'
        """
        if not source.startswith(("http://", "https://")):
            return "file"
        elif "arxiv.org/pdf/" in source.lower():
            return "arxiv"
        else:
            return "url"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, PdfDownloadError)),
        after=_log_retry_attempt,
    )
    def download_pdf(self, url: str) -> bytes:
        """Download PDF from URL.

        Parameters
        ----------
        url : str
            URL of the PDF to download.

        Returns
        -------
        bytes
            PDF content as bytes.

        Raises
        ------
        PdfDownloadError
            If download fails.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> pdf_data = converter.download_pdf("https://example.com/paper.pdf")
        >>> len(pdf_data) > 0
        True
        """
        try:
            logger.info(f"Downloading PDF from: {url}")

            # Set headers to mimic a browser request
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                ),
                "Accept": "application/pdf,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Verify content is actually a PDF
            content_type = response.headers.get("content-type", "").lower()
            if "pdf" not in content_type and not url.endswith(".pdf"):
                # Check PDF magic bytes
                if not response.content.startswith(b"%PDF"):
                    raise PdfDownloadError(
                        f"Downloaded content is not a PDF: {content_type}"
                    )

            logger.info(f"Successfully downloaded PDF: {len(response.content)} bytes")
            return response.content

        except requests.RequestException as e:
            error_msg = f"Failed to download PDF from {url}: {e}"
            logger.error(error_msg)
            raise PdfDownloadError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error downloading PDF from {url}: {e}"
            logger.error(error_msg)
            raise PdfDownloadError(error_msg) from e

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=5),
        retry=retry_if_exception(_should_retry_conversion),
        after=_log_retry_attempt,
    )
    def convert_pdf_with_pymupdf(
        self, pdf_path: Path, max_pages: int | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Convert PDF to markdown using PyMuPDF (fitz).

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.
        max_pages : int, optional
            Maximum number of pages to process.

        Returns
        -------
        tuple[str, dict[str, Any]]
            Tuple of (markdown_content, metadata).

        Raises
        ------
        PdfConversionError
            If conversion fails.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> markdown, metadata = converter.convert_pdf_with_pymupdf(Path("paper.pdf"))
        >>> len(markdown) > 0
        True
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise PdfConversionError(
                "PyMuPDF not available. Install with: uv add pymupdf"
            )

        try:
            logger.info(f"Converting PDF with PyMuPDF: {pdf_path}")

            # Open PDF document
            doc = fitz.open(str(pdf_path))

            # Determine page range
            total_pages = len(doc)
            if max_pages:
                end_page = min(max_pages, total_pages)
                logger.info(f"Processing {end_page} of {total_pages} pages")
            else:
                end_page = total_pages
                logger.info(f"Processing all {total_pages} pages")

            # Extract text from pages
            text_blocks = []
            for page_num in range(end_page):
                page = doc[page_num]

                # Extract text with layout preservation
                text = page.get_text("text")

                if text.strip():  # Only add non-empty pages
                    # Clean up the text
                    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)  # Normalize whitespace
                    text = text.strip()

                    if text:
                        text_blocks.append(f"# Page {page_num + 1}\n\n{text}")

            doc.close()

            # Combine all text blocks
            if text_blocks:
                markdown_content = "\n\n---\n\n".join(text_blocks)
            else:
                markdown_content = "No readable text found in PDF."

            # Create metadata
            metadata = {
                "conversion_method": "pymupdf",
                "pages": end_page,
                "total_pages": total_pages,
            }

            logger.info(f"Successfully converted PDF with PyMuPDF: {len(markdown_content)} chars from {end_page} pages")
            return markdown_content, metadata

        except Exception as e:
            error_msg = f"Failed to convert PDF with PyMuPDF: {e}"
            logger.error(error_msg)
            raise PdfConversionError(error_msg) from e

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=5, max=15),
        retry=retry_if_exception(_should_retry_conversion),
        after=_log_retry_attempt,
    )
    def convert_pdf_with_marker(
        self, pdf_path: Path, max_pages: int | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Convert PDF to markdown using Marker CLI.

        Parameters
        ----------
        pdf_path : Path
            Path to the PDF file.
        max_pages : int, optional
            Maximum number of pages to process.

        Returns
        -------
        tuple[str, dict[str, Any]]
            Tuple of (markdown_content, metadata).

        Raises
        ------
        PdfConversionError
            If conversion fails.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> markdown, metadata = converter.convert_pdf_with_marker(Path("paper.pdf"))
        >>> len(markdown) > 0
        True
        """
        import subprocess
        import shutil

        temp_input_dir = None
        temp_output_dir = None

        try:
            logger.info(f"Converting PDF with Marker CLI: {pdf_path}")

            # Create temporary directories for marker CLI
            temp_input_dir = tempfile.mkdtemp(prefix="marker_input_")
            temp_output_dir = tempfile.mkdtemp(prefix="marker_output_")

            # Copy PDF to input directory
            temp_pdf_path = Path(temp_input_dir) / pdf_path.name
            shutil.copy2(pdf_path, temp_pdf_path)

            # Build marker command
            marker_cmd = [
                "marker",
                str(temp_input_dir),
                "--output_format",
                "markdown",
                "--output_dir",
                str(temp_output_dir),
                "--disable_multiprocessing",  # Simpler processing
            ]

            # Add page range if specified
            if max_pages:
                marker_cmd.extend(["--page_range", f"0-{max_pages - 1}"])

            logger.info(f"Running marker command: {' '.join(marker_cmd)}")

            # Run marker CLI
            result = subprocess.run(
                marker_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                check=True,
            )

            logger.info("Marker conversion completed successfully")

            # Find the output markdown file
            output_files = list(Path(temp_output_dir).rglob("*.md"))
            if not output_files:
                raise PdfConversionError("No markdown output file found")

            # Read the markdown content
            output_file = output_files[0]
            markdown_content = output_file.read_text(encoding="utf-8")

            # Create basic metadata
            metadata = {
                "conversion_method": "marker_cli",
                "output_file": str(output_file.name),
                "pages": 0,  # We don't have easy access to page count from CLI
            }

            # Try to extract some basic info from marker output
            if result.stderr:
                logger.debug(f"Marker stderr: {result.stderr}")

            logger.info(f"Successfully converted PDF: {len(markdown_content)} chars")
            return markdown_content, metadata

        except subprocess.TimeoutExpired as e:
            error_msg = f"Marker conversion timed out after 5 minutes: {e}"
            logger.error(error_msg)
            raise PdfConversionError(error_msg) from e
        except subprocess.CalledProcessError as e:
            error_msg = f"Marker CLI failed with exit code {e.returncode}: {e.stderr}"
            logger.error(error_msg)
            raise PdfConversionError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to convert PDF with Marker CLI: {e}"
            logger.error(error_msg)
            raise PdfConversionError(error_msg) from e
        finally:
            # Clean up temporary directories
            if temp_input_dir and Path(temp_input_dir).exists():
                shutil.rmtree(temp_input_dir, ignore_errors=True)
            if temp_output_dir and Path(temp_output_dir).exists():
                shutil.rmtree(temp_output_dir, ignore_errors=True)

    def convert_pdf(
        self,
        source: str,
        max_pages: int | None = None,
    ) -> ConvertedContent:
        """Convert PDF to markdown from file path or URL.

        Parameters
        ----------
        source : str
            PDF file path or URL.
        max_pages : int, optional
            Maximum number of pages to process.

        Returns
        -------
        ConvertedContent
            Converted content with metadata.

        Raises
        ------
        PdfConversionError
            If conversion fails.
        ValueError
            If source is invalid.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> content = converter.convert_pdf("paper.pdf")
        >>> content.source_type
        'file'
        >>> content = converter.convert_pdf("https://arxiv.org/pdf/2506.05296")
        >>> content.source_type
        'arxiv'
        """
        try:
            source_type = self.determine_source_type(source)
            logger.info(f"Converting PDF from {source_type}: {source}")

            # Handle different source types
            if source_type == "file":
                # Local file
                pdf_path = Path(source)
                if not pdf_path.exists():
                    raise ValueError(f"PDF file not found: {source}")
                if not pdf_path.is_file():
                    raise ValueError(f"Path is not a file: {source}")

                # Try PyMuPDF first, fallback to Marker
                try:
                    markdown_content, conversion_metadata = self.convert_pdf_with_pymupdf(
                        pdf_path, max_pages
                    )
                    logger.info("PDF converted successfully using PyMuPDF")
                except PdfConversionError as e:
                    logger.warning(f"PyMuPDF conversion failed: {e}")
                    logger.info("Falling back to Marker conversion")
                    markdown_content, conversion_metadata = self.convert_pdf_with_marker(
                        pdf_path, max_pages
                    )
                    logger.info("PDF converted successfully using Marker as fallback")
                temp_file = None

            else:
                # URL - download first
                validated_url = self.validate_url(source)
                pdf_data = self.download_pdf(validated_url)

                # Save to temporary file
                temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                try:
                    temp_file.write(pdf_data)
                    temp_file.flush()
                    temp_pdf_path = Path(temp_file.name)

                    # Try PyMuPDF first, fallback to Marker
                    try:
                        markdown_content, conversion_metadata = self.convert_pdf_with_pymupdf(
                            temp_pdf_path, max_pages
                        )
                        logger.info("PDF converted successfully using PyMuPDF")
                    except PdfConversionError as e:
                        logger.warning(f"PyMuPDF conversion failed: {e}")
                        logger.info("Falling back to Marker conversion")
                        markdown_content, conversion_metadata = self.convert_pdf_with_marker(
                            temp_pdf_path, max_pages
                        )
                        logger.info("PDF converted successfully using Marker as fallback")

                finally:
                    temp_file.close()

            # Calculate word count
            word_count = len(markdown_content.split()) if markdown_content else 0

            # Create converted content object
            converted_content = ConvertedContent(
                url=source,
                markdown=markdown_content,
                metadata=conversion_metadata,
                conversion_date=datetime.now().isoformat(),
                word_count=word_count,
                source_type=source_type,
            )

            logger.info(
                f"Successfully converted PDF: {word_count} words, {conversion_metadata.get('pages', 0)} pages"
            )

            # Clean up temporary file if created
            if temp_file and Path(temp_file.name).exists():
                try:
                    Path(temp_file.name).unlink()
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary file: {e}")

            return converted_content

        except ValueError:
            # Input validation errors - don't retry
            raise
        except Exception as e:
            error_msg = f"Failed to convert PDF from {source}: {e}"
            logger.error(error_msg)
            raise PdfConversionError(error_msg) from e

    def content_to_text(self, content: ConvertedContent) -> str:
        """Convert converted content to plain text.

        Parameters
        ----------
        content : ConvertedContent
            Converted content object.

        Returns
        -------
        str
            Plain text content extracted from markdown.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> content = converter.convert_pdf("paper.pdf")
        >>> text = converter.content_to_text(content)
        >>> len(text) > 0
        True
        """
        if not content.markdown:
            return ""

        # Simple markdown to text conversion
        # Remove markdown formatting
        text = content.markdown

        # Remove headers
        text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)

        # Remove links but keep text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Remove bold/italic formatting
        text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
        text = re.sub(r"_+([^_]+)_+", r"\1", text)

        # Remove code blocks
        text = re.sub(r"```[^`]*```", "", text, flags=re.DOTALL)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Clean up whitespace
        text = re.sub(r"\n\s*\n", "\n\n", text)
        text = text.strip()

        return text

    def content_to_markdown(self, content: ConvertedContent) -> str:
        """Get markdown content from converted content.

        Parameters
        ----------
        content : ConvertedContent
            Converted content object.

        Returns
        -------
        str
            Markdown formatted content.

        Examples
        --------
        >>> converter = PdfConverter()
        >>> content = converter.convert_pdf("paper.pdf")
        >>> markdown = converter.content_to_markdown(content)
        >>> len(markdown) > 0
        True
        """
        return content.markdown or ""
