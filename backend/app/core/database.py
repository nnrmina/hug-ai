from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import settings
from app.core.logging import logger

Base = declarative_base()


def _build_engine():
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
        )
    try:
        engine_candidate = create_engine(db_url, pool_pre_ping=True)
        with engine_candidate.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine_candidate
    except Exception as exc:
        logger.warning(
            "PostgreSQL connection unavailable (%s). Falling back to local SQLite database for MVP runtime.",
            exc,
        )
        return create_engine(
            settings.FALLBACK_SQLITE_URL,
            connect_args={"check_same_thread": False},
        )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Create all database tables if they do not exist."""
    import app.models.user  # noqa: F401
    import app.models.preference  # noqa: F401
    import app.models.reminder  # noqa: F401
    import app.models.agent_event  # noqa: F401
    import app.models.care  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

