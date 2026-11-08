from datetime import datetime, timedelta, timezone
import uuid

import jwt
import pytest

from app.core.config import settings
from tests.conftest import register

WAV_HEADER = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 32


def _message(client, text, headers):
    return client.post("/api/v1/assistant/message", json={"message": text}, headers=headers)


# --------------------------------------------------------------------------- basics
def test_root_and_health(client):
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "text/html" in r_root.headers["content-type"]
    assert r_root.headers["x-content-type-options"] == "nosniff"

    assert client.get("/health").json()["status"] == "healthy"
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"


# --------------------------------------------------------------------------- auth
def test_endpoints_require_token(client):
    assert client.post("/api/v1/assistant/message", json={"message": "Salam"}).status_code == 401
    assert client.get("/api/v1/reminders").status_code == 401
    assert client.get("/api/v1/users/me").status_code == 401
    assert client.post("/api/v1/security/analyze", json={"message": "test"}).status_code == 401
    bad = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/v1/reminders", headers=bad).status_code == 401


def test_forged_and_expired_tokens_rejected(client):
    _, user_id = register(client)
    forged = jwt.encode(
        {"sub": user_id, "iss": "yaxin-ai", "typ": "device", "iat": 0, "exp": 9999999999},
        "wrong-secret-" + "y" * 40,
        algorithm="HS256",
    )
    assert client.get("/api/v1/reminders", headers={"Authorization": f"Bearer {forged}"}).status_code == 401

    expired = jwt.encode(
        {"sub": user_id, "iss": "yaxin-ai", "typ": "device", "iat": 0, "exp": 1},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    assert client.get("/api/v1/reminders", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_client_sent_user_id_is_ignored(client):
    headers_a, user_a = register(client)
    headers_b, user_b = register(client)
    # B tries to create a reminder "for A" and to list A's reminders by passing A's id.
    res = client.post(
        "/api/v1/reminders",
        headers=headers_b,
        json={"title": "Saxta", "scheduled_at": "2026-12-01T10:00:00+04:00", "user_id": user_a},
    )
    assert res.status_code == 201
    assert res.json()["user_id"] == user_b
    assert client.get("/api/v1/reminders", params={"user_id": user_a}, headers=headers_a).json() == []


def test_device_secret_reauth_keeps_same_account(client, db_session):
    first = client.post("/api/v1/auth/device", json={}).json()
    assert first["device_secret"]
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    client.post("/api/v1/reminders", headers=headers, json={"title": "Mənim", "scheduled_at": "2026-12-01T10:00:00+04:00"})

    # Token lost/expired -> re-authenticate with the device secret -> same account, same data.
    again = client.post("/api/v1/auth/device", json={"user_id": first["user_id"], "device_secret": first["device_secret"]})
    assert again.status_code == 200
    assert again.json()["user_id"] == first["user_id"]
    assert again.json()["device_secret"] is None
    new_headers = {"Authorization": f"Bearer {again.json()['access_token']}"}
    assert [r["title"] for r in client.get("/api/v1/reminders", headers=new_headers).json()] == ["Mənim"]

    # Wrong secret / someone else's id -> rejected
    assert client.post("/api/v1/auth/device", json={"user_id": first["user_id"], "device_secret": "guess"}).status_code == 401
    assert client.post("/api/v1/auth/device", json={"user_id": first["user_id"]}).status_code == 401

    # Only a hash is stored
    from app.models.device_credential import DeviceCredential
    assert db_session.get(DeviceCredential, first["user_id"]).secret_hash != first["device_secret"]


def test_legacy_account_can_be_claimed_only_once(client, db_session):
    from app.repositories.user_repository import UserRepository

    legacy = str(uuid.uuid4())
    UserRepository(db_session).get_or_create_default_user(legacy)

    _, first = register(client, legacy_user_id=legacy)
    _, second = register(client, legacy_user_id=legacy)
    assert first == legacy
    assert second != legacy  # an attacker who learns the UUID later gets a fresh empty account


# --------------------------------------------------------------------------- assistant
def test_assistant_call_and_confirmation_flow(client, auth):
    data = _message(client, "Qızıma zəng et", auth).json()
    assert data["intent"] == "MAKE_CALL"
    assert data["status"] == "needs_confirmation"
    action_id = data["action_id"]

    assert client.get(f"/api/v1/assistant/status/{action_id}", headers=auth).json()["status"] == "needs_confirmation"
    confirmed = client.post(f"/api/v1/assistant/confirm/{action_id}", headers=auth).json()
    assert confirmed["status"] == "completed"
    assert confirmed["action_data"]["authorized_execution"] == "OPEN_DIALER"


def test_other_user_cannot_see_or_confirm_action(client, auth):
    other, _ = register(client)
    action_id = _message(client, "Qızıma zəng et", auth).json()["action_id"]
    assert client.get(f"/api/v1/assistant/status/{action_id}", headers=other).status_code == 404
    assert client.post(f"/api/v1/assistant/confirm/{action_id}", headers=other).status_code == 404
    assert client.post(f"/api/v1/assistant/cancel/{action_id}", headers=other).status_code == 404
    # The owner can still confirm it.
    assert client.post(f"/api/v1/assistant/confirm/{action_id}", headers=auth).status_code == 200


def test_message_validation(client, auth):
    assert _message(client, "   ", auth).status_code == 422
    assert _message(client, "a" * 2001, auth).status_code == 422
    assert client.post("/api/v1/assistant/message", json={}, headers=auth).status_code == 422


def test_rejected_action_cannot_be_confirmed(client, auth):
    data = _message(client, "Karta pul köçür", auth).json()
    assert data["status"] == "rejected"
    assert client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth).status_code == 409


def test_clarification_and_info_cannot_be_confirmed(client, auth):
    for text in ("blablabla", "Sən kimsən?"):
        data = _message(client, text, auth).json()
        assert data["status"] in ("needs_clarification", "completed")
        assert client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth).status_code == 409


