# PDF to Markdown Converter

A Python package for converting PDF documents to markdown using Pandoc as the primary conversion method with Marker library as fallback, with support for arXiv papers, enhanced metadata generation, and AI-powered frontmatter for Obsidian-compatible output.

## Features

- **PDF to Markdown Conversion**: Uses Pandoc for fast, reliable conversion with Marker library as fallback for high-quality results
- **arXiv Support**: Specialized handling for arXiv papers with automatic PDF URL normalization
- **Multiple Sources**: Support for local PDF files and PDF URLs
- **Enhanced Metadata**: AI-powered filename generation, tags, and frontmatter
- **Obsidian Compatible**: Generates markdown with YAML frontmatter for seamless Obsidian integration
- **Robust Error Handling**: Comprehensive error handling with retry logic for network operations
- **Multiple Output Formats**: Text, markdown with frontmatter, and JSON output

## Installation

This package is part of the yt workspace. Install all dependencies with:

```bash
uv sync
```

**Prerequisites:**
- **Pandoc**: The primary conversion engine. Install from [pandoc.org](https://pandoc.org/installing.html)
- **Marker (optional)**: For fallback conversion when Pandoc fails. Install with `uv sync --extra marker`

```bash
# Install with Marker fallback support
uv sync --extra marker
```

## CLI Usage

### Basic Conversion

```bash
# Convert local PDF file
uv run --package pdf pdf paper.pdf

# Convert arXiv paper
uv run --package pdf pdf "https://arxiv.org/pdf/2506.05296"

# Convert any PDF URL
uv run --package pdf pdf "https://example.com/document.pdf"
```

### Output Formats

```bash
# Plain text output (default)
uv run --package pdf pdf paper.pdf

# Markdown with enhanced metadata and frontmatter
uv run --package pdf pdf paper.pdf --format markdown

# JSON output with metadata
uv run --package pdf pdf paper.pdf --format json --output data.json
```

### Advanced Options

```bash
# Limit pages processed
uv run --package pdf pdf paper.pdf --max-pages 10

# Custom output file
uv run --package pdf pdf paper.pdf --output converted.md --format markdown

# Disable AI-powered enhancements
uv run --package pdf pdf paper.pdf --format markdown --disable-ai-generation

# Enable debug logging
uv run --package pdf pdf paper.pdf --log-level DEBUG
```

## Programmatic Usage

```python
from pdf import PdfConverter, PdfMetadataGenerator
from common.config import Config

# Initialize converter
config = Config()
converter = PdfConverter(config)

# Convert PDF
content = converter.convert_pdf("paper.pdf")
print(f"Converted {content.word_count} words from {content.metadata['pages']} pages")

# Generate enhanced markdown
metadata_generator = PdfMetadataGenerator(config)
pdf_metadata = metadata_generator.extract_pdf_metadata(content)

# Generate AI-powered enhancements
ai_content = metadata_generator.generate_ai_content_for_pdf(
    pdf_metadata, content.markdown[:2000]
)

# Create complete markdown with frontmatter
enhanced_markdown = metadata_generator.generate_markdown_content(
    pdf_metadata, content.markdown, ai_content
)
```

## Supported PDF Sources

### Local Files
- Any PDF file on the local filesystem
- Automatic content type detection based on content analysis

### arXiv Papers
- Direct arXiv PDF URLs: `https://arxiv.org/pdf/XXXX.XXXXX`
- Automatic `.pdf` extension handling
- Specialized metadata extraction for research papers

### Web URLs
- Any publicly accessible PDF URL
- Custom headers for compatibility with various servers
- Content type verification

## Output Formats

### Text (Default)
Plain text extraction with markdown formatting removed.

### Markdown with Metadata
Enhanced markdown with YAML frontmatter including:
- Document title and description
- Author information
- Publication date (if available)
- AI-generated tags and categories
- Source information and conversion metadata

Example frontmatter:
```yaml
---
title: "Attention Is All You Need"
description: "We propose a new simple network architecture, the Transformer..."
author: "Ashish Vaswani, Noam Shazeer, Niki Parmar"
publish_date: "2017-06-12"
tags: ["machine-learning", "neural-networks", "attention-mechanism"]
source: pdf
source_type: arxiv
pages: 15
language: en
conversion_date: "2025-01-08"
---
```

### JSON
Structured JSON output with metadata and content:
```json
{
  "source": "https://arxiv.org/pdf/1706.03762.pdf",
  "metadata": {
    "pages": 15,
    "language": "en",
    "conversion_method": "marker",
    "word_count": 7891
  },
  "content": {
    "markdown": "# Attention Is All You Need...",
    "text": "Attention Is All You Need..."
  }
}
```

## Error Handling

The package includes comprehensive error handling for:

- **Network Issues**: Automatic retry with exponential backoff
- **Invalid PDFs**: Content type verification and magic byte checking
- **Conversion Failures**: Graceful fallback and detailed error messages
- **Missing Dependencies**: Clear guidance on missing requirements

## Configuration

Configure via environment variables in `.env`:

```bash
# OpenAI API key for AI-powered enhancements
OPENAI_API_KEY=your_openai_key

# Logging configuration
LOG_LEVEL=INFO
LOG_FILE=pdf.log

# Optional: Maximum pages to process
MAX_PDF_PAGES=100
```

## Integration with Summarize

The PDF package integrates seamlessly with the summarize package:

```bash
# Summarize arXiv paper directly
uv run --package summarize summarize "https://arxiv.org/pdf/2506.05296" --style key_takeaways

# Summarize local PDF
uv run --package summarize summarize paper.pdf --style questions

# All summary styles work with PDFs
uv run --package summarize summarize document.pdf --style chapter_breakdown
```

## Architecture

The package follows the workspace's modular design:

- **`converter.py`**: Core PDF conversion using Pandoc with Marker fallback
- **`metadata.py`**: Metadata extraction and AI enhancement
- **`cli.py`**: Command-line interface
- **Common utilities**: Shared logging, configuration, and AI metadata generation

## Dependencies

### Required
- **Pandoc**: Primary PDF to markdown conversion engine
- **requests**: HTTP client for downloading PDFs
- **tenacity**: Retry logic for robust error handling
- **validators**: URL validation
- **common**: Shared workspace utilities

### Optional
- **marker-pdf**: Fallback conversion for enhanced quality when Pandoc fails

## Performance

Conversion performance varies by method:

**Pandoc (Primary)**:
- **Fast and consistent**: ~2-10 seconds for most PDFs regardless of hardware
- **Cross-platform**: Works identically on all systems
- **Low resource usage**: Minimal CPU and memory requirements

**Marker (Fallback)**:
- **GPU (NVIDIA)**: ~50-100 pages/second
- **Apple Silicon**: ~20-45 pages/second
- **CPU**: ~5-15 pages/second
- **Hardware acceleration**: Automatically uses available GPU when installed

The package tries Pandoc first for speed and reliability, falling back to Marker for enhanced quality when needed.
