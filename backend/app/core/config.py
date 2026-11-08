from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    APP_NAME: str = "YAXIN AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # Database configuration (defaults to local SQLite fallback if Postgres is unavailable)
    DATABASE_URL: str = "sqlite:///./yaxin_ai.db"
    FALLBACK_SQLITE_URL: str = "sqlite:///./yaxin_ai.db"

    # AI / LLM Provider settings
    LLM_PROVIDER: str = "rule_based"  # rule_based | openai | gemini | llama
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: str = "gpt-4o-mini"

    # Speech-to-Text & Text-to-Speech settings
    STT_PROVIDER: str = "whisper"  # whisper | google | android_native
    STT_API_KEY: Optional[str] = None
    TTS_PROVIDER: str = "android_native"  # android_native | google
    TTS_API_KEY: Optional[str] = None

    # Localization defaults (Azerbaijan)
    DEFAULT_LANGUAGE: str = "az-AZ"
    DEFAULT_TIMEZONE: str = "Asia/Baku"
    DEFAULT_CURRENCY: str = "AZN"
    DEFAULT_COUNTRY_CODE: str = "+994"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

