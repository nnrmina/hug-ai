import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Tests never call the real Gemini API (a developer's backend/.env key must not leak in);
# Gemini behaviour is covered with an injected fake client in test_gemini_adapter.py.
os.environ["LLM_PROVIDER"] = "rule_based"
os.environ["GEMINI_API_KEY"] = ""
os.environ["LLM_API_KEY"] = ""
os.environ["SCHEDULER_ENABLED"] = "false"  # tests drive CareService.tick() directly
os.environ["VAPID_PUBLIC_KEY"] = ""
os.environ["VAPID_PRIVATE_KEY"] = ""

from app.main import app  # noqa: E402
from app.core.database import Base, get_db  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()



@pytest.fixture(autouse=True)
def _reset_memory():
    from app.services.assistant_service import _ACTION_STORE
    from app.services.session_store import session_store

    _ACTION_STORE.clear()
    session_store.clear()
    yield
