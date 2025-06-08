"""PDF to markdown conversion utilities using Marker.

This package provides functionality to convert PDF documents to markdown
format using the Marker library, with support for arXiv papers and
enhanced metadata generation for Obsidian-compatible output.
"""

from .converter import PdfConverter, ConvertedContent, PdfConversionError
from .metadata import (
    PdfMetadataGenerator,
    PdfMetadata,
)

__version__ = "0.1.0"
__all__ = [
    "PdfConverter",
    "PdfMetadataGenerator",
    "PdfMetadata",
    "ConvertedContent",
    "PdfConversionError",
]
