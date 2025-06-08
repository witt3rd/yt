# YouTube Transcript Extractor

A Python package for extracting transcripts from YouTube videos with support for multiple output formats, including enhanced markdown output with AI-powered metadata generation.

## Features

- Extract transcripts from YouTube videos using video URLs or IDs
- Support for multiple languages with preference ordering
- Multiple output formats: text, timed, JSON, and markdown
- AI-powered filename generation and metadata extraction for markdown format
- Automatic frontmatter generation for Obsidian-compatible notes
- Robust error handling and logging
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
# Required for basic transcript extraction
# (no additional API keys needed for text, timed, json formats)

# Required for markdown format with metadata
YOUTUBE_API_KEY=your_youtube_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Configure logging
LOG_LEVEL=INFO
```

### Getting API Keys

- **YouTube Data API Key**: Get from [Google Cloud Console](https://console.cloud.google.com/)
- **OpenAI API Key**: Get from [OpenAI Platform](https://platform.openai.com/)

## Usage

### Command Line Interface

```bash
# Basic text extraction
uv run --package transcript yt-transcript "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Save to file with specific format
uv run --package transcript yt-transcript dQw4w9WgXcQ --format json --output transcript.json

# Timed transcript with timestamps
uv run --package transcript yt-transcript dQw4w9WgXcQ --format timed

# Enhanced markdown with AI-powered metadata (requires API keys)
uv run --package transcript yt-transcript dQw4w9WgXcQ --format markdown

# Markdown without AI features (basic metadata only)
uv run --package transcript yt-transcript dQw4w9WgXcQ --format markdown --disable-ai-generation

# Language preferences
uv run --package transcript yt-transcript dQw4w9WgXcQ --languages en,es,fr
```

### Output Formats

#### Text Format (Default)
Plain text transcript with all segments joined together.

```
Never gonna give you up Never gonna let you down Never gonna run around and desert you...
```

#### Timed Format
Transcript with timestamps for each segment.

```
[00:12] Never gonna give you up
[00:15] Never gonna let you down
[00:18] Never gonna run around and desert you
```

#### JSON Format
Structured data with detailed segment information.

```json
{
  "video_id": "dQw4w9WgXcQ",
  "segments": [
    {
      "text": "Never gonna give you up",
      "start": 12.5,
      "duration": 2.8,
      "end_time": 15.3
    }
  ],
  "total_segments": 61
}
```

#### Markdown Format
Enhanced markdown with YAML frontmatter for Obsidian compatibility.

```markdown
---
title: Rick Astley - Never Gonna Give You Up (Official Video)
source: YouTube
channel: RickAstleyVEVO
url: https://www.youtube.com/watch?v=dQw4w9WgXcQ
date: 2009-10-25
authors: Rick Astley
tags: [music, pop, 80s, rickroll, official-video]
---

Never gonna give you up Never gonna let you down Never gonna run around and desert you...
```

### Python API

```python
from transcript import TranscriptExtractor, MetadataGenerator

# Initialize extractor
extractor = TranscriptExtractor()

# Extract video ID from URL
video_id = extractor.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ")

# Get transcript
transcript = extractor.get_transcript(video_id, languages=["en"])

# Convert to different formats
text = extractor.transcript_to_text(transcript)
timed = extractor.transcript_to_timed_text(transcript)

# Generate enhanced markdown with metadata
metadata_generator = MetadataGenerator()
video_metadata = metadata_generator.fetch_video_metadata(video_id)
ai_content = metadata_generator.generate_ai_content(video_metadata)
markdown = metadata_generator.generate_markdown_content(video_metadata, text, ai_content)
```

## AI-Powered Features

When using the markdown format with API keys configured, the extractor provides:

### Intelligent Filename Generation
- AI-powered descriptive filenames suitable for Obsidian
- Includes channel name when not in title
- Uses hyphens for compatibility
- Example: `Never-Gonna-Give-You-Up-RickAstleyVEVO.md`

### Automatic Tag Generation
- Relevant tags based on video content
- Optimized for Obsidian's tag system
- Example: `[music, pop, 80s, rickroll, official-video]`

### Author Extraction
- Identifies presenters/authors from video descriptions
- Useful for academic or educational content
- Falls back gracefully when no authors detected

### Rich Metadata
- Video title, channel, publication date
- YouTube URL for reference
- Source attribution

## Error Handling

The package provides graceful degradation:

- **No API keys**: Markdown format falls back to basic transcript with simple filename
- **YouTube API errors**: Uses basic metadata or falls back to text format
- **OpenAI API errors**: Proceeds with basic metadata, no AI-generated content
- **Invalid video IDs**: Clear error messages with validation
- **Transcript unavailable**: Informative error messages

## Architecture

The package follows clean modular design:

- `TranscriptExtractor`: Core transcript extraction functionality
- `MetadataGenerator`: YouTube metadata and AI-powered content generation
- Separate concerns for maintainability
- Comprehensive error handling
- Type hints throughout

## Contributing

1. Follow Python 3.13+ best practices
2. Use NumPy-style docstrings
3. Include type hints for all functions
4. Add tests for new functionality
5. Maintain backward compatibility

## License

This project is part of the YouTube utilities workspace and follows the same licensing terms.
