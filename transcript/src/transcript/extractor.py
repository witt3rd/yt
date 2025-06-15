"""YouTube transcript extraction functionality using yt-dlp.

This module provides the core functionality for extracting transcripts from
YouTube videos using yt-dlp, with structured output and error handling.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from loguru import logger
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    after_log,
)

from common.types import VideoInfo, TranscriptSegment, TranscriptData
from common.config import Config


class TranscriptExtractorError(Exception):
    """Base exception for transcript extraction errors."""
    pass


class TranscriptsDisabled(TranscriptExtractorError):
    """Raised when transcripts are disabled for the video."""
    pass


class NoTranscriptFound(TranscriptExtractorError):
    """Raised when no transcript is available in requested languages."""
    pass


class VideoUnavailable(TranscriptExtractorError):
    """Raised when the video is not accessible."""
    pass


def _should_retry_extraction(exception: BaseException) -> bool:
    """Determine if transcript extraction should be retried.

    Parameters
    ----------
    exception : BaseException
        The exception that occurred during transcript extraction.

    Returns
    -------
    bool
        True if the operation should be retried, False otherwise.
    """
    # Don't retry permanent errors
    if isinstance(exception, (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable)):
        return False

    # Retry on subprocess errors that might be transient
    if isinstance(exception, subprocess.CalledProcessError):
        return True

    # Retry on network-related errors
    error_msg = str(exception).lower()
    network_error_indicators = [
        "connection error",
        "timeout",
        "network",
        "503",  # Service unavailable
        "502",  # Bad gateway
        "500",  # Internal server error
    ]

    return any(indicator in error_msg for indicator in network_error_indicators)


def _log_retry_attempt(retry_state) -> None:
    """Log retry attempts with context information.

    Parameters
    ----------
    retry_state : RetryCallState
        The current retry state from tenacity.
    """
    if retry_state.attempt_number > 1:
        logger.info(
            f"Retrying transcript extraction (attempt {retry_state.attempt_number}) "
            f"after {retry_state.next_action}: {retry_state.outcome.exception()}"
        )


class TranscriptExtractor:
    """Extract transcripts from YouTube videos using yt-dlp.

    Provides methods to extract transcripts from YouTube videos with support
    for automatic language detection, manual language selection, and structured
    output formats.

    Parameters
    ----------
    config : Config, optional
        Configuration instance. If None, creates a new Config instance.

    Examples
    --------
    >>> extractor = TranscriptExtractor()
    >>> video_id = extractor.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ")
    >>> transcript = extractor.get_transcript(video_id)
    >>> len(transcript)
    42
    """

    def __init__(self, config: Config | None = None):
        """Initialize transcript extractor.

        Parameters
        ----------
        config : Config, optional
            Configuration instance for settings.
        """
        self.config: Config = config or Config()

    def extract_video_id(self, url_or_id: str) -> str:
        """Extract YouTube video ID from URL or return if already an ID.

        Parameters
        ----------
        url_or_id : str
            YouTube URL or video ID.

        Returns
        -------
        str
            11-character YouTube video ID.

        Raises
        ------
        ValueError
            If unable to extract valid video ID.

        Examples
        --------
        >>> extractor = TranscriptExtractor()
        >>> extractor.extract_video_id("https://youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> extractor.extract_video_id("dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        """
        # If already looks like a video ID (11 characters, alphanumeric + underscore/hyphen)
        if re.match(r"^[a-zA-Z0-9_-]{11}$", url_or_id):
            return url_or_id

        # Extract from various YouTube URL formats
        patterns = [
            r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})",
            r"youtube\.com/.*[?&]v=([a-zA-Z0-9_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        # Try using yt-dlp to extract the video ID
        try:
            cmd = ["yt-dlp", "--get-id", url_or_id]
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )
            video_id = result.stdout.strip()
            if video_id and re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
                return video_id
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

        raise ValueError(f"Unable to extract valid YouTube video ID from: {url_or_id}")

    def _parse_vtt_content(self, vtt_content: str) -> TranscriptData:
        """Parse VTT subtitle content into transcript segments.

        Parameters
        ----------
        vtt_content : str
            VTT subtitle file content.

        Returns
        -------
        TranscriptData
            List of transcript segments with timing information.
        """
        segments = []
        lines = vtt_content.split('\n')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip WEBVTT header and metadata
            if line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
                i += 1
                continue

            # Look for timestamp lines
            if '-->' in line:
                # Parse timestamp line
                timestamp_match = re.match(
                    r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})',
                    line
                )

                if timestamp_match:
                    # Convert start time to seconds
                    start_h, start_m, start_s, start_ms = map(int, timestamp_match.groups()[:4])
                    start_time = start_h * 3600 + start_m * 60 + start_s + start_ms / 1000

                    # Convert end time to seconds
                    end_h, end_m, end_s, end_ms = map(int, timestamp_match.groups()[4:])
                    end_time = end_h * 3600 + end_m * 60 + end_s + end_ms / 1000

                    duration = end_time - start_time

                    # Get the text content (next non-empty lines until blank line or next timestamp)
                    i += 1
                    text_lines = []
                    while i < len(lines) and lines[i].strip() and '-->' not in lines[i]:
                        text_line = lines[i].strip()
                        # Remove VTT formatting tags
                        text_line = re.sub(r'<[^>]+>', '', text_line)
                        # Remove positioning and styling
                        text_line = re.sub(r'align:start position:\d+%', '', text_line)
                        if text_line:
                            text_lines.append(text_line)
                        i += 1

                    if text_lines:
                        text = ' '.join(text_lines).strip()
                        if text:
                            segment = TranscriptSegment(
                                text=text,
                                start=start_time,
                                duration=duration,
                            )
                            segments.append(segment)
            else:
                i += 1

        return segments

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(subprocess.CalledProcessError),
        after=_log_retry_attempt,
    )
    def get_transcript(
        self,
        video_id: str,
        languages: list[str] | None = None,
        auto_generated: bool = True,
    ) -> TranscriptData:
        """Extract transcript for a YouTube video using yt-dlp.

        Parameters
        ----------
        video_id : str
            YouTube video ID (11 characters).
        languages : list[str], optional
            Preferred languages in order of preference (e.g., ['en', 'es']).
            If None, uses auto-detection.
        auto_generated : bool, default True
            Whether to accept auto-generated transcripts if manual ones
            are not available.

        Returns
        -------
        TranscriptData
            List of transcript segments with timing information.

        Raises
        ------
        TranscriptsDisabled
            If transcripts are disabled for the video.
        NoTranscriptFound
            If no transcript is available in requested languages.
        VideoUnavailable
            If the video is not accessible.

        Examples
        --------
        >>> extractor = TranscriptExtractor()
        >>> transcript = extractor.get_transcript("dQw4w9WgXcQ", ["en"])
        >>> transcript[0].text
        'Never gonna give you up'
        """
        logger.info(f"Fetching transcript for video: {video_id}")

        # Create temporary directory for subtitle files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Build yt-dlp command
            url = f"https://youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-subs" if auto_generated else "--write-subs",
                "--output", str(temp_path / "%(title)s.%(ext)s"),
                url
            ]

            # Add language preferences if specified
            if languages:
                # Join languages with comma for yt-dlp
                lang_string = ",".join(languages)
                cmd.extend(["--sub-lang", lang_string])

            try:
                logger.debug(f"Running yt-dlp command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=120,
                    cwd=temp_dir
                )
                logger.debug(f"yt-dlp stdout: {result.stdout}")
                logger.debug(f"yt-dlp stderr: {result.stderr}")

            except subprocess.CalledProcessError as e:
                error_output = e.stderr if e.stderr else e.stdout
                logger.error(f"yt-dlp failed with code {e.returncode}: {error_output}")

                # Parse common error conditions
                if "Private video" in error_output or "This video is unavailable" in error_output:
                    raise VideoUnavailable(f"Video {video_id} is unavailable: {error_output}")
                elif "No automatic captions" in error_output or "No subtitles" in error_output:
                    raise NoTranscriptFound(f"No transcripts found for video {video_id}: {error_output}")
                else:
                    raise TranscriptExtractorError(f"yt-dlp extraction failed: {error_output}")

            except subprocess.TimeoutExpired:
                raise TranscriptExtractorError(f"yt-dlp timed out while extracting transcript for {video_id}")

            # Find the downloaded subtitle file
            vtt_files = list(temp_path.glob("*.vtt"))
            if not vtt_files:
                raise NoTranscriptFound(f"No subtitle files were downloaded for video {video_id}")

            # Use the first VTT file found (yt-dlp downloads preferred language first)
            vtt_file = vtt_files[0]
            logger.info(f"Found subtitle file: {vtt_file.name}")

            # Read and parse the VTT content
            try:
                vtt_content = vtt_file.read_text(encoding='utf-8')
                segments = self._parse_vtt_content(vtt_content)

                if not segments:
                    raise NoTranscriptFound(f"No transcript segments found in subtitle file for video {video_id}")

                logger.info(f"Extracted {len(segments)} transcript segments")

                # Check length limit
                total_chars = sum(len(seg.text) for seg in segments)
                if total_chars > self.config.max_transcript_length:
                    logger.warning(
                        f"Transcript length ({total_chars}) exceeds limit "
                        f"({self.config.max_transcript_length})"
                    )

                return segments

            except Exception as e:
                raise TranscriptExtractorError(f"Failed to parse VTT content: {e}")

    def get_video_info(self, video_id: str) -> VideoInfo:
        """Get basic video information using yt-dlp.

        Parameters
        ----------
        video_id : str
            YouTube video ID.

        Returns
        -------
        VideoInfo
            Video information structure.
        """
        try:
            url = f"https://youtube.com/watch?v={video_id}"
            cmd = [
                "yt-dlp",
                "--dump-json",
                "--no-download",
                url
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=30
            )

            video_data = json.loads(result.stdout)

            return VideoInfo(
                video_id=video_id,
                title=video_data.get('title'),
                channel=video_data.get('uploader'),
                duration=video_data.get('duration'),
                language=video_data.get('language')
            )

        except (subprocess.CalledProcessError, json.JSONDecodeError, subprocess.TimeoutExpired):
            # Fallback to basic info
            return VideoInfo(video_id=video_id)

    def transcript_to_text(self, transcript: TranscriptData) -> str:
        """Convert transcript segments to plain text.

        Parameters
        ----------
        transcript : TranscriptData
            List of transcript segments.

        Returns
        -------
        str
            Plain text transcript with segments joined by spaces.

        Examples
        --------
        >>> extractor = TranscriptExtractor()
        >>> segments = [TranscriptSegment("Hello", 0, 1), TranscriptSegment("world", 1, 1)]
        >>> extractor.transcript_to_text(segments)
        'Hello world'
        """
        return " ".join(segment.text for segment in transcript)

    def transcript_to_timed_text(self, transcript: TranscriptData) -> str:
        """Convert transcript segments to timed text format.

        Parameters
        ----------
        transcript : TranscriptData
            List of transcript segments.

        Returns
        -------
        str
            Timed text format with timestamps.

        Examples
        --------
        >>> extractor = TranscriptExtractor()
        >>> segments = [TranscriptSegment("Hello", 0, 1)]
        >>> extractor.transcript_to_timed_text(segments)
        '[00:00] Hello'
        """
        lines = []
        for segment in transcript:
            minutes = int(segment.start // 60)
            seconds = int(segment.start % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            lines.append(f"{timestamp} {segment.text}")
        return "\n".join(lines)
