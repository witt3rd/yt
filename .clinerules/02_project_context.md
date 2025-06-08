# Project Context: Content Analysis Utilities

## Project Overview

This is a Python 3.13 workspace for content extraction, analysis, and summarization following Unix philosophy - modular tools that can be composed together to process various forms of content.

## Architecture

- **uv workspace** pattern with shared dependencies
- **Modular design**: Independent packages that share common utilities
- **Unix philosophy**: Do one thing well and compose tools together

## Key Modules

### transcript/
- YouTube transcript extraction using youtube-transcript-api
- Support for multiple languages and output formats
- CLI tool: `yt-transcript`

### summarize/
- Universal content summarization using OpenAI GPT or Anthropic Claude
- Multiple summary styles: brief, detailed, bullet_points, key_takeaways, chapter_breakdown, questions
- CLI tool: `summarize`

### common/
- Shared utilities package
- Configuration management with `python-dotenv`
- Logging setup with `loguru`
- Common type definitions

## Current Capabilities

- YouTube transcript extraction with multiple language support
- Universal content summarization (YouTube videos, text files)
- Multiple output formats: text, JSON, timed transcript
- Configurable summary styles and AI providers
- Unix-like CLI tools that can be composed together
- **Auto-save behavior**: Summaries automatically save to `.md` files by default

## Planned Capabilities

- Web content extraction using Firecrawl for clean markdown conversion
- Additional content sources and input formats

## Environment Configuration

Required environment variables in `.env`:
- `OPENAI_API_KEY` - Required for OpenAI summarization
- `ANTHROPIC_API_KEY` - Required for Anthropic summarization
- Optional: `DEFAULT_MODEL`, `LOG_LEVEL`, `MAX_TRANSCRIPT_LENGTH`, `OUTPUT_FORMAT`

## Development Patterns

- Python 3.13 best practices with modern type hints
- NumPy-style docstrings
- Modular CLI design with Click
- Workspace architecture for shared dependencies
- Error handling and logging throughout

## CLI Usage Examples

```bash
# Extract YouTube transcript
uv run --package transcript yt-transcript "VIDEO_ID" --languages en,es

# Summarize content (auto-saves to VIDEO_ID.md)
uv run --package summarize summarize "VIDEO_ID" --style key_takeaways

# Summarize text file (auto-saves to filename.md)
uv run --package summarize summarize document.txt --style questions

# Pipeline composition
uv run --package transcript yt-transcript VIDEO_ID --output transcript.txt
uv run --package summarize summarize transcript.txt --style questions

# Override auto-save with explicit output
uv run --package summarize summarize VIDEO_ID --output custom_summary.txt
```

## Project Structure

```
yt/
├── pyproject.toml              # Workspace root
├── common/                     # Shared utilities
├── transcript/                 # YouTube transcript extraction
└── summarize/                  # Content summarization
