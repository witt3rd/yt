"""Common type definitions for YouTube utilities.

This module defines shared data structures and type hints used across
all YouTube utility packages, following Python 3.13 best practices.
"""

from dataclasses import dataclass


@dataclass
class VideoInfo:
    """Information about a YouTube video.

    Parameters
    ----------
    video_id : str
        YouTube video ID (11-character identifier).
    title : str, optional
        Video title, if available.
    channel : str, optional
        Channel name, if available.
    duration : float, optional
        Video duration in seconds, if available.
    language : str, optional
        Primary language of the video content.

    Examples
    --------
    >>> video = VideoInfo(
    ...     video_id="dQw4w9WgXcQ",
    ...     title="Never Gonna Give You Up",
    ...     channel="RickAstleyVEVO"
    ... )
    >>> video.video_id
    'dQw4w9WgXcQ'
    """
    video_id: str
    title: str | None = None
    channel: str | None = None
    duration: float | None = None
    language: str | None = None

    def __post_init__(self):
        """Validate video_id format after initialization."""
        if len(self.video_id) != 11:
            raise ValueError(f"Invalid video_id format: {self.video_id}")


@dataclass
class TranscriptSegment:
    """A single segment of a video transcript.

    Parameters
    ----------
    text : str
        The transcript text for this segment.
    start : float
        Start time of the segment in seconds.
    duration : float
        Duration of the segment in seconds.
    confidence : float, optional
        Confidence score for this segment (0.0 to 1.0).

    Examples
    --------
    >>> segment = TranscriptSegment(
    ...     text="Hello everyone",
    ...     start=1.5,
    ...     duration=2.3
    ... )
    >>> segment.end_time
    3.8
    """
    text: str
    start: float
    duration: float
    confidence: float | None = None

    @property
    def end_time(self) -> float:
        """Calculate end time of the segment.

        Returns
        -------
        float
            End time in seconds (start + duration).
        """
        return self.start + self.duration

    def __post_init__(self):
        """Validate segment timing after initialization."""
        if self.start < 0:
            raise ValueError(f"Start time cannot be negative: {self.start}")
        if self.duration <= 0:
            raise ValueError(f"Duration must be positive: {self.duration}")
        if self.confidence is not None and not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence must be between 0.0 and 1.0: {self.confidence}")


# Type aliases for commonly used collections
TranscriptData = list[TranscriptSegment]
VideoMetadata = dict[str, str | float | None]
