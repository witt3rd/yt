"""Command-line interface for PDF to markdown conversion.

This module provides a CLI for converting PDF documents to markdown
using the Marker library with various output formats and AI-powered
enhancements.
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from common.config import Config
from common.logger import setup_logger
from .converter import PdfConverter, PdfConversionError
from .metadata import PdfMetadataGenerator, MetadataGenerationError


@click.command()
@click.argument('source', required=True)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output file path. If not provided, prints to stdout or auto-generates filename for markdown format.'
)
@click.option(
    '--format', '-f', 'output_format',
    type=click.Choice(['text', 'markdown', 'json'], case_sensitive=False),
    default='text',
    help='Output format (default: text).'
)
@click.option(
    '--max-pages',
    type=int,
    help='Maximum number of pages to process.'
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
    source: str,
    output: Path | None,
    output_format: str,
    max_pages: int | None,
    disable_ai_generation: bool,
    log_level: str,
    log_file: Path | None
):
    """Convert PDF documents to markdown using Marker.

    SOURCE can be a local PDF file path or URL to a PDF document.
    Supports arXiv URLs (e.g., https://arxiv.org/pdf/2506.05296).

    Examples:

        pdf "paper.pdf"

        pdf "https://arxiv.org/pdf/2506.05296" --format markdown

        pdf "document.pdf" --format json --output converted.json

        pdf "https://example.com/manual.pdf" --max-pages 10

        pdf "research.pdf" --format markdown --disable-ai-generation
    """
    # Set up logging
    setup_logger(level=log_level, log_file=log_file)

    try:
        # Initialize configuration and converter
        config = Config()
        converter = PdfConverter(config)

        # Convert PDF
        try:
            logger.info(f"Converting PDF from: {source}")

            converted_content = converter.convert_pdf(
                source=source,
                max_pages=max_pages,
            )

            logger.info(f"Successfully converted PDF: {converted_content.word_count} words, {converted_content.metadata.get('pages', 0)} pages")

        except PdfConversionError as e:
            logger.error(f"Failed to convert PDF: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error during conversion: {e}")
            sys.exit(1)

        # Format output
        if output_format.lower() == 'json':
            # Convert to JSON-serializable format
            output_data = {
                'source': converted_content.url,
                'metadata': {
                    'pages': converted_content.metadata.get('pages', 0),
                    'language': converted_content.metadata.get('language', 'unknown'),
                    'conversion_method': converted_content.metadata.get('conversion_method', 'marker'),
                    'images_found': converted_content.metadata.get('images_found', 0),
                    'conversion_date': converted_content.conversion_date,
                    'word_count': converted_content.word_count,
                    'source_type': converted_content.source_type,
                },
                'content': {
                    'markdown': converted_content.markdown,
                    'text': converter.content_to_text(converted_content),
                }
            }

            output_content = json.dumps(output_data, indent=2)

        elif output_format.lower() == 'markdown':
            # Generate enhanced markdown with metadata and frontmatter
            try:
                metadata_generator = PdfMetadataGenerator(config)

                # Extract PDF metadata
                try:
                    pdf_metadata = metadata_generator.extract_pdf_metadata(converted_content)
                    logger.info(f"Extracted metadata for: {pdf_metadata.title or pdf_metadata.url}")
                except MetadataGenerationError as e:
                    logger.warning(f"Failed to extract PDF metadata: {e}")
                    logger.info("Proceeding with basic markdown output")
                    output_content = converted_content.markdown
                    # Set suggested filename for markdown without metadata
                    if not output:
                        if converted_content.source_type == 'file':
                            base_name = Path(source).stem
                            output = Path(f"{base_name}-converted.md")
                        else:
                            output = Path("converted-pdf.md")
                else:
                    # Generate AI content if enabled and possible
                    ai_content = None
                    if not disable_ai_generation:
                        try:
                            # Get content preview for AI analysis
                            content_preview = converted_content.markdown[:2000] if converted_content.markdown else ""
                            ai_content = metadata_generator.generate_ai_content_for_pdf(pdf_metadata, content_preview)
                            logger.info("Generated AI-powered metadata")
                        except Exception as e:
                            logger.warning(f"Failed to generate AI content: {e}")
                            logger.info("Proceeding with basic metadata")

                    # Generate complete markdown with frontmatter
                    output_content = metadata_generator.generate_markdown_content(
                        pdf_metadata, converted_content.markdown, ai_content
                    )

                    # Set suggested filename if not provided
                    if not output:
                        suggested_filename = metadata_generator.get_suggested_filename(
                            pdf_metadata, ai_content
                        )
                        output = Path(suggested_filename)
                        logger.info(f"Using suggested filename: {output}")

            except Exception as e:
                logger.error(f"Failed to generate markdown with metadata: {e}")
                logger.info("Falling back to plain markdown content")
                output_content = converted_content.markdown
                if not output:
                    if converted_content.source_type == 'file':
                        base_name = Path(source).stem
                        output = Path(f"{base_name}-converted.md")
                    else:
                        output = Path("converted-pdf.md")

        else:  # text format
            output_content = converter.content_to_text(converted_content)

        # Write output
        if output:
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(output_content, encoding='utf-8')
                logger.info(f"Content saved to: {output}")

            except Exception as e:
                logger.error(f"Failed to write output file: {e}")
                sys.exit(1)
        else:
            print(output_content)

        logger.info("PDF conversion completed successfully")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
