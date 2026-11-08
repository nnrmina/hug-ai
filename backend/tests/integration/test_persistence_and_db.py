"""Server-restart persistence and database-configuration behaviour."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import database
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from tests.conftest import register


def _client_for(db_url):
    """A fresh engine + session factory + app client, as after a process restart."""
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    return engine


def test_actions_and_security_results_survive_restart(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'restart.db'}"

    engine = _client_for(db_url)
    with TestClient(app) as c:
        headers, _ = register(c)
        action_id = c.post("/api/v1/assistant/message", json={"message": "Sabah saat 10-da dərmanımı xatırlat"}, headers=headers).json()["action_id"]
        analysis = c.post("/api/v1/security/analyze", json={"message": "Kartınız bloklanıb, kodu göndərin"}, headers=headers).json()
    engine.dispose()
    app.dependency_overrides.clear()

    # --- "restart": brand-new engine and sessions on the same database file ---
    engine = _client_for(db_url)
    try:
        with TestClient(app) as c:
            assert c.get(f"/api/v1/assistant/status/{action_id}", headers=headers).json()["status"] == "needs_confirmation"
            assert c.post(f"/api/v1/assistant/confirm/{action_id}", headers=headers).status_code == 200
            assert c.post(f"/api/v1/assistant/confirm/{action_id}", headers=headers).status_code == 409
            assert len(c.get("/api/v1/reminders", headers=headers).json()) == 1
            assert c.get(f"/api/v1/security/result/{analysis['analysis_id']}", headers=headers).json() == analysis
    finally:
        engine.dispose()
        app.dependency_overrides.clear()


def test_unreachable_postgres_does_not_silently_fall_back(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@127.0.0.1:1/nope?connect_timeout=1")
    monkeypatch.setattr(settings, "ALLOW_SQLITE_FALLBACK", False)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    with pytest.raises(database.DatabaseConfigurationError):
        database._build_engine()


def test_explicit_dev_fallback_is_allowed_but_never_in_production(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@127.0.0.1:1/nope?connect_timeout=1")
    monkeypatch.setattr(settings, "FALLBACK_SQLITE_URL", f"sqlite:///{tmp_path / 'fb.db'}")
    monkeypatch.setattr(settings, "ALLOW_SQLITE_FALLBACK", True)
    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    engine = database._build_engine()
    assert engine.dialect.name == "sqlite"
    engine.dispose()

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(database.DatabaseConfigurationError):
        database._build_engine()


def test_sqlite_refused_in_production(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./x.db")
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    with pytest.raises(database.DatabaseConfigurationError):
        database._build_engine()


def test_postgres_url_normalization(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_URL", "postgres://u:p@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://u:p@host:5432/db"
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@host/db")
    assert settings.database_url == "postgresql+psycopg://u:p@host/db"


def test_production_config_validation(monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://u:p@h/db")
    monkeypatch.setattr(settings, "JWT_SECRET", "s" * 40)
    monkeypatch.setattr(settings, "ALLOWED_ORIGINS", "https://hug.example.az")
    monkeypatch.setattr(settings, "STT_PROVIDER", "none")
    settings.validate_for_production()  # valid -> no error

    for field, bad in [("JWT_SECRET", None), ("ALLOWED_ORIGINS", "*"), ("DATABASE_URL", "sqlite:///x.db"), ("STT_PROVIDER", "mock")]:
        original = getattr(settings, field)
        monkeypatch.setattr(settings, field, bad)
        with pytest.raises(RuntimeError):
            settings.validate_for_production()
        monkeypatch.setattr(settings, field, original)
