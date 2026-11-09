import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.care import HealthReading
from app.services.care_service import CareService
import app.services.care_service as care_mod


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    import app.models.user  # noqa: F401
    import app.models.care  # noqa: F401
    import app.models.reminder  # noqa: F401
    Base.metadata.create_all(bind=engine)
    sess = TestingSession()
    try:
        yield sess
    finally:
        sess.close()
        Base.metadata.drop_all(bind=engine)


def test_sos_status_no_family(db_session):
    svc = CareService(db_session)
    ev, sent = svc.sos("elder-1", lat=40.4, lon=49.8, reason="Yıxıldım")
    assert sent == 0
    assert ev.status == "no_family"
    assert ev.notified_count == 0


def test_sos_status_no_devices(db_session):
    svc = CareService(db_session)
    svc.add_family("elder-1", name="Sevinc", relation="qızım", phone="+994501234567")
    ev, sent = svc.sos("elder-1", lat=40.4, lon=49.8)
    assert sent == 0
    assert ev.status == "no_devices"
    assert ev.notified_count == 0


def test_sos_status_delivered(db_session, monkeypatch):
    monkeypatch.setattr(care_mod, "push_to_family", lambda db, uid, p, **k: 2)
    svc = CareService(db_session)
    svc.add_family("elder-1", name="Sevinc", relation="qızım", phone="+994501234567")
    ev, sent = svc.sos("elder-1", lat=40.4, lon=49.8)
    assert sent == 2
    assert ev.status == "delivered"
    assert ev.notified_count == 2


def test_sos_cancel(db_session):
    svc = CareService(db_session)
    ev = svc.cancel_sos("elder-1")
    assert ev.kind == "sos_cancelled"
    assert ev.status == "cancelled"


def test_critical_health_reading_truthful_reply(db_session, monkeypatch):
    svc = CareService(db_session)
    # 1) When no device is notified (sent = 0)
    monkeypatch.setattr(care_mod, "push_to_family", lambda db, uid, p, **k: 0)
    row, sent = svc.add_reading("elder-1", "bp", 190, 115)
    assert row.level == "critical"
    assert sent == 0
    reply = svc.reading_reply(row, lang="az", notified_count=sent)
    assert "DİQQƏT" in reply
    assert "Ailə cihazlarına bildiriş çatmadı" in reply
    assert "Ailənizə xəbər verdim" not in reply

    # 2) When 1 device is notified (sent = 1)
    monkeypatch.setattr(care_mod, "push_to_family", lambda db, uid, p, **k: 1)
    row2, sent2 = svc.add_reading("elder-1", "bp", 195, 120)
    assert sent2 == 1
    reply2 = svc.reading_reply(row2, lang="az", notified_count=sent2)
    assert "Ailənizə xəbər verdim (1 cihaza çatdı)" in reply2
