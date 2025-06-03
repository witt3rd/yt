"""Configuration management for YouTube utilities.

This module provides centralized configuration management using environment variables
loaded from .env files with python-dotenv, following Python 3.13 best practices.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger


class Config:
    """Configuration manager for YouTube utilities.

    Loads configuration from environment variables with sensible defaults.
    Automatically loads .env file if present in the project root.

    Parameters
    ----------
    env_file : str or Path, optional
        Path to environment file to load. If None, searches for .env in
        current directory and parent directories.

    Examples
    --------
    >>> config = Config()
    >>> api_key = config.openai_api_key
    >>> config.log_level
    'INFO'
    """

    def __init__(self, env_file: str | Path | None = None):
        """Initialize configuration manager.

        Parameters
        ----------
        env_file : str or Path or None, optional
            Path to environment file to load.
        """
        if env_file:
            load_dotenv(env_file)
        else:
            # Search for .env file in current and parent directories
            load_dotenv(dotenv_path=self._find_env_file())

        logger.debug("Configuration loaded from environment")

    def _find_env_file(self) -> Path | None:
        """Find .env file in current or parent directories.

        Returns
        -------
        Path or None
            Path to .env file if found, None otherwise.
        """
        current = Path.cwd()
        while current != current.parent:
            env_path = current / ".env"
            if env_path.exists():
                return env_path
            current = current.parent
        return None

    @property
    def openai_api_key(self) -> str:
        """OpenAI API key for summarization services."""
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def anthropic_api_key(self) -> str:
        """Anthropic API key for summarization services."""
        return os.getenv("ANTHROPIC_API_KEY", "")

    @property
    def default_model(self) -> str:
        """Default AI model to use for summarization."""
        return os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    @property
    def log_level(self) -> str:
        """Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
        return os.getenv("LOG_LEVEL", "INFO").upper()

    @property
    def log_file(self) -> str | None:
        """Log file path, if file logging is enabled."""
        return os.getenv("LOG_FILE")

    @property
    def max_transcript_length(self) -> int:
        """Maximum transcript length for processing (characters)."""
        try:
            return int(os.getenv("MAX_TRANSCRIPT_LENGTH", "50000"))
        except ValueError:
            logger.warning("Invalid MAX_TRANSCRIPT_LENGTH, using default 50000")
            return 50000

    @property
    def output_format(self) -> str:
        """Default output format (json, text, markdown)."""
        return os.getenv("OUTPUT_FORMAT", "text").lower()

    @property
    def prompts_path(self) -> Path:
        """Path to prompts directory for dynamic prompt loading."""
        prompts_dir = os.getenv("PROMPTS_PATH", "./prompts")
        return Path(prompts_dir)

    def validate(self) -> bool:
        """Validate required configuration values.

        Returns
        -------
        bool
            True if configuration is valid, False otherwise.

        Notes
        -----
        Logs warnings for missing required configuration values.
        """
        valid = True

        if not self.openai_api_key and not self.anthropic_api_key:
            logger.warning(
                "No API keys configured (OPENAI_API_KEY or ANTHROPIC_API_KEY)"
            )
            valid = False

        if self.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger.warning(f"Invalid LOG_LEVEL: {self.log_level}")
            valid = False

        if self.output_format not in ["json", "text", "markdown"]:
            logger.warning(f"Invalid OUTPUT_FORMAT: {self.output_format}")
            valid = False

        return valid
