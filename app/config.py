"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # LLM Configuration
    primary_llm: str = "gemini"  # "gemini" or "groq"
    llm_max_retries: int = 3
    llm_timeout_seconds: int = 120
    gemini_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    # TTS Configuration
    male_voice: str = "en-US-AndrewMultilingualNeural"
    female_voice: str = "en-US-AvaMultilingualNeural"
    male_voice_fallback: str = "en-US-AndrewNeural"
    female_voice_fallback: str = "en-US-EmmaMultilingualNeural"
    tts_max_concurrent: int = 5
    tts_batch_size: int = 10
    tts_max_retries: int = 3

    # Audio Configuration
    speaker_pause_ms: int = 350
    continuation_pause_ms: int = 150
    crossfade_ms: int = 50
    target_dbfs: float = -16.0
    output_bitrate: str = "192k"
    sample_rate: int = 44100

    # File Paths
    base_dir: Path = Path(".").resolve()
    uploads_dir: Path = Path("uploads")
    output_dir: Path = Path("output")
    temp_dir: Path = Path("temp")

    # App Configuration
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = False

    # Pipeline Configuration
    max_review_iterations: int = 1
    min_quality_score: float = 6.0
    max_podcast_length_minutes: int = 120

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.uploads_dir, self.output_dir, self.temp_dir]:
            path = self.base_dir / d
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()
