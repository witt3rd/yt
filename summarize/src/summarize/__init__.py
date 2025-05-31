"""YouTube content summarization utilities.

This package provides functionality to summarize YouTube video content
using AI models like OpenAI GPT and Anthropic Claude, with support for
different summarization styles and output formats.
"""

from .summarizer import VideoSummarizer

__version__ = "0.1.0"
__all__ = ["VideoSummarizer"]
