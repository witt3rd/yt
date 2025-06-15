"""Command-line interface for YouTube transcript extraction using yt-dlp.

This module provides a CLI for extracting transcripts from YouTube videos
with various output formats and options using yt-dlp as the backend.
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from common.config import Config
from common.logger import setup_logger
from .extractor import (
    TranscriptExtractor,
    TranscriptExtractorError,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)


@click.command()
@click.argument('url_or_id', required=True)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output file path. If not provided, prints to stdout.'
)
@click.option(
    '--format', '-f', 'output_format',
    type=click.Choice(['text', 'timed', 'json'], case_sensitive=False),
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
    log_level: str,
    log_file: Path | None
):
    """Extract transcripts from YouTube videos using yt-dlp.

    URL_OR_ID can be a YouTube URL or video ID.

    Examples:

        yt-transcript "https://youtube.com/watch?v=dQw4w9WgXcQ"

        yt-transcript dQw4w9WgXcQ --format json --output transcript.json

        yt-transcript dQw4w9WgXcQ --languages en,es --format timed

        yt-transcript dQw4w9WgXcQ --no-auto-generated
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
        except VideoUnavailable as e:
            logger.error(f"Video unavailable: {e}")
            sys.exit(1)
        except NoTranscriptFound as e:
            logger.error(f"No transcript found: {e}")
            sys.exit(1)
        except TranscriptsDisabled as e:
            logger.error(f"Transcripts disabled: {e}")
            sys.exit(1)
        except TranscriptExtractorError as e:
            logger.error(f"Transcript extraction failed: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error during transcript extraction: {e}")
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