def test_double_confirm_creates_single_reminder(client, auth):
    data = _message(client, "Sabah saat 9-da dərmanımı xatırlat", auth).json()
    assert data["intent"] == "CREATE_REMINDER"
    assert "saat 09:00" in data["response"]
    # Nothing is created before confirmation.
    assert client.get("/api/v1/reminders", headers=auth).json() == []
    first = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth)
    second = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth)
    assert first.status_code == 200
    assert second.status_code == 409
    reminders = client.get("/api/v1/reminders", headers=auth).json()
    assert len(reminders) == 1 and reminders[0]["title"] == "Dərman qəbulu"


def test_cancelled_action_cannot_be_confirmed(client, auth):
    data = _message(client, "Anama zəng et", auth).json()
    assert client.post(f"/api/v1/assistant/cancel/{data['action_id']}", headers=auth).status_code == 200
    assert client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth).status_code == 409


def test_expired_action_cannot_be_confirmed(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "ACTION_TTL_MINUTES", -1)
    data = _message(client, "Qızıma zəng et", auth).json()
    assert client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth).status_code == 404


def test_emergency_call_flow(client, auth):
    data = _message(client, "Ürəyim ağrıyır, təcili yardım çağır", auth).json()
    assert data["intent"] == "EMERGENCY_CALL"
    assert data["action_data"]["phone_number"] == "103"
    confirmed = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=auth).json()
    assert confirmed["action_data"]["authorized_execution"] == "OPEN_DIALER"


# --------------------------------------------------------------------------- reminders
def test_reminders_crud_and_ownership(client, auth):
    other, _ = register(client)
    create_res = client.post(
        "/api/v1/reminders",
        headers=auth,
        json={
            "title": "Dərman qəbulu",
            "description": "Axşam yeməyindən sonra",
            "scheduled_at": "2026-11-09T20:00:00+04:00",
            "timezone": "Asia/Baku",
        },
    )
    assert create_res.status_code == 201
    rem_id = create_res.json()["id"]

    assert client.get(f"/api/v1/reminders/{rem_id}", headers=other).status_code == 404
    assert client.patch(f"/api/v1/reminders/{rem_id}", headers=other, json={"status": "cancelled"}).status_code == 404
    assert client.delete(f"/api/v1/reminders/{rem_id}", headers=other).status_code == 404
    assert client.get("/api/v1/reminders", headers=other).json() == []

    assert client.get(f"/api/v1/reminders/{rem_id}", headers=auth).json()["title"] == "Dərman qəbulu"
    patch_res = client.patch(f"/api/v1/reminders/{rem_id}", headers=auth, json={"status": "completed"})
    assert patch_res.status_code == 200 and patch_res.json()["status"] == "completed"
    assert client.delete(f"/api/v1/reminders/{rem_id}", headers=auth).status_code == 204
    assert client.get(f"/api/v1/reminders/{rem_id}", headers=auth).status_code == 404


def test_reminder_validation(client, auth):
    base = {"scheduled_at": "2026-12-01T10:00:00+04:00"}
    assert client.post("/api/v1/reminders", headers=auth, json={**base, "title": "   "}).status_code == 422
    assert client.post("/api/v1/reminders", headers=auth, json={**base, "title": "x", "timezone": "<script>"}).status_code == 422
    assert client.post("/api/v1/reminders", headers=auth, json={"title": "x", "scheduled_at": "dünən"}).status_code == 422
    naive = client.post("/api/v1/reminders", headers=auth, json={"title": "x", "scheduled_at": "2026-12-01T10:00:00"})
    assert naive.status_code == 201


