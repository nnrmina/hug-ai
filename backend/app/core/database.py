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
        connect_args = {"connect_timeout": 2} if "postgres" in db_url else {}
        engine_candidate = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
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

    # Sync columns on existing databases without requiring alembic
    try:
        with engine.connect() as conn:
            if engine.dialect.name == "sqlite":
                res = conn.execute(text("PRAGMA table_info(care_events)")).fetchall()
                col_names = {row[1] for row in res}
                if col_names and "status" not in col_names:
                    conn.execute(text("ALTER TABLE care_events ADD COLUMN status VARCHAR(30)"))
                if col_names and "notified_count" not in col_names:
                    conn.execute(text("ALTER TABLE care_events ADD COLUMN notified_count INTEGER DEFAULT 0"))
                conn.commit()
            else:
                conn.execute(text("ALTER TABLE care_events ADD COLUMN IF NOT EXISTS status VARCHAR(30)"))
                conn.execute(text("ALTER TABLE care_events ADD COLUMN IF NOT EXISTS notified_count INTEGER DEFAULT 0"))
                conn.commit()
    except Exception as exc:
        logger.warning("care_events schema sync note: %s", exc)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency providing a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

