"""Command-line interface for content summarization.

This module provides a CLI for summarizing various types of content
including YouTube videos, text files, and other documents with various
AI providers, styles, and output options.
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from common.config import Config
from common.logger import setup_logger
from .summarizer import ContentSummarizer, SummaryStyle


@click.command()
@click.argument("input_source", required=True)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file path. If not provided, defaults to input name with .md extension (e.g., video_id.md).",
)
@click.option(
    "--style",
    "-s",
    type=click.Choice([s.value for s in SummaryStyle], case_sensitive=False),
    default=SummaryStyle.BRIEF.value,
    help="Summary style (default: brief).",
)
@click.option(
    "--provider",
    "-p",
    type=click.Choice(["openai", "anthropic"], case_sensitive=False),
    help="AI provider to use. If not specified, uses OpenAI if available, then Anthropic.",
)
@click.option(
    "--languages",
    "-l",
    help='Comma-separated list of preferred transcript languages (e.g., "en,es,fr").',
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["text", "json"], case_sensitive=False),
    default="text",
    help="Output format (default: text).",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Logging level (default: INFO).",
)
@click.option(
    "--log-file",
    type=click.Path(path_type=Path),
    help="Log file path. If not provided, logs to stderr only.",
)
def main(
    input_source: str,
    output: Path | None,
    style: str,
    provider: str | None,
    languages: str | None,
    output_format: str,
    log_level: str,
    log_file: Path | None,
):
    """Summarize various types of content using AI.

    INPUT_SOURCE can be a YouTube URL, video ID, or path to a text file.

    By default, output files are automatically created with .md extension:
    - Video IDs: saved as "video_id.md"
    - Text files: saved with same name but .md extension

    Examples:

        # Auto-saves to dQw4w9WgXcQ.md
        summarize "https://youtube.com/watch?v=dQw4w9WgXcQ"

        # Auto-saves to dQw4w9WgXcQ.md with detailed summary
        summarize dQw4w9WgXcQ --style detailed --provider anthropic

        # Auto-saves to transcript.md
        summarize transcript.txt --style bullet_points

        # Explicit output file (overrides default behavior)
        summarize dQw4w9WgXcQ --style questions --output custom_summary.json --format json

        # Auto-saves to alita.md with questions style
        summarize alita.txt --style questions --provider openai

        # Auto-saves to document.md with chapter breakdown
        summarize document.md --style chapter_breakdown --provider anthropic
    """
    # Set up logging
    setup_logger(level=log_level, log_file=log_file)

    try:
        # Initialize configuration and summarizer
        config = Config()

        # Validate configuration
        if not config.validate():
            logger.error("Configuration validation failed")
            sys.exit(1)

        summarizer = ContentSummarizer(config)

        # Parse languages if provided
        language_list = None
        if languages:
            language_list = [lang.strip() for lang in languages.split(",")]

        # Convert style string to enum
        try:
            summary_style = SummaryStyle(style.lower())
        except ValueError:
            logger.error(f"Invalid style: {style}")
            sys.exit(1)

        # Track if output was explicitly provided by user
        output_explicitly_provided = output is not None

        # Generate default output filename if none provided
        if output is None:
            # Check if input is a file path
            input_path = Path(input_source)
            if input_path.exists() and input_path.is_file():
                # For file input, use same name with .md extension
                output = Path(input_path.with_suffix('.md'))
                logger.info(f"No output file specified, using default: {output}")
            else:
                # For YouTube URL/ID, extract video ID and use it as filename
                try:
                    video_id = summarizer.transcript_extractor.extract_video_id(input_source)
                    output = Path(f"{video_id}.md")
                    logger.info(f"No output file specified, using default: {output}")
                except ValueError:
                    # For web URLs, we'll set the filename after we get the AI-generated name
                    # For now, use a temporary placeholder
                    output = Path("summary.md")
                    logger.info(f"No output file specified, will use AI-generated filename")

        # Detect input type and generate summary
        try:
            logger.info(
                f"Generating {summary_style.value} summary using {provider or 'auto-detected'} provider"
            )

            # Check if input is a file path
            input_path = Path(input_source)
            if input_path.exists() and input_path.is_file():
                logger.info(f"Processing text file: {input_source}")
                summary = summarizer.summarize_text_file(
                    input_path, style=summary_style, provider=provider
                )
                # For file input, we don't have a content_id
                content_id = None
                output_content = summary
            else:
                # Check if it's a web URL (starts with http:// or https://)
                if input_source.startswith(('http://', 'https://')):
                    # Check if it's a YouTube URL first
                    try:
                        content_id = summarizer.transcript_extractor.extract_video_id(
                            input_source
                        )
                        logger.info(f"Processing YouTube video: {content_id}")

                        # Use enhanced metadata functionality for YouTube videos
                        enhanced_markdown, suggested_filename = summarizer.summarize_video_with_metadata(
                            input_source,
                            style=summary_style,
                            provider=provider,
                            languages=language_list,
                        )

                        # Update output filename if not explicitly provided
                        if not output_explicitly_provided:
                            output = Path(suggested_filename)
                            logger.info(f"Using enhanced filename: {output}")

                        # For YouTube videos, we already have the enhanced markdown
                        output_content = enhanced_markdown
                        summary = enhanced_markdown  # For compatibility with existing logic

                    except ValueError:
                        # Not a YouTube URL, treat as regular web URL
                        logger.info(f"Processing web URL: {input_source}")
                        try:
                            # Use enhanced metadata functionality for web URLs
                            enhanced_markdown, suggested_filename = summarizer.summarize_url_with_metadata(
                                input_source,
                                style=summary_style,
                                provider=provider,
                            )

                            # Update output filename if not explicitly provided
                            if not output_explicitly_provided:
                                output = Path(suggested_filename)
                                logger.info(f"Using enhanced filename: {output}")

                            # For web URLs, we already have the enhanced markdown
                            output_content = enhanced_markdown
                            summary = enhanced_markdown  # For compatibility with existing logic
                            content_id = None  # Web URLs don't have a specific content_id

                        except Exception as e:
                            logger.error(f"Failed to process web URL: {e}")
                            sys.exit(1)
                else:
                    # Assume it's a YouTube video ID
                    try:
                        content_id = summarizer.transcript_extractor.extract_video_id(
                            input_source
                        )
                        logger.info(f"Processing video ID: {content_id}")

                        # Use enhanced metadata functionality for YouTube videos
                        enhanced_markdown, suggested_filename = summarizer.summarize_video_with_metadata(
                            input_source,
                            style=summary_style,
                            provider=provider,
                            languages=language_list,
                        )

                        # Update output filename if not explicitly provided
                        if not output_explicitly_provided:
                            output = Path(suggested_filename)
                            logger.info(f"Using enhanced filename: {output}")

                        # For YouTube videos, we already have the enhanced markdown
                        output_content = enhanced_markdown
                        summary = enhanced_markdown  # For compatibility with existing logic

                    except ValueError as e:
                        logger.error(
                            f"Invalid input: not a valid file path, web URL, or YouTube URL/ID: {e}"
                        )
                        sys.exit(1)

            logger.info("Summary generation completed successfully")
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            sys.exit(1)

        # Format output for JSON if requested
        if output_format.lower() == "json":
            # For JSON format, extract just the summary text from enhanced markdown if needed
            summary_text = summary
            if isinstance(summary, str) and summary.startswith("---"):
                # If it's enhanced markdown, extract just the content after frontmatter
                parts = summary.split("---", 2)
                if len(parts) >= 3:
                    summary_text = parts[2].strip()

            output_content = json.dumps(
                {
                    "content_id": content_id,
                    "style": summary_style.value,
                    "provider": provider,
                    "summary": summary_text,
                    "languages": language_list,
                },
                indent=2,
            )
        # For text format, output_content is already set correctly above

        # Write output (output is always defined now due to default behavior)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            _ = output.write_text(output_content, encoding="utf-8")
            logger.info(f"Summary saved to: {output}")
        except Exception as e:
            logger.error(f"Failed to write output file: {e}")
            sys.exit(1)

        logger.info("Content summarization completed successfully")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
