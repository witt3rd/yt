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
    help="Output file path. If not provided, prints to stdout.",
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

    Examples:

        summarize "https://youtube.com/watch?v=dQw4w9WgXcQ"

        summarize dQw4w9WgXcQ --style detailed --provider anthropic

        summarize transcript.txt --style bullet_points --format json --output summary.json

        summarize dQw4w9WgXcQ --languages en,es --style key_takeaways

        summarize alita.txt --style questions --provider openai

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
            else:
                # Assume it's a YouTube URL or video ID
                try:
                    content_id = summarizer.transcript_extractor.extract_video_id(
                        input_source
                    )
                    logger.info(f"Processing video ID: {content_id}")
                    summary = summarizer.summarize_video(
                        input_source,
                        style=summary_style,
                        provider=provider,
                        languages=language_list,
                    )
                except ValueError as e:
                    logger.error(
                        f"Invalid input: not a valid file path or YouTube URL/ID: {e}"
                    )
                    sys.exit(1)

            logger.info("Summary generation completed successfully")
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            sys.exit(1)

        # Format output
        if output_format.lower() == "json":
            output_content = json.dumps(
                {
                    "content_id": content_id,
                    "style": summary_style.value,
                    "provider": provider,
                    "summary": summary,
                    "languages": language_list,
                },
                indent=2,
            )
        else:  # text format
            output_content = summary

        # Write output
        if output:
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                _ = output.write_text(output_content, encoding="utf-8")
                logger.info(f"Summary saved to: {output}")
            except Exception as e:
                logger.error(f"Failed to write output file: {e}")
                sys.exit(1)
        else:
            print(output_content)

        logger.info("Content summarization completed successfully")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