# --------------------------------------------------------------------------- security
def test_security_analyze_and_ownership(client, auth):
    other, _ = register(client)
    res = client.post(
        "/api/v1/security/analyze",
        headers=auth,
        json={"message": "Bank hesabınız bloklanıb. Linkə daxil olun və kart məlumatlarını yazın: http://bit.ly/scam"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["risk_level"] == "high"
    assert {"urgency", "credential_request", "suspicious_link"} <= set(body["indicators"])

    assert client.get(f"/api/v1/security/result/{body['analysis_id']}", headers=auth).json() == body
    assert client.get(f"/api/v1/security/result/{body['analysis_id']}", headers=other).status_code == 404


def test_security_raw_message_not_stored(client, auth, db_session):
    from app.models.security_analysis import SecurityAnalysis

    secret_text = "Kodum 4821, kart 4169 1234 5678 9012"
    client.post("/api/v1/security/analyze", headers=auth, json={"message": secret_text})
    row = db_session.query(SecurityAnalysis).one()
    stored = " ".join(str(v) for v in (row.explanation, row.recommendation, row.indicators))
    assert "4169" not in stored and "4821" not in stored


# --------------------------------------------------------------------------- users
def test_user_and_preferences_endpoints(client, auth):
    me = client.get("/api/v1/users/me", headers=auth)
    assert me.status_code == 200 and me.json()["language"] == "az-AZ"
    pref = client.patch("/api/v1/users/preferences", headers=auth, json={"voice_speed": 0.9, "theme": "high_contrast"})
    assert pref.status_code == 200
    assert pref.json()["voice_speed"] == 0.9 and pref.json()["theme"] == "high_contrast"
    assert client.patch("/api/v1/users/preferences", headers=auth, json={"voice_speed": 9}).status_code == 422


def test_api_key_enforced_when_configured(client, monkeypatch):
    headers, _ = register(client)
    monkeypatch.setattr(settings, "API_KEY", "secret-test-key")
    assert client.post("/api/v1/auth/device", json={}).status_code == 401
    assert _message(client, "Salam", headers).status_code == 401
    ok = client.post(
        "/api/v1/assistant/message",
        json={"message": "Salam"},
        headers={**headers, "X-API-Key": "secret-test-key"},
    )
    assert ok.status_code == 200
    assert client.get("/api/v1/health").status_code == 200


# --------------------------------------------------------------------------- voice
def test_voice_endpoint_never_fakes_transcript(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "none")
    res = client.post(
        "/api/v1/assistant/voice",
        headers=auth,
        files={"audio": ("voice.wav", WAV_HEADER + b"\x00\x01" * 100, "audio/wav")},
    )
    assert res.status_code == 503

    res = client.post("/api/v1/assistant/voice", headers=auth, data={"transcript": "Anama zəng et"})
    assert res.status_code == 200
    assert res.json()["intent"] == "MAKE_CALL"


def test_voice_upload_validation(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "none")
    # Wrong MIME type
    res = client.post("/api/v1/assistant/voice", headers=auth, files={"audio": ("x.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert res.status_code == 415
    # Audio MIME type but not really audio
    res = client.post("/api/v1/assistant/voice", headers=auth, files={"audio": ("x.wav", b"<html>not audio</html>", "audio/wav")})
    assert res.status_code == 415
    # Too large
    monkeypatch.setattr(settings, "STT_MAX_AUDIO_BYTES", 1024)
    res = client.post("/api/v1/speech/transcribe", headers=auth, files={"audio": ("big.wav", WAV_HEADER + b"\x00" * 4096, "audio/wav")})
    assert res.status_code == 413
    # Missing everything
    assert client.post("/api/v1/assistant/voice", headers=auth).status_code == 400


def test_voice_endpoint_mock_provider(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "STT_PROVIDER", "mock")
    res = client.post(
        "/api/v1/assistant/voice",
        headers=auth,
        files={"audio": ("voice.wav", "Qızıma zəng et".encode("utf-8"), "audio/wav")},
    )
    assert res.status_code == 200
    assert res.json()["intent"] == "MAKE_CALL"


def test_unexpected_errors_do_not_leak_details(client, auth, monkeypatch):
    from app.services import assistant_service

    def boom(*args, **kwargs):
        raise RuntimeError("internal secret detail")

    monkeypatch.setattr(assistant_service, "run_agent_workflow", boom)
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.post("/api/v1/assistant/message", json={"message": "Salam"}, headers=auth)
    assert res.status_code == 500
    assert "secret" not in res.text
