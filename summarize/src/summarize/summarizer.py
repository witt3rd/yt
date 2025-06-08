"""Content summarization functionality.

This module provides AI-powered summarization of various content types
including YouTube video transcripts, text files, and other documents using
OpenAI GPT and Anthropic Claude models with configurable prompts and output styles.
"""

from enum import Enum
from pathlib import Path

import openai
import anthropic
from loguru import logger

from common.config import Config
from common.types import TranscriptData, TranscriptSegment
from transcript import TranscriptExtractor, MetadataGenerator, YouTubeAPIError, OpenAIError
from scrape import WebScraper, WebMetadataGenerator, FirecrawlAPIError


class SummaryStyle(Enum):
    """Enumeration of available summary styles."""

    BRIEF = "brief"
    DETAILED = "detailed"
    BULLET_POINTS = "bullet_points"
    KEY_TAKEAWAYS = "key_takeaways"
    CHAPTER_BREAKDOWN = "chapter_breakdown"
    QUESTIONS = "questions"


class ContentSummarizer:
    """Summarize various types of content using AI models.

    Provides methods to generate summaries of text files, YouTube video transcripts,
    and other content types using various AI models and summary styles, with automatic
    content extraction and processing.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.
    transcript_extractor : TranscriptExtractor, optional
        Transcript extractor instance. If None, creates a new instance.

    Examples
    --------
    >>> summarizer = ContentSummarizer()
    >>> summary = summarizer.summarize_url(
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
        """Initialize content summarizer.

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

        # Initialize metadata generator for enhanced summaries
        self.metadata_generator = MetadataGenerator(self.config)

        # Initialize web scraper and metadata generator for URL processing
        self.web_scraper = WebScraper(self.config)
        self.web_metadata_generator = WebMetadataGenerator(self.config)

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

    def _load_prompt_from_file(self, filename: str) -> str:
        """Load prompt content from a file in the prompts directory.

        Parameters
        ----------
        filename : str
            Name of the prompt file to load.

        Returns
        -------
        str
            Content of the prompt file.

        Raises
        ------
        FileNotFoundError
            If the prompt file doesn't exist.
        """
        prompt_path = self.config.prompts_path / filename
        try:
            content = prompt_path.read_text(encoding="utf-8")
            logger.debug(f"Loaded prompt from {prompt_path}")
            return content
        except FileNotFoundError:
            logger.error(f"Prompt file not found: {prompt_path}")
            raise
        except Exception as e:
            logger.error(f"Failed to read prompt file {prompt_path}: {e}")
            raise

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
        # Handle dynamic prompt loading for QUESTIONS style
        if style == SummaryStyle.QUESTIONS:
            try:
                return self._load_prompt_from_file("question_tree.md")
            except FileNotFoundError:
                logger.warning(
                    "question_tree.md not found, falling back to default prompt"
                )
                return (
                    "You are an expert at reverse engineering question architecture from content. "
                    "Apply systematic question-oriented analysis to extract the implicit "
                    "question-answer structure from the provided content, following the "
                    "four-phase method: central question discovery, domain question extraction, "
                    "specific and atomic question decomposition, and synthesis chain evaluation."
                )

        # Static prompts for other styles
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
            SummaryStyle.QUESTIONS: "Apply the reverse engineering question architecture methodology to analyze this content:",
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
        >>> summarizer = ContentSummarizer()
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
        >>> summarizer = ContentSummarizer()
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

        logger.info("Content summarization completed successfully")
        return summary

    def summarize_video_with_metadata(
        self,
        url_or_id: str,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
        languages: list[str] | None = None,
        disable_ai_generation: bool = False,
    ) -> tuple[str, str]:
        """Summarize a YouTube video with enhanced metadata and frontmatter.

        Uses yt-transcript's existing markdown generation to get full metadata,
        then replaces transcript content with summary content.

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
        disable_ai_generation : bool, default False
            Disable AI-powered filename and tag generation.

        Returns
        -------
        tuple[str, str]
            Enhanced markdown content with frontmatter and suggested filename.

        Raises
        ------
        Exception
            If transcript extraction or summarization fails.

        Examples
        --------
        >>> summarizer = ContentSummarizer()
        >>> content, filename = summarizer.summarize_video_with_metadata(
        ...     "dQw4w9WgXcQ",
        ...     style=SummaryStyle.KEY_TAKEAWAYS
        ... )
        >>> filename.endswith(".md")
        True
        >>> "---" in content
        True
        """
        # Extract video ID
        video_id = self.transcript_extractor.extract_video_id(url_or_id)
        logger.info(f"Summarizing video with metadata: {video_id}")

        try:
            # Get transcript
            transcript = self.transcript_extractor.get_transcript(
                video_id, languages=languages
            )

            # Generate enhanced markdown using existing yt-transcript functionality
            try:
                video_metadata = self.metadata_generator.fetch_video_metadata(video_id)
                logger.info(f"Fetched metadata for: {video_metadata.title}")

                # Generate AI content if enabled
                ai_content = None
                if not disable_ai_generation:
                    try:
                        ai_content = self.metadata_generator.generate_ai_content(video_metadata)
                        logger.info("Generated AI-powered metadata")
                    except OpenAIError as e:
                        logger.warning(f"Failed to generate AI content: {e}")
                        logger.info("Proceeding with basic metadata")

                # Generate transcript text and summary
                transcript_text = self.transcript_extractor.transcript_to_text(transcript)
                summary = self.summarize_transcript(transcript, style, provider)

                # Generate complete markdown with frontmatter + summary instead of transcript
                enhanced_markdown = self.metadata_generator.generate_markdown_content(
                    video_metadata, summary, ai_content
                )

                # Get suggested filename
                suggested_filename = self.metadata_generator.get_suggested_filename(
                    video_metadata, ai_content
                )

                logger.info(f"Generated enhanced summary with filename: {suggested_filename}")
                return enhanced_markdown, suggested_filename

            except YouTubeAPIError as e:
                logger.warning(f"Failed to fetch video metadata: {e}")
                logger.info("Falling back to basic summary without metadata")

                # Fallback: generate plain summary and use basic filename
                summary = self.summarize_transcript(transcript, style, provider)
                basic_filename = f"{video_id}.md"
                return summary, basic_filename

        except Exception as e:
            logger.error(f"Failed to summarize video with metadata: {e}")
            raise

        logger.info("Content summarization with metadata completed successfully")

    def text_to_transcript(self, text: str) -> TranscriptData:
        """Convert plain text to transcript format."""
        text = text.strip()
        if not text:
            raise ValueError("Text file is empty")

        segment = TranscriptSegment(
            text=text, start=0.0, duration=float(len(text.split()))
        )
        return [segment]

    def summarize_text_file(
        self,
        file_path: Path,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
    ) -> str:
        """Summarize content from a text file."""
        logger.info(f"Reading text file: {file_path}")

        try:
            text_content = file_path.read_text(encoding="utf-8")
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

    def summarize_url(
        self,
        url: str,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
    ) -> str:
        """Summarize content from a web URL.

        Parameters
        ----------
        url : str
            Web URL to scrape and summarize.
        style : SummaryStyle, default SummaryStyle.BRIEF
            Desired summary style.
        provider : str, optional
            AI provider to use ("openai" or "anthropic").

        Returns
        -------
        str
            Generated summary.

        Raises
        ------
        Exception
            If scraping or summarization fails.

        Examples
        --------
        >>> summarizer = ContentSummarizer()
        >>> summary = summarizer.summarize_url(
        ...     "https://example.com",
        ...     style=SummaryStyle.KEY_TAKEAWAYS
        ... )
        >>> len(summary) > 0
        True
        """
        logger.info(f"Summarizing URL: {url}")

        try:
            # Scrape content
            scraped_content = self.web_scraper.scrape_content(
                url=url,
                formats=['markdown'],
                only_main_content=True,
            )

            logger.info(f"Successfully scraped content: {scraped_content.word_count} words")

            # Convert to text and summarize
            content_text = self.web_scraper.content_to_text(scraped_content)
            transcript = self.text_to_transcript(content_text)
            summary = self.summarize_transcript(transcript, style, provider)

            logger.info("URL summarization completed successfully")
            return summary

        except FirecrawlAPIError as e:
            logger.error(f"Failed to scrape URL {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to summarize URL {url}: {e}")
            raise

    def summarize_url_with_metadata(
        self,
        url: str,
        style: SummaryStyle = SummaryStyle.BRIEF,
        provider: str | None = None,
        disable_ai_generation: bool = False,
    ) -> tuple[str, str]:
        """Summarize a web URL with enhanced metadata and frontmatter.

        Parameters
        ----------
        url : str
            Web URL to scrape and summarize.
        style : SummaryStyle, default SummaryStyle.BRIEF
            Desired summary style.
        provider : str, optional
            AI provider to use ("openai" or "anthropic").
        disable_ai_generation : bool, default False
            Disable AI-powered filename and tag generation.

        Returns
        -------
        tuple[str, str]
            Enhanced markdown content with frontmatter and suggested filename.

        Raises
        ------
        Exception
            If scraping or summarization fails.

        Examples
        --------
        >>> summarizer = ContentSummarizer()
        >>> content, filename = summarizer.summarize_url_with_metadata(
        ...     "https://example.com",
        ...     style=SummaryStyle.KEY_TAKEAWAYS
        ... )
        >>> filename.endswith(".md")
        True
        >>> "---" in content
        True
        """
        logger.info(f"Summarizing URL with metadata: {url}")

        try:
            # Scrape content
            scraped_content = self.web_scraper.scrape_content(
                url=url,
                formats=['markdown'],
                only_main_content=True,
            )

            logger.info(f"Successfully scraped content: {scraped_content.word_count} words")

            # Extract web metadata
            try:
                web_metadata = self.web_metadata_generator.extract_web_metadata(scraped_content)
                logger.info(f"Extracted metadata for: {web_metadata.title or web_metadata.url}")

                # Generate AI content if enabled
                ai_content = None
                if not disable_ai_generation:
                    try:
                        # Get content preview for AI analysis
                        content_preview = scraped_content.markdown[:2000] if scraped_content.markdown else ""
                        ai_content = self.web_metadata_generator.generate_ai_content_for_web(
                            web_metadata, content_preview
                        )
                        logger.info("Generated AI-powered metadata")
                    except Exception as e:
                        logger.warning(f"Failed to generate AI content: {e}")
                        logger.info("Proceeding with basic metadata")

                # Convert to text and generate summary
                content_text = self.web_scraper.content_to_text(scraped_content)
                transcript = self.text_to_transcript(content_text)
                summary = self.summarize_transcript(transcript, style, provider)

                # Generate complete markdown with frontmatter + summary
                enhanced_markdown = self.web_metadata_generator.generate_markdown_content_for_web(
                    web_metadata, summary, ai_content
                )

                # Get suggested filename
                suggested_filename = self.web_metadata_generator.get_suggested_filename_for_web(
                    web_metadata, ai_content
                )

                logger.info(f"Generated enhanced summary with filename: {suggested_filename}")
                return enhanced_markdown, suggested_filename

            except Exception as e:
                logger.warning(f"Failed to extract web metadata: {e}")
                logger.info("Falling back to basic summary without metadata")

                # Fallback: generate plain summary and use basic filename
                content_text = self.web_scraper.content_to_text(scraped_content)
                transcript = self.text_to_transcript(content_text)
                summary = self.summarize_transcript(transcript, style, provider)

                # Generate basic filename from URL
                try:
                    validated_url = self.web_scraper.validate_url(url)
                    domain = validated_url.split('/')[2].replace('www.', '')
                    basic_filename = f"summary-{domain}.md"
                except Exception:
                    basic_filename = "summary-web-content.md"

                return summary, basic_filename

        except FirecrawlAPIError as e:
            logger.error(f"Failed to scrape URL {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to summarize URL with metadata: {e}")
            raise

        logger.info("URL summarization with metadata completed successfully")
