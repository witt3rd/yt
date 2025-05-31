# YouTube (YT) Utilities

A Python 3.13 workspace for YouTube-related utilities including transcript extraction and AI-powered summarization.

## Features

- **Transcript Extraction**: Extract transcripts from YouTube videos with multiple language support
- **AI Summarization**: Summarize video content using OpenAI GPT or Anthropic Claude models
- **Multiple Output Formats**: Support for text, JSON, and timed transcript formats
- **Configurable Styles**: Brief, detailed, bullet-points, key takeaways, and chapter breakdown summaries
- **CLI Tools**: Easy-to-use command-line interfaces for both transcript extraction and summarization
- **Modular Design**: Clean workspace structure with shared utilities and independent packages

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
└── summarize/                  # YouTube content summarization
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
MAX_TRANSCRIPT_LENGTH=50000
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

### Video Summarization

```bash
# Basic summarization
uv run --package summarize yt-summarize "https://youtube.com/watch?v=VIDEO_ID"

# Different summary styles
uv run --package summarize yt-summarize VIDEO_ID --style detailed
uv run --package summarize yt-summarize VIDEO_ID --style bullet_points
uv run --package summarize yt-summarize VIDEO_ID --style key_takeaways
uv run --package summarize yt-summarize VIDEO_ID --style chapter_breakdown

# Specify AI provider
uv run --package summarize yt-summarize VIDEO_ID --provider anthropic

# Save summary to file
uv run --package summarize yt-summarize VIDEO_ID --style detailed --output summary.txt

# JSON output with metadata
uv run --package summarize yt-summarize VIDEO_ID --format json --output summary.json
```

### Library Usage

```python
from common.config import Config
from common.logger import setup_logger
from transcript import TranscriptExtractor
from summarize import VideoSummarizer, SummaryStyle

# Set up logging
setup_logger("INFO")

# Initialize components
config = Config()
extractor = TranscriptExtractor(config)
summarizer = VideoSummarizer(config)

# Extract transcript
video_id = extractor.extract_video_id("https://youtube.com/watch?v=VIDEO_ID")
transcript = extractor.get_transcript(video_id, languages=["en"])

# Generate summary
summary = summarizer.summarize_transcript(
    transcript,
    style=SummaryStyle.KEY_TAKEAWAYS,
    provider="openai"
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

1. **Extend existing packages**: Add new methods to `TranscriptExtractor` or `VideoSummarizer`
2. **Create new packages**: Follow the same structure for additional YouTube utilities
3. **Shared utilities**: Add common functionality to the `common` package

## API Documentation

### Core Classes

- **`Config`**: Centralized configuration management with environment variable support
- **`TranscriptExtractor`**: YouTube transcript extraction with language detection
- **`VideoSummarizer`**: AI-powered summarization with multiple providers and styles
- **`VideoInfo`**: Video metadata structure
- **`TranscriptSegment`**: Individual transcript segment with timing

### Supported Formats

- **Input**: YouTube URLs, video IDs
- **Transcript Output**: Plain text, timed text, JSON
- **Summary Output**: Plain text, JSON with metadata
- **Languages**: Auto-detection or manual specification

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
