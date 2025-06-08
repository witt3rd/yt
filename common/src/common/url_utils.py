"""URL utilities for content type detection and validation.

This module provides utilities for detecting content types and validating URLs,
particularly focused on PDF content detection for remote URLs.
"""

import re
from typing import Optional

import requests
from loguru import logger
from requests.exceptions import ConnectionError, Timeout, RequestException


def is_remote_pdf_url(url: str, timeout: int = 5) -> bool:
    """Check if a URL points to a PDF document.

    Performs an HTTP HEAD request to check the Content-Type header without
    downloading the full content. More reliable than pattern matching on URLs.

    Parameters
    ----------
    url : str
        URL to check for PDF content.
    timeout : int, default 5
        Timeout in seconds for the HTTP request.

    Returns
    -------
    bool
        True if the URL points to a PDF document, False otherwise.

    Examples
    --------
    >>> is_remote_pdf_url("https://arxiv.org/pdf/2506.05296")
    True
    >>> is_remote_pdf_url("https://example.com/document.html")
    False
    >>> is_remote_pdf_url("invalid-url")
    False

    Notes
    -----
    This function only works for publicly accessible URLs that respond to
    HEAD requests. Some servers may block HEAD requests or require
    authentication, in which case this will return False.
    """
    if not url or not isinstance(url, str):
        logger.debug(f"Invalid URL provided: {url}")
        return False

    # Basic URL validation
    if not _is_valid_http_url(url):
        logger.debug(f"URL is not a valid HTTP/HTTPS URL: {url}")
        return False

    try:
        logger.debug(f"Checking if URL is PDF: {url}")
        response = requests.head(url, timeout=timeout, allow_redirects=True)

        # Check if request was successful
        if not response.ok:
            logger.warning(f"HTTP {response.status_code} when checking URL: {url}")
            return False

        content_type = response.headers.get("Content-Type", "").lower()
        is_pdf = content_type == "application/pdf"

        logger.debug(f"Content-Type for {url}: {content_type}")
        logger.debug(f"Is PDF: {is_pdf}")

        return is_pdf

    except ConnectionError:
        logger.warning(f"Failed to connect to URL: {url}")
        return False
    except Timeout:
        logger.warning(f"Timeout when checking URL: {url}")
        return False
    except RequestException as e:
        logger.warning(f"Request error when checking URL {url}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error when checking URL {url}: {e}")
        return False


def _is_valid_http_url(url: str) -> bool:
    """Check if a string is a valid HTTP/HTTPS URL.

    Parameters
    ----------
    url : str
        String to validate as URL.

    Returns
    -------
    bool
        True if the string is a valid HTTP/HTTPS URL, False otherwise.
    """
    if not url or not isinstance(url, str):
        return False

    # Basic HTTP/HTTPS URL pattern
    url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(url_pattern, url, re.IGNORECASE))
