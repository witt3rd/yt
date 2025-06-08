# Content Analysis Utilities

A Python 3.13 workspace for content extraction, analysis, and summarization following Unix philosophy - modular tools that can be composed together to process various forms of content.

## Philosophy

This project embodies Unix principles: **do one thing well** and **compose tools together**. Each module is designed to be a focused utility that can work independently or be combined with others through standard input/output patterns.

## Features

### Current Capabilities ✅
- **YouTube Transcript Extraction**: Extract transcripts from YouTube videos with multiple language support
- **Universal Content Summarization**: Summarize any text content using OpenAI GPT or Anthropic Claude models
  - YouTube videos (via transcript extraction)
  - Text files (Markdown, plain text, etc.)
  - Any text content piped through stdin
- **Multiple Output Formats**: Support for text, JSON, and timed transcript formats
- **Configurable Summary Styles**: Brief, detailed, bullet-points, key takeaways, chapter breakdown, and question-oriented analysis
- **Unix-like CLI Tools**: Composable command-line interfaces that can be piped together
- **Modular Design**: Independent packages that share common utilities

### Planned Capabilities 🚧
- **Web Content Extraction**: General web scraping and content extraction using Firecrawl for clean markdown conversion
- **Enhanced Pipeline Support**: Better stdin/stdout integration for true Unix-style composition
- **Additional Content Sources**: Support for more input formats and sources

## Project Structure

This project uses the **uv workspace** pattern with Python 3.13 best practices:

```
yt/
├── pyproject.toml              # Workspace root configuration
├── uv.lock                     # Shared dependency lockfile
├── .env.example                # Environment variables template
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
├── common/                     # Shared utilities package
│   ├── pyproject.toml
│   └── src/
│       └── common/
│           ├── __init__.py
│           ├── config.py       # Configuration management
│           ├── logger.py       # Logging setup
│           └── types.py        # Common type definitions
├── transcript/                 # YouTube transcript extraction
│   ├── pyproject.toml
│   └── src/
│       └── transcript/
│           ├── __init__.py
│           ├── extractor.py    # Core transcript functionality
│           └── cli.py          # Command-line interface
└── summarize/                  # Universal content summarization
    ├── pyproject.toml
    └── src/
        └── summarize/
            ├── __init__.py
            ├── summarizer.py   # AI summarization logic
            └── cli.py          # Command-line interface
```

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager

### Installation

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd yt
   ```

2. **Set up environment variables**:

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Install dependencies**:

   ```bash
   uv sync
   ```

### Configuration

Edit the `.env` file with your API keys:

```env
# Required for summarization
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional settings
DEFAULT_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
MAX_TRANSCRIPT_LENGTH=800000
OUTPUT_FORMAT=text
```

## Usage

### Transcript Extraction

```bash
# Basic transcript extraction
uv run --package transcript yt-transcript "https://youtube.com/watch?v=VIDEO_ID"

# Extract with specific language preferences
uv run --package transcript yt-transcript VIDEO_ID --languages en,es

# Save to file with timed format
uv run --package transcript yt-transcript VIDEO_ID --format timed --output transcript.txt

# JSON output
uv run --package transcript yt-transcript VIDEO_ID --format json --output transcript.json
```

### Content Summarization

```bash
# YouTube video summarization
uv run --package summarize summarize "https://youtube.com/watch?v=VIDEO_ID"

# Text file summarization
uv run --package summarize summarize document.txt --style detailed
uv run --package summarize summarize research.md --style bullet_points

# Different summary styles
uv run --package summarize summarize VIDEO_ID --style key_takeaways
uv run --package summarize summarize VIDEO_ID --style chapter_breakdown
uv run --package summarize summarize VIDEO_ID --style questions  # Question-oriented analysis

# Specify AI provider
uv run --package summarize summarize VIDEO_ID --provider anthropic

# Save summary to file
uv run --package summarize summarize VIDEO_ID --style detailed --output summary.txt

# JSON output with metadata
uv run --package summarize summarize VIDEO_ID --format json --output summary.json
```

### Unix-Style Pipeline Examples

```bash
# Extract transcript and pipe to summarizer (future capability)
uv run --package transcript yt-transcript VIDEO_ID | uv run --package summarize summarize --style brief

# Combine transcript extraction with text processing
uv run --package transcript yt-transcript VIDEO_ID --format text --output transcript.txt
uv run --package summarize summarize transcript.txt --style key_takeaways

