import os
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # Database configuration.
    # Production must use PostgreSQL. SQLite is only for local development and is never used
    # silently: falling back from an unreachable PostgreSQL requires ALLOW_SQLITE_FALLBACK=true
    # outside production.
    DATABASE_URL: str = _get_default_sqlite_url()
    FALLBACK_SQLITE_URL: str = _get_default_sqlite_url()
    ALLOW_SQLITE_FALLBACK: bool = False

    # Access control
    # If API_KEY is set, every /api/v1 request (except health) must send header "X-API-Key".
    API_KEY: Optional[str] = None
    # JWT signing secret (required in production, >= 32 chars). In development a random secret is
    # generated once and kept in backend/.dev_jwt_secret (gitignored).
    JWT_SECRET: Optional[str] = None
    JWT_EXPIRE_DAYS: int = 180
    # Comma-separated list of allowed CORS origins. "*" is rejected in production.
    ALLOWED_ORIGINS: str = (
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:8080,http://127.0.0.1:8080"
    )

    # AI / LLM Provider settings
    LLM_PROVIDER: str = "rule_based"  # rule_based (only implemented provider)
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL_NAME: str = "gpt-4o-mini"

    # Optional hug-ml intent classifier service (e.g. http://localhost:8001). Empty = disabled.
    HUG_ML_URL: Optional[str] = None
    HUG_ML_TIMEOUT_SECONDS: float = 1.5
    HUG_ML_MIN_CONFIDENCE: float = 0.6

    # Speech-to-Text settings
    # none   -> server-side STT disabled (clients do on-device / browser STT and send text)
    # openai -> OpenAI Whisper API, requires STT_API_KEY (or OPENAI_API_KEY)
    # mock   -> test mode: audio bytes containing UTF-8 text are treated as the transcript
    STT_PROVIDER: str = "none"
    STT_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    STT_MAX_AUDIO_BYTES: int = 10 * 1024 * 1024
    TTS_PROVIDER: str = "android_native"  # android_native | google
    TTS_API_KEY: Optional[str] = None

    # Pending confirmation lifetime
    ACTION_TTL_MINUTES: int = 10

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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.strip().lower() in ("production", "prod")

    @property
    def database_url(self) -> str:
        """DATABASE_URL normalized for SQLAlchemy + psycopg3 (hosted providers give postgres://...)."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url

    def validate_for_production(self) -> None:
        """Fail fast on unsafe production configuration instead of running insecurely."""
        if not self.is_production:
            return
        problems = []
        if self.database_url.startswith("sqlite"):
            problems.append("DATABASE_URL PostgreSQL olmalıdır (SQLite production-da qadağandır).")
        if not self.JWT_SECRET or len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET təyin edilməyib və ya 32 simvoldan qısadır.")
        if "*" in self.allowed_origins_list:
            problems.append("ALLOWED_ORIGINS='*' production-da qadağandır; frontend domenini yazın.")
        if self.STT_PROVIDER.lower() == "mock":
            problems.append("STT_PROVIDER=mock production-da qadağandır.")
        if problems:
            raise RuntimeError("Təhlükəsiz olmayan production konfiqurasiyası: " + " ".join(problems))

    @property
    def allowed_origins_list(self) -> List[str]:
        origins = [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]
        return origins or ["*"]

    @property
    def stt_api_key(self) -> Optional[str]:
        return self.STT_API_KEY or self.OPENAI_API_KEY


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
