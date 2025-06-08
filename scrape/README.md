# Web Content Scraper

A Python package for extracting content from web pages using Firecrawl with support for multiple output formats, including enhanced markdown output with AI-powered metadata generation.

## Features

- Extract content from any web page using Firecrawl's robust scraping engine
- Support for dynamic JavaScript-heavy websites (SPAs, React apps, etc.)
- Multiple output formats: text, markdown, JSON, and HTML
- AI-powered filename generation and metadata extraction for markdown format
- Automatic frontmatter generation for Obsidian-compatible notes
- Advanced Firecrawl features: screenshots, link extraction, custom wait times
- Robust error handling with retry logic for network issues
- Clean modular architecture

## Installation

```bash
# Install dependencies
uv sync

# Install in development mode
uv pip install -e .
```

## Environment Configuration

Copy `.env.example` to `.env` and configure the required API keys:

```bash
# Required for web scraping
FIRECRAWL_API_KEY=your_firecrawl_api_key_here

# Required for markdown format with AI metadata
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Configure logging
LOG_LEVEL=INFO
MAX_CONTENT_LENGTH=500000
```

### Getting API Keys

- **Firecrawl API Key**: Get from [Firecrawl Dashboard](https://firecrawl.dev/)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/)

## Usage

### Command Line Interface

```bash
# Basic content extraction
uv run --package scrape scrape "https://example.com"

# Save to file with specific format
uv run --package scrape scrape "https://example.com" --format json --output content.json

# Enhanced markdown with AI-powered metadata (requires API keys)
uv run --package scrape scrape "https://example.com" --format markdown

# Markdown without AI features (basic metadata only)
uv run --package scrape scrape "https://example.com" --format markdown --disable-ai-generation

# Advanced Firecrawl features
uv run --package scrape scrape "https://spa-website.com" --wait-for 3000 --screenshot

# Include HTML content
uv run --package scrape scrape "https://example.com" --format html --output page.html
```

### Output Formats

#### Text Format (Default)
Plain text extracted from the web page with markdown formatting removed.

```
Introduction to Web Scraping

Web scraping is the process of automatically extracting data from websites...
```

#### Markdown Format
Clean markdown content with optional AI-powered YAML frontmatter.

```markdown
---
title: Introduction to Web Scraping with Python
source: web
url: https://example.com/web-scraping-guide
domain: example.com
scrape_date: 2024-01-15
authors: John Developer
tags: [python, web-scraping, automation, tutorial]
word_count: 1250
content_type: tutorial
---

# Introduction to Web Scraping with Python

Web scraping is the process of automatically extracting data from websites...
```

#### JSON Format
Structured data with complete metadata and content in multiple formats.

```json
{
  "url": "https://example.com/web-scraping-guide",
  "metadata": {
    "title": "Introduction to Web Scraping with Python",
    "description": "Learn how to scrape websites using Python",
    "author": "John Developer",
    "status_code": 200,
    "scrape_date": "2024-01-15T10:30:00Z",
    "word_count": 1250
  },
  "content": {
    "markdown": "# Introduction to Web Scraping...",
    "text": "Introduction to Web Scraping..."
  }
}
```

#### HTML Format
Raw HTML content for debugging or processing.

```html
<!DOCTYPE html>
<html>
<head>
    <title>Introduction to Web Scraping</title>
</head>
<body>
    <h1>Introduction to Web Scraping with Python</h1>
    <p>Web scraping is the process...</p>
</body>
</html>
```

### Python API

```python
from scrape import WebScraper, WebMetadataGenerator
from common.config import Config

# Initialize scraper
config = Config()
scraper = WebScraper(config)

# Scrape content
content = scraper.scrape_content("https://example.com")

# Convert to different formats
text = scraper.content_to_text(content)
markdown = scraper.content_to_markdown(content)

# Generate enhanced markdown with metadata
metadata_generator = WebMetadataGenerator(config)
web_metadata = metadata_generator.extract_web_metadata(content)
ai_content = metadata_generator.generate_ai_content(web_metadata, content.markdown[:2000])
enhanced_markdown = metadata_generator.generate_markdown_content(web_metadata, content.markdown, ai_content)
```

## AI-Powered Features

When using the markdown format with API keys configured, the scraper provides:

### Intelligent Filename Generation
- AI-powered descriptive filenames suitable for Obsidian
- Includes domain name when helpful for context
- Uses hyphens for compatibility
- Example: `Web-Scraping-Python-Guide-Real-Python.md`

### Automatic Tag Generation
- Relevant tags based on page content and context
- Technology tags (python, javascript, react, etc.)
- Topic tags (web-scraping, automation, tutorial, etc.)
- Content type tags (guide, documentation, article, etc.)
- Optimized for Obsidian's tag system

### Author Extraction
- Identifies authors from page metadata and content
- Extracts from bylines, author sections, and attribution
- Useful for academic or professional content
- Falls back gracefully when no authors detected

### Content Categorization
- AI-determined content types (tutorial, article, documentation, etc.)
- Based on URL patterns and content analysis
- Helps with content organization and filtering

### Rich Metadata
- Page title, description, and publication date
- Domain and URL for reference
- Word count and scrape date
- Source attribution

## Firecrawl Features

### Dynamic Content Support
- Handles JavaScript-heavy websites (SPAs, React apps)
- Configurable wait times for dynamic content loading
- Custom actions (click, scroll, wait) before scraping

### Anti-Bot Mechanisms
- Built-in proxy rotation and anti-bot bypass
- Handles CAPTCHAs and rate limiting
- Automatic retries for failed requests

### Multiple Content Types
- Extracts text from PDFs, DOCX files, and images
- Supports various media formats
- Clean content extraction with noise filtering

## Error Handling

The package provides graceful degradation:

- **No API keys**: Markdown format falls back to basic content with simple filename
- **Firecrawl API errors**: Clear error messages with validation and retry logic
- **OpenAI API errors**: Proceeds with basic metadata, no AI-generated content
- **Invalid URLs**: URL validation with helpful error messages
- **Network issues**: Automatic retries with exponential backoff
- **Content unavailable**: Informative error messages with troubleshooting guidance

## Architecture

The package follows clean modular design:

- `WebScraper`: Core content extraction functionality using Firecrawl
- `WebMetadataGenerator`: Web metadata extraction and AI-powered content generation
- Separate concerns for maintainability
- Comprehensive error handling with retry logic
- Type hints throughout

## Advanced Usage

### Custom Firecrawl Options

```bash
# Wait for dynamic content
uv run --package scrape scrape "https://spa-website.com" --wait-for 5000

# Include screenshot
uv run --package scrape scrape "https://example.com" --screenshot --format json

# Extract links
uv run --package scrape scrape "https://example.com" --include-links

# Include navigation and footers (not just main content)
uv run --package scrape scrape "https://example.com" --no-main-content-only

# Custom timeout
uv run --package scrape scrape "https://slow-website.com" --timeout 30
```

### Batch Processing

```python
from scrape import WebScraper
from common.config import Config

scraper = WebScraper(Config())
urls = [
    "https://example.com/article1",
    "https://example.com/article2",
    "https://example.com/article3"
]

for url in urls:
    try:
        content = scraper.scrape_content(url)
        print(f"Scraped {content.word_count} words from {url}")
    except Exception as e:
        print(f"Failed to scrape {url}: {e}")
```

### Integration with Other Packages

```bash
# Scrape and summarize workflow
uv run --package scrape scrape "https://example.com/article" --format markdown --output article.md
uv run --package summarize summarize article.md --style key_takeaways
```

## Contributing

1. Follow Python 3.13+ best practices
2. Use NumPy-style docstrings
3. Include type hints for all functions
4. Add tests for new functionality
5. Maintain backward compatibility

## License

This project is part of the content analysis utilities workspace and follows the same licensing terms.
