"""YouTube content summarization functionality.

This module provides AI-powered summarization of YouTube video transcripts
using OpenAI GPT and Anthropic Claude models with configurable prompts
and output styles.
"""


from enum import Enum
from pathlib import Path

import openai
import anthropic
from loguru import logger

from common.config import Config
from common.types import TranscriptData, TranscriptSegment
from transcript import TranscriptExtractor


class SummaryStyle(Enum):
    """Enumeration of available summary styles."""

    BRIEF = "brief"
    DETAILED = "detailed"
    BULLET_POINTS = "bullet_points"
    KEY_TAKEAWAYS = "key_takeaways"
    CHAPTER_BREAKDOWN = "chapter_breakdown"


class VideoSummarizer:
    """Summarize YouTube video content using AI models.

    Provides methods to generate summaries of YouTube video transcripts
    using various AI models and summary styles, with automatic transcript
    extraction integration.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.
    transcript_extractor : TranscriptExtractor, optional
        Transcript extractor instance. If None, creates a new instance.

    Examples
    --------
    >>> summarizer = VideoSummarizer()
    >>> summary = summarizer.summarize_video(
    ...     "dQw4w9WgXcQ",
    ...     style=SummaryStyle.BRIEF
    ... )
    >>> len(summary)
    150
    """

    config: Config
    transcript_extractor: TranscriptExtractor
    openai_client: openai.OpenAI | None
    anthropic_client: anthropic.Anthropic | None

    def __init__(
        self,
        config: Config | None = None,
        transcript_extractor: TranscriptExtractor | None = None,
    ):
        """Initialize video summarizer.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        transcript_extractor : TranscriptExtractor, optional
            Transcript extractor instance for fetching transcripts.
        """
        self.config = config or Config()
        self.transcript_extractor = transcript_extractor or TranscriptExtractor(
            self.config
        )

        # Initialize AI clients based on available API keys
        self.openai_client = None
        self.anthropic_client = None

        if self.config.openai_api_key:
            self.openai_client = openai.OpenAI(api_key=self.config.openai_api_key)
            logger.debug("OpenAI client initialized")

        if self.config.anthropic_api_key:
            self.anthropic_client = anthropic.Anthropic(
                api_key=self.config.anthropic_api_key
            )
            logger.debug("Anthropic client initialized")

        if not self.openai_client and not self.anthropic_client:
            logger.warning("No AI API keys configured - summarization will not work")

    def _get_system_prompt(self, style: SummaryStyle) -> str:
        """Get system prompt for the specified summary style.

        Parameters
        ----------
        style : SummaryStyle
            Desired summary style.

        Returns
        -------
        str
            System prompt for the AI model.
        """
        prompts = {
            SummaryStyle.BRIEF: (
                "You are an expert at creating concise summaries. "
                "Provide a brief, clear summary that captures the main points "
                "in 2-3 sentences."
            ),
            SummaryStyle.DETAILED: (
                "You are an expert at creating comprehensive summaries. "
                "Provide a detailed summary that covers all major topics, "
                "key arguments, and important details discussed in the content."
            ),
            SummaryStyle.BULLET_POINTS: (
                "You are an expert at organizing information. "
                "Create a structured summary using bullet points that "
                "organize the content into clear, actionable points."
            ),
            SummaryStyle.KEY_TAKEAWAYS: (
                "You are an expert at identifying key insights. "
                "Extract and present the most important takeaways, lessons, "
                "or insights from the content in a clear, numbered list."
            ),
            SummaryStyle.CHAPTER_BREAKDOWN: (
                "You are an expert at structuring content. "
                "Break down the content into logical chapters or sections, "
                "providing a title and summary for each major segment."
            ),
        }
        return prompts.get(style, prompts[SummaryStyle.BRIEF])

    def _create_user_prompt(self, transcript_text: str, style: SummaryStyle) -> str:
        """Create user prompt with transcript content.

        Parameters
        ----------
        transcript_text : str
            The transcript text to summarize.
        style : SummaryStyle
            Desired summary style.

        Returns
        -------
        str
            User prompt including the transcript.
        """
        style_instructions = {
            SummaryStyle.BRIEF: "Create a brief summary (2-3 sentences):",
            SummaryStyle.DETAILED: "Create a detailed summary covering all major points:",
            SummaryStyle.BULLET_POINTS: "Create a bullet-point summary:",
            SummaryStyle.KEY_TAKEAWAYS: "Extract the key takeaways as a numbered list:",
            SummaryStyle.CHAPTER_BREAKDOWN: "Break this down into chapters with titles and summaries:",
        }

        instruction = style_instructions.get(
            style, style_instructions[SummaryStyle.BRIEF]
        )

        return f"""{instruction}

Transcript:
{transcript_text}"""

    def _summarize_with_openai(
        self, transcript_text: str, style: SummaryStyle, model: str | None = None
    ) -> str:
        """Generate summary using OpenAI API.

        Parameters
        ----------
        transcript_text : str
            The transcript text to summarize.
        style : SummaryStyle
            Desired summary style.
        model : str, optional
            OpenAI model to use. If None, uses default from config.

        Returns
        -------
        str
            Generated summary.

        Raises
        ------
        Exception
            If OpenAI API call fails.
        """
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized - check API key")

        model = model or self.config.default_model

        try:
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(style)},
                    {
                        "role": "user",
                        "content": self._create_user_prompt(transcript_text, style),
                    },
                ],
                temperature=0.3,  # Lower temperature for more consistent summaries
                max_tokens=2000,
            )

            summary = response.choices[0].message.content
            if summary is None:
                raise ValueError("OpenAI returned empty response")
            logger.info(f"Generated summary using OpenAI {model}")
            return summary

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _summarize_with_anthropic(
        self,
        transcript_text: str,
        style: SummaryStyle,
        model: str = "claude-3-haiku-20240307",
    ) -> str:
        """Generate summary using Anthropic API.

        Parameters
        ----------
        transcript_text : str
            The transcript text to summarize.
        style : SummaryStyle
            Desired summary style.
        model : str, default "claude-3-haiku-20240307"
            Anthropic model to use.

        Returns
        -------
        str
            Generated summary.

        Raises
        ------
        Exception
            If Anthropic API call fails.
        """
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized - check API key")

        try:
            message = self.anthropic_client.messages.create(
                model=model,
                max_tokens=2000,
                temperature=0.3,
                system=self._get_system_prompt(style),
                messages=[
                    {
                        "role": "user",
                        "content": self._create_user_prompt(transcript_text, style),
                    }
                ],
            )

            # Extract text from the response
            if message.content:
                # Look for text content in the response
                summary = ""
                for block in message.content:
                    # Use getattr to safely access text attribute
                    block_text = getattr(block, "text", None)
                    if block_text:
                        summary = block_text
                        break
                if not summary:
                    raise ValueError("No text content found in Anthropic response")
            else:
                raise ValueError("Anthropic returned empty response")
            logger.info(f"Generated summary using Anthropic {model}")
            return summary

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def summarize_transcript(
        self,
        transcript: TranscriptData,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
    ) -> str:
        """Summarize a transcript using AI.

        Parameters
        ----------
        transcript : TranscriptData
            List of transcript segments to summarize.
        style : SummaryStyle, default SummaryStyle.BRIEF
            Desired summary style.
        provider : str, optional
            AI provider to use ("openai" or "anthropic").
            If None, uses OpenAI if available, otherwise Anthropic.

        Returns
        -------
        str
            Generated summary.

        Raises
        ------
        ValueError
            If no AI providers are configured.
        Exception
            If summarization fails.

        Examples
        --------
        >>> summarizer = VideoSummarizer()
        >>> segments = [TranscriptSegment("Hello world", 0, 1)]
        >>> summary = summarizer.summarize_transcript(segments)
        >>> "Hello" in summary
        True
        """
        # Convert transcript to text
        transcript_text = self.transcript_extractor.transcript_to_text(transcript)

        # Check transcript length
        if len(transcript_text) > self.config.max_transcript_length:
            logger.warning("Transcript exceeds maximum length, truncating")
            transcript_text = transcript_text[: self.config.max_transcript_length]

        # Determine provider
        if provider:
            provider = provider.lower()
        elif self.openai_client:
            provider = "openai"
        elif self.anthropic_client:
            provider = "anthropic"
        else:
            raise ValueError("No AI providers configured")

        # Generate summary
        if provider == "openai":
            return self._summarize_with_openai(transcript_text, style)
        elif provider == "anthropic":
            return self._summarize_with_anthropic(transcript_text, style)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def summarize_video(
        self,
        url_or_id: str,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
        languages: list[str] | None = None,
    ) -> str:
        """Summarize a YouTube video by URL or ID.

        Parameters
        ----------
        url_or_id : str
            YouTube URL or video ID.
        style : SummaryStyle, default SummaryStyle.BRIEF
            Desired summary style.
        provider : str, optional
            AI provider to use ("openai" or "anthropic").
        languages : list[str], optional
            Preferred transcript languages.

        Returns
        -------
        str
            Generated summary.

        Raises
        ------
        Exception
            If transcript extraction or summarization fails.

        Examples
        --------
        >>> summarizer = VideoSummarizer()
        >>> summary = summarizer.summarize_video(
        ...     "dQw4w9WgXcQ",
        ...     style=SummaryStyle.KEY_TAKEAWAYS
        ... )
        >>> len(summary) > 0
        True
        """
        # Extract video ID
        video_id = self.transcript_extractor.extract_video_id(url_or_id)
        logger.info(f"Summarizing video: {video_id}")

        # Get transcript
        transcript = self.transcript_extractor.get_transcript(
            video_id, languages=languages
        )

        # Generate summary
        summary = self.summarize_transcript(transcript, style, provider)

        logger.info("Video summarization completed successfully")
        return summary

    def text_to_transcript(self, text: str) -> TranscriptData:
        """Convert plain text to transcript format."""
        text = text.strip()
        if not text:
            raise ValueError("Text file is empty")

        segment = TranscriptSegment(
            text=text,
            start=0.0,
            duration=float(len(text.split()))
        )
        return [segment]

    def summarize_text_file(
        self,
        file_path: Path,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None
    ) -> str:
        """Summarize content from a text file."""
        logger.info(f"Reading text file: {file_path}")

        try:
            text_content = file_path.read_text(encoding='utf-8')
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            raise ValueError(f"Unable to read file: {e}")

        if not text_content.strip():
            raise ValueError(f"File {file_path} is empty")

        transcript = self.text_to_transcript(text_content)
        summary = self.summarize_transcript(transcript, style, provider)

        logger.info("Text file summarization completed successfully")
        return summary
