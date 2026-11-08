"""Multi-turn follow-ups, stateless confirmation tokens and the session store (rule engine)."""
from app.services.assistant_service import _ACTION_STORE
from app.services.session_store import SessionStore


def _say(client, text, session="s-1", **extra):
    return client.post(
        "/api/v1/assistant/message",
        json={"message": text, "session_id": session, **extra},
    ).json()


def test_reminder_follow_up_fills_missing_time(client):
    first = _say(client, "Dərmanımı xatırlat")
    assert first["status"] == "needs_clarification"
    assert "Nə vaxt" in first["response"]

    second = _say(client, "sabah saat 9-da")
    assert second["intent"] == "CREATE_REMINDER"
    assert second["status"] == "needs_confirmation"
    assert second["action_data"]["title"] == "Dərman qəbulu"
    assert second["action_data"]["scheduled_at"].endswith("T09:00:00+04:00")


def test_follow_up_is_per_session(client):
    _say(client, "Dərmanımı xatırlat", session="a")
    other = _say(client, "sabah saat 9-da", session="b")
    assert other["intent"] != "CREATE_REMINDER" or other["action_data"]["title"] != "Dərman qəbulu"


def test_call_follow_up_asks_who(client):
    first = _say(client, "Zəng et")
    assert first["status"] == "needs_clarification"
    assert "Kimə" in first["response"]
    second = _say(client, "qızıma")
    assert second["intent"] == "MAKE_CALL"
    assert second["action_data"]["contact_alias"] == "qızım"


def test_client_history_is_used_when_server_session_is_gone(client):
    history = [{
        "user": "Dərmanımı xatırlat",
        "assistant": "Nə vaxt xatırladım?",
        "intent": "CREATE_REMINDER",
        "status": "needs_clarification",
        "pending": {"intent": "CREATE_REMINDER", "title": "Dərman qəbulu"},
    }]
    data = _say(client, "axşam saat 8-də", session="fresh", history=history)
    assert data["intent"] == "CREATE_REMINDER"
    assert data["action_data"]["scheduled_at"].endswith("T20:00:00+04:00")


def test_confirm_works_from_signed_token_after_restart(client):
    data = _say(client, "Taksi çağır")
    token = data["action_token"]
    assert token
    _ACTION_STORE.clear()  # simulate another serverless instance / restart

    res = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", json={"action_token": token})
    assert res.status_code == 200
    assert res.json()["status"] == "completed"

    # replaying the confirm is idempotent
    again = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", json={"action_token": token})
    assert again.json()["status"] == "completed"


def test_tampered_or_mismatched_token_is_rejected(client):
    data = _say(client, "Taksi çağır")
    _ACTION_STORE.clear()
    body, sig = data["action_token"].rsplit(".", 1)
    tampered = body + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
    bad = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", json={"action_token": tampered})
    assert bad.status_code == 404
    wrong_id = client.post("/api/v1/assistant/confirm/other-id", json={"action_token": data["action_token"]})
    assert wrong_id.status_code == 404


def test_confirmed_reminder_is_not_created_twice(client):
    data = _say(client, "Sabah saat 10-da dərmanımı xatırlat")
    client.post(f"/api/v1/assistant/confirm/{data['action_id']}")
    client.post(f"/api/v1/assistant/confirm/{data['action_id']}")
    assert len(client.get("/api/v1/reminders").json()) == 1


def test_session_store_ttl_and_max_turns():
    now = [1000.0]
    store = SessionStore(ttl_s=10, max_turns=2, clock=lambda: now[0])
    for i in range(3):
        store.append("s", {"user": str(i)})
    assert [t["user"] for t in store.get("s")] == ["1", "2"]
    now[0] += 11
    assert store.get("s") == []


def test_static_app_files_are_served(client):
    assert "text/html" in client.get("/").headers["content-type"]
    css = client.get("/static/styles.css")
    assert css.status_code == 200 and "text/css" in css.headers["content-type"]
