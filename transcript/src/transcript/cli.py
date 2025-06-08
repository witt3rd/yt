"""Command-line interface for YouTube transcript extraction.

This module provides a CLI for extracting transcripts from YouTube videos
with various output formats and options.
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from common.config import Config
from common.logger import setup_logger
from .extractor import TranscriptExtractor
from .metadata import MetadataGenerator, YouTubeAPIError, OpenAIError


@click.command()
@click.argument('url_or_id', required=True)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output file path. If not provided, prints to stdout.'
)
@click.option(
    '--format', '-f', 'output_format',
    type=click.Choice(['text', 'timed', 'json', 'markdown'], case_sensitive=False),
    default='text',
    help='Output format (default: text).'
)
@click.option(
    '--languages', '-l',
    help='Comma-separated list of preferred languages (e.g., "en,es,fr").'
)
@click.option(
    '--no-auto-generated',
    is_flag=True,
    help='Exclude auto-generated transcripts, only use manual ones.'
)
@click.option(
    '--disable-ai-generation',
    is_flag=True,
    help='Disable AI-powered filename and tag generation for markdown format.'
)
@click.option(
    '--log-level',
    type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']),
    default='INFO',
    help='Logging level (default: INFO).'
)
@click.option(
    '--log-file',
    type=click.Path(path_type=Path),
    help='Log file path. If not provided, logs to stderr only.'
)
def main(
    url_or_id: str,
    output: Path | None,
    output_format: str,
    languages: str | None,
    no_auto_generated: bool,
    disable_ai_generation: bool,
    log_level: str,
    log_file: Path | None
):
    """Extract transcripts from YouTube videos.

    URL_OR_ID can be a YouTube URL or video ID.

    Examples:

        yt-transcript "https://youtube.com/watch?v=dQw4w9WgXcQ"

        yt-transcript dQw4w9WgXcQ --format json --output transcript.json

        yt-transcript dQw4w9WgXcQ --languages en,es --format timed

        yt-transcript dQw4w9WgXcQ --format markdown

        yt-transcript dQw4w9WgXcQ --format markdown --disable-ai-generation
    """
    # Set up logging
    setup_logger(level=log_level, log_file=log_file)

    try:
        # Initialize configuration and extractor
        config = Config()
        extractor = TranscriptExtractor(config)

        # Parse languages if provided
        language_list = None
        if languages:
            language_list = [lang.strip() for lang in languages.split(',')]

        # Extract video ID
        try:
            video_id = extractor.extract_video_id(url_or_id)
            logger.info(f"Extracted video ID: {video_id}")
        except ValueError as e:
            logger.error(f"Invalid YouTube URL or video ID: {e}")
            sys.exit(1)

        # Get transcript
        try:
            transcript = extractor.get_transcript(
                video_id,
                languages=language_list,
                auto_generated=not no_auto_generated
            )
            logger.info(f"Successfully extracted transcript with {len(transcript)} segments")
        except Exception as e:
            logger.error(f"Failed to extract transcript: {e}")
            sys.exit(1)

        # Format output
        if output_format.lower() == 'json':
            # Convert to JSON-serializable format
            transcript_data = []
            for segment in transcript:
                transcript_data.append({
                    'text': segment.text,
                    'start': segment.start,
                    'duration': segment.duration,
                    'end_time': segment.end_time
                })
            output_content = json.dumps({
                'video_id': video_id,
                'segments': transcript_data,
                'total_segments': len(transcript_data)
            }, indent=2)
        elif output_format.lower() == 'timed':
            output_content = extractor.transcript_to_timed_text(transcript)
        elif output_format.lower() == 'markdown':
            # Generate markdown with metadata and frontmatter
            try:
                metadata_generator = MetadataGenerator(config)

                # Fetch video metadata
                try:
                    video_metadata = metadata_generator.fetch_video_metadata(video_id)
                    logger.info(f"Fetched metadata for: {video_metadata.title}")
                except YouTubeAPIError as e:
                    logger.warning(f"Failed to fetch video metadata: {e}")
                    logger.info("Proceeding with basic transcript output")
                    output_content = extractor.transcript_to_text(transcript)
                    # Set suggested filename for markdown without metadata
                    if not output:
                        output = Path(f"{video_id}.md")
                else:
                    # Generate AI content if enabled and possible
                    ai_content = None
                    if not disable_ai_generation:
                        try:
                            ai_content = metadata_generator.generate_ai_content(video_metadata)
                            logger.info("Generated AI-powered metadata")
                        except OpenAIError as e:
                            logger.warning(f"Failed to generate AI content: {e}")
                            logger.info("Proceeding with basic metadata")

                    # Generate transcript content
                    transcript_text = extractor.transcript_to_text(transcript)

                    # Generate complete markdown with frontmatter
                    output_content = metadata_generator.generate_markdown_content(
                        video_metadata, transcript_text, ai_content
                    )

                    # Set suggested filename if not provided
                    if not output:
                        suggested_filename = metadata_generator.get_suggested_filename(
                            video_metadata, ai_content
                        )
                        output = Path(suggested_filename)
                        logger.info(f"Using suggested filename: {output}")

            except Exception as e:
                logger.error(f"Failed to generate markdown with metadata: {e}")
                logger.info("Falling back to plain text transcript")
                output_content = extractor.transcript_to_text(transcript)
                if not output:
                    output = Path(f"{video_id}.md")
        else:  # text format
            output_content = extractor.transcript_to_text(transcript)

        # Write output
        if output:
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(output_content, encoding='utf-8')
                logger.info(f"Transcript saved to: {output}")
            except Exception as e:
                logger.error(f"Failed to write output file: {e}")
                sys.exit(1)
        else:
            print(output_content)

        logger.info("Transcript extraction completed successfully")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
