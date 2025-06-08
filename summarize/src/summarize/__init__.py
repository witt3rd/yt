"""Content summarization utilities.

This package provides functionality to summarize various types of content
including YouTube videos, text files, and other documents using AI models
like OpenAI GPT and Anthropic Claude, with support for different
summarization styles and output formats.
"""

from .summarizer import ContentSummarizer

__version__ = "0.1.0"
__all__ = ["ContentSummarizer"]