# Process multiple videos in sequence
for video in "video1" "video2" "video3"; do
  uv run --package transcript yt-transcript "$video" --output "${video}_transcript.txt"
  uv run --package summarize summarize "${video}_transcript.txt" --style brief --output "${video}_summary.txt"
done
```

### Library Usage

```python
from pathlib import Path
from common.config import Config
from common.logger import setup_logger
from transcript import TranscriptExtractor
from summarize import ContentSummarizer, SummaryStyle

# Set up logging
setup_logger("INFO")

# Initialize components
config = Config()
extractor = TranscriptExtractor(config)
summarizer = ContentSummarizer(config)

# YouTube video processing
video_id = extractor.extract_video_id("https://youtube.com/watch?v=VIDEO_ID")
transcript = extractor.get_transcript(video_id, languages=["en"])
summary = summarizer.summarize_transcript(
    transcript,
    style=SummaryStyle.KEY_TAKEAWAYS,
    provider="openai"
)

# Text file processing
text_summary = summarizer.summarize_text_file(
    Path("document.txt"),
    style=SummaryStyle.DETAILED,
    provider="anthropic"
)

# Direct video summarization
video_summary = summarizer.summarize_video(
    "VIDEO_ID",
    style=SummaryStyle.QUESTIONS,
    languages=["en"]
)

print(summary)
```

## Development

### Python 3.13 Best Practices

This project follows Python 3.13 best practices:

- **Type Hints**: Uses built-in types (`list[str]`, `dict[str, int]`) instead of deprecated `typing` aliases
- **NumPy-Style Docstrings**: Comprehensive documentation with parameters, returns, and examples
- **Configuration Management**: Secure environment variable handling with `python-dotenv`
- **Modern Logging**: Clean, structured logging with `loguru`
- **Minimal Comments**: Focus on "why" rather than "what", with self-documenting code

### Workspace Benefits

- **Shared Dependencies**: Single lockfile ensures consistent versions across packages
- **Cross-Package Dependencies**: `summarize` can easily import and use `transcript` functionality
- **Independent Development**: Each package can be developed, tested, and used independently
- **Consistent Configuration**: Shared configuration and logging across all packages

### Adding New Features

1. **Extend existing packages**: Add new methods to `TranscriptExtractor` or `ContentSummarizer`
2. **Create new packages**: Follow the same structure for additional content utilities (e.g., web scraping)
3. **Shared utilities**: Add common functionality to the `common` package

### Unix Philosophy in Practice

The design allows for powerful compositions:

```bash
# Future: True pipeline support
curl "https://example.com/article" | content-extract | summarize --style brief

# Current: File-based composition
yt-transcript VIDEO_ID --output video.txt
summarize video.txt --style questions --output analysis.txt
```

## API Documentation

### Core Classes

- **`Config`**: Centralized configuration management with environment variable support
- **`TranscriptExtractor`**: YouTube transcript extraction with language detection and URL parsing
- **`ContentSummarizer`**: Universal content summarization with multiple providers, styles, and input sources
- **`SummaryStyle`**: Enumeration of available summary styles (brief, detailed, bullet_points, key_takeaways, chapter_breakdown, questions)
- **`VideoInfo`**: Video metadata structure with validation
- **`TranscriptSegment`**: Individual transcript segment with timing and confidence data

### Supported Input Sources

- **YouTube**: URLs, video IDs with automatic extraction
- **Text Files**: Markdown, plain text, any UTF-8 encoded files
- **Future**: Web pages via Firecrawl, stdin for pipeline integration

### Output Formats

- **Transcript Output**: Plain text, timed text with timestamps, structured JSON
- **Summary Output**: Plain text, JSON with metadata and analysis details
- **Languages**: Auto-detection, manual specification, multi-language preference lists

## Dependencies

### Core Dependencies

- `loguru` - Modern logging
- `python-dotenv` - Environment variable management
- `click` - Command-line interfaces
- `youtube-transcript-api` - YouTube transcript extraction
- `openai` - OpenAI API client
- `anthropic` - Anthropic API client

### Development

- `python>=3.13` - Modern Python features
- `uv` - Fast Python package manager

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes following the Python 3.13 best practices
4. Add tests if applicable
5. Submit a pull request

## Support

For issues, questions, or contributions, please open an issue on the repository.
