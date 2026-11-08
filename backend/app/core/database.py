import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.core.config import settings
from app.core.logging import logger

Base = declarative_base()


class DatabaseConfigurationError(RuntimeError):
    """Raised when the configured database cannot be used. Never hidden by a silent fallback."""


def _sqlite_engine(url: str):
    return create_engine(url, connect_args={"check_same_thread": False})


def _build_engine():
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        if settings.is_production:
            raise DatabaseConfigurationError(
                "SQLite yalnız lokal development üçündür. Production-da DATABASE_URL PostgreSQL olmalıdır."
            )
        logger.info("Using local SQLite database (development only).")
        return _sqlite_engine(db_url)

    # Serverless platforms (Vercel) freeze processes between requests: don't keep pooled connections.
    pool_kwargs = {"poolclass": NullPool} if os.environ.get("VERCEL") else {"pool_size": 5, "max_overflow": 5}
    engine = create_engine(db_url, pool_pre_ping=True, **pool_kwargs)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Connected to PostgreSQL.")
        return engine
    except Exception as exc:
        engine.dispose()
        # Never log the URL itself: it contains the password.
        reason = f"{type(exc).__name__}"
        if not settings.is_production and settings.ALLOW_SQLITE_FALLBACK:
            logger.error(
                "!!! PostgreSQL unavailable (%s). ALLOW_SQLITE_FALLBACK=true -> using LOCAL SQLite %s. "
                "Data written now will NOT be in PostgreSQL. !!!",
                reason,
                settings.FALLBACK_SQLITE_URL,
            )
            return _sqlite_engine(settings.FALLBACK_SQLITE_URL)
        raise DatabaseConfigurationError(
            f"PostgreSQL-ə qoşulmaq mümkün olmadı ({reason}). DATABASE_URL-i yoxlayın."
        ) from exc


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create missing tables (existing tables and data are never dropped or altered)."""
    import app.models  # noqa: F401  (registers every model on Base.metadata)

    Base.metadata.create_all(bind=engine)


def check_db_connection() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
