"""Command-line interface for web content scraping.

This module provides a CLI for scraping web content using Firecrawl
with various output formats and AI-powered enhancements.
"""

import json
import sys
from pathlib import Path

import click
from loguru import logger

from common.config import Config
from common.logger import setup_logger
from .scraper import WebScraper, FirecrawlAPIError
from .metadata import WebMetadataGenerator, MetadataGenerationError, OpenAIError


@click.command()
@click.argument('url', required=True)
@click.option(
    '--output', '-o',
    type=click.Path(path_type=Path),
    help='Output file path. If not provided, prints to stdout or auto-generates filename for markdown format.'
)
@click.option(
    '--format', '-f', 'output_format',
    type=click.Choice(['text', 'markdown', 'json', 'html'], case_sensitive=False),
    default='text',
    help='Output format (default: text).'
)
@click.option(
    '--wait-for',
    type=int,
    help='Milliseconds to wait for dynamic content to load.'
)
@click.option(
    '--timeout',
    type=int,
    help='Maximum time in seconds to wait for the page to load.'
)
@click.option(
    '--screenshot',
    is_flag=True,
    help='Include screenshot in the output (saved as base64).'
)
@click.option(
    '--include-links',
    is_flag=True,
    help='Include extracted links in the output.'
)
@click.option(
    '--include-html',
    is_flag=True,
    help='Include raw HTML content in JSON output.'
)
@click.option(
    '--no-main-content-only',
    is_flag=True,
    help='Include navigation, footers, etc. (by default only main content is extracted).'
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
    url: str,
    output: Path | None,
    output_format: str,
    wait_for: int | None,
    timeout: int | None,
    screenshot: bool,
    include_links: bool,
    include_html: bool,
    no_main_content_only: bool,
    disable_ai_generation: bool,
    log_level: str,
    log_file: Path | None
):
    """Scrape content from web pages using Firecrawl.

    URL should be a complete web URL (e.g., https://example.com).

    Examples:

        scrape "https://example.com"

        scrape "https://example.com" --format json --output content.json

        scrape "https://example.com" --format markdown

        scrape "https://example.com" --wait-for 3000 --screenshot

        scrape "https://example.com" --format markdown --disable-ai-generation
    """
    # Set up logging
    setup_logger(level=log_level, log_file=log_file)

    try:
        # Initialize configuration and scraper
        config = Config()
        scraper = WebScraper(config)

        # Scrape content
        try:
            logger.info(f"Scraping content from: {url}")

            # Determine formats to request from Firecrawl
            formats = ['markdown']  # Always get markdown as base
            if output_format.lower() == 'html' or include_html:
                formats.append('html')

            scraped_content = scraper.scrape_content(
                url=url,
                formats=formats,
                only_main_content=not no_main_content_only,
                wait_for=wait_for,
                timeout=timeout,
                include_screenshot=screenshot,
                include_links=include_links,
            )

            logger.info(f"Successfully scraped content: {scraped_content.word_count} words, status {scraped_content.status_code}")

        except FirecrawlAPIError as e:
            logger.error(f"Failed to scrape content: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error during scraping: {e}")
            sys.exit(1)

        # Format output
        if output_format.lower() == 'json':
            # Convert to JSON-serializable format
            output_data = {
                'url': scraped_content.url,
                'metadata': {
                    'title': scraped_content.metadata.get('title') if scraped_content.metadata else None,
                    'description': scraped_content.metadata.get('description') if scraped_content.metadata else None,
                    'author': scraped_content.metadata.get('author') if scraped_content.metadata else None,
                    'status_code': scraped_content.status_code,
                    'scrape_date': scraped_content.scrape_date,
                    'word_count': scraped_content.word_count,
                },
                'content': {
                    'markdown': scraped_content.markdown,
                    'text': scraper.content_to_text(scraped_content),
                }
            }

            # Add HTML if requested or available
            if scraped_content.html:
                output_data['content']['html'] = scraped_content.html

            # Add screenshot if available
            if scraped_content.screenshot:
                output_data['screenshot'] = scraped_content.screenshot

            output_content = json.dumps(output_data, indent=2)

        elif output_format.lower() == 'html':
            if scraped_content.html:
                output_content = scraped_content.html
            else:
                logger.error("HTML content not available. Use --include-html to request HTML format.")
                sys.exit(1)

        elif output_format.lower() == 'markdown':
            # Generate enhanced markdown with metadata and frontmatter
            try:
                metadata_generator = WebMetadataGenerator(config)

                # Extract web metadata
                try:
                    web_metadata = metadata_generator.extract_web_metadata(scraped_content)
                    logger.info(f"Extracted metadata for: {web_metadata.title or web_metadata.url}")
                except MetadataGenerationError as e:
                    logger.warning(f"Failed to extract web metadata: {e}")
                    logger.info("Proceeding with basic markdown output")
                    output_content = scraped_content.markdown
                    # Set suggested filename for markdown without metadata
                    if not output:
                        parsed_url = scraper.validate_url(url)
                        domain = parsed_url.split('/')[2].replace('www.', '')
                        output = Path(f"scraped-{domain}.md")
                else:
                    # Generate AI content if enabled and possible
                    ai_content = None
                    if not disable_ai_generation:
                        try:
                            # Get content preview for AI analysis
                            content_preview = scraped_content.markdown[:2000] if scraped_content.markdown else ""
                            ai_content = metadata_generator.generate_ai_content(web_metadata, content_preview)
                            logger.info("Generated AI-powered metadata")
                        except OpenAIError as e:
                            logger.warning(f"Failed to generate AI content: {e}")
                            logger.info("Proceeding with basic metadata")

                    # Generate complete markdown with frontmatter
                    output_content = metadata_generator.generate_markdown_content(
                        web_metadata, scraped_content.markdown, ai_content
                    )

                    # Set suggested filename if not provided
                    if not output:
                        suggested_filename = metadata_generator.get_suggested_filename(
                            web_metadata, ai_content
                        )
                        output = Path(suggested_filename)
                        logger.info(f"Using suggested filename: {output}")

            except Exception as e:
                logger.error(f"Failed to generate markdown with metadata: {e}")
                logger.info("Falling back to plain markdown content")
                output_content = scraped_content.markdown
                if not output:
                    try:
                        parsed_url = scraper.validate_url(url)
                        domain = parsed_url.split('/')[2].replace('www.', '')
                        output = Path(f"scraped-{domain}.md")
                    except Exception:
                        output = Path("scraped-content.md")

        else:  # text format
            output_content = scraper.content_to_text(scraped_content)

        # Write output
        if output:
            try:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(output_content, encoding='utf-8')
                logger.info(f"Content saved to: {output}")

                # Log screenshot info if included
                if screenshot and scraped_content.screenshot:
                    logger.info("Screenshot included in output as base64 data")

            except Exception as e:
                logger.error(f"Failed to write output file: {e}")
                sys.exit(1)
        else:
            print(output_content)

        logger.info("Web scraping completed successfully")

    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
