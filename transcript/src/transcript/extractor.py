"""YouTube transcript extraction functionality.

This module provides the core functionality for extracting transcripts from
YouTube videos using the youtube-transcript-api library, with structured
output and error handling.
"""

import re
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api._api import YouTubeTranscriptApi
from youtube_transcript_api._transcripts import TranscriptList, FetchedTranscript
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
from loguru import logger

from common.types import VideoInfo, TranscriptSegment, TranscriptData
from common.config import Config


class TranscriptExtractor:
    """Extract transcripts from YouTube videos.

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

        # Try parsing as URL and extracting from query params
        try:
            parsed = urlparse(url_or_id)
            if "v" in parse_qs(parsed.query):
                video_id = parse_qs(parsed.query)["v"][0]
                if re.match(r"^[a-zA-Z0-9_-]{11}$", video_id):
                    return video_id
        except Exception:
            pass

        raise ValueError(f"Unable to extract valid YouTube video ID from: {url_or_id}")

    def get_transcript(
        self,
        video_id: str,
        languages: list[str] | None = None,
        auto_generated: bool = True,
    ) -> TranscriptData:
        """Extract transcript for a YouTube video.

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
        try:
            logger.info(f"Fetching transcript for video: {video_id}")
            api = YouTubeTranscriptApi()

            if languages:
                # Try to get transcript in preferred languages
                transcript_list: TranscriptList = api.list(video_id)

                for lang in languages:
                    try:
                        if auto_generated:
                            # Try manual first, then auto-generated
                            try:
                                transcript = (
                                    transcript_list.find_manually_created_transcript([
                                        lang
                                    ])
                                )
                            except NoTranscriptFound:
                                transcript = transcript_list.find_generated_transcript([
                                    lang
                                ])
                        else:
                            # Only manual transcripts
                            transcript = (
                                transcript_list.find_manually_created_transcript([lang])
                            )

                        raw_transcript = transcript.fetch()
                        logger.info(f"Found transcript in language: {lang}")
                        break
                    except NoTranscriptFound:
                        continue
                else:
                    raise NoTranscriptFound(video_id, languages, None)

                # Convert from fetched transcript (has attributes)
                segments = []
                for item in raw_transcript:
                    segment = TranscriptSegment(
                        text=item.text.strip(),
                        start=float(item.start),
                        duration=float(item.duration),
                    )
                    segments.append(segment)
            else:
                # Auto-detect best available transcript
                fetched_transcript: FetchedTranscript = api.fetch(video_id)
                logger.info("Using auto-detected transcript")

                # Convert from fetched transcript (has attributes)
                segments = []
                for item in fetched_transcript:
                    segment = TranscriptSegment(
                        text=item.text.strip(),
                        start=float(item.start),
                        duration=float(item.duration),
                    )
                    segments.append(segment)

            logger.info(f"Extracted {len(segments)} transcript segments")

            # Check length limit
            total_chars = sum(len(seg.text) for seg in segments)
            if total_chars > self.config.max_transcript_length:
                logger.warning(
                    f"Transcript length ({total_chars}) exceeds limit "
                    f"({self.config.max_transcript_length})"
                )

            return segments

        except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable) as e:
            logger.error(f"Failed to get transcript for {video_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting transcript for {video_id}: {e}")
            raise

    def get_video_info(self, video_id: str) -> VideoInfo:
        """Get basic video information.

        Parameters
        ----------
        video_id : str
            YouTube video ID.

        Returns
        -------
        VideoInfo
            Video information structure.

        Notes
        -----
        This method currently only returns the video_id. Additional metadata
        would require the YouTube Data API which needs separate authentication.
        """
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
