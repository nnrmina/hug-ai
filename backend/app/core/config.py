import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env is found no matter which directory the server is started from
BACKEND_DIR = Path(__file__).resolve().parents[2]


def _get_default_sqlite_url() -> str:
    # Vercel serverless functions have a read-only filesystem except for /tmp
    if os.environ.get("VERCEL"):
        return "sqlite:////tmp/yaxin_ai.db"
    return "sqlite:///./yaxin_ai.db"


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    APP_NAME: str = "YAXIN AI"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # Database configuration (defaults to local SQLite fallback if Postgres is unavailable)
    DATABASE_URL: str = _get_default_sqlite_url()
    FALLBACK_SQLITE_URL: str = _get_default_sqlite_url()

    # AI / LLM Provider settings
    # auto = Gemini when a key is configured, otherwise the built-in rule-based parser
    LLM_PROVIDER: str = "auto"  # auto | gemini | rule_based
    GEMINI_API_KEY: Optional[str] = None
    LLM_API_KEY: Optional[str] = None  # legacy alias for GEMINI_API_KEY
    LLM_MODEL_NAME: str = "gemini-3.5-flash-lite"  # best accuracy/latency on the free tier (benchmarked 2026-11-09)
    # Gemini rejects request deadlines under 10 s (400 INVALID_ARGUMENT); values are clamped
    LLM_TIMEOUT_TEXT_MS: int = 12000
    LLM_TIMEOUT_AUDIO_MS: int = 20000

    # Conversation memory & confirmation tokens
    SESSION_TTL_S: int = 900
    SESSION_MAX_TURNS: int = 6
    ACTION_SIGNING_KEY: Optional[str] = None  # set in production so tokens survive restarts / instances
    ACTION_TOKEN_TTL_S: int = 600

    # Speech-to-Text & Text-to-Speech settings
    STT_PROVIDER: str = "gemini"  # gemini (audio understanding) | browser
    STT_API_KEY: Optional[str] = None
    TTS_PROVIDER: str = "android_native"  # android_native | google
    TTS_API_KEY: Optional[str] = None

    # Localization defaults (Azerbaijan)
    DEFAULT_LANGUAGE: str = "az-AZ"
    DEFAULT_TIMEZONE: str = "Asia/Baku"
    DEFAULT_CURRENCY: str = "AZN"
    DEFAULT_COUNTRY_CODE: str = "+994"

    model_config = SettingsConfigDict(
        env_file=(str(BACKEND_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


    @property
    def gemini_key(self) -> Optional[str]:
        key = (self.GEMINI_API_KEY or self.LLM_API_KEY or "").strip()
        return key or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

