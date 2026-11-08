def test_root_and_health(client):
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "text/html" in r_root.headers["content-type"]

    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"


def test_assistant_call_and_confirmation_flow(client):
    res = client.post("/api/v1/assistant/message", json={"message": "Qızıma zəng et"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "MAKE_CALL"
    assert data["status"] == "needs_confirmation"
    action_id = data["action_id"]
    assert action_id is not None

    status_res = client.get(f"/api/v1/assistant/status/{action_id}")
    assert status_res.status_code == 200
    assert status_res.json()["status"] == "needs_confirmation"

    confirm_res = client.post(f"/api/v1/assistant/confirm/{action_id}")
    assert confirm_res.status_code == 200
    confirmed = confirm_res.json()
    assert confirmed["status"] == "completed"
    assert confirmed["action_data"]["authorized_execution"] == "OPEN_DIALER"


def test_assistant_reminder_confirm_and_cancel_flow(client):
    res = client.post(
        "/api/v1/assistant/message",
        json={"message": "Sabah saat 10-da mənə qızıma zəng etməyi xatırlat"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "CREATE_REMINDER"
    assert data["status"] == "needs_confirmation"
    action_id = data["action_id"]

    confirm_res = client.post(f"/api/v1/assistant/confirm/{action_id}")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["status"] == "completed"
    assert "reminder_id" in confirm_res.json()["action_data"]

    # Verify reminder was persisted in database
    rem_list = client.get("/api/v1/reminders")
    assert rem_list.status_code == 200
    assert len(rem_list.json()) >= 1


def test_reminders_crud(client):
    create_res = client.post(
        "/api/v1/reminders",
        json={
            "title": "Dərman qəbulu",
            "description": "Axşam yeməyindən sonra",
            "scheduled_at": "2026-11-09T20:00:00+04:00",
            "timezone": "Asia/Baku",
        },
    )
    assert create_res.status_code == 201
    rem_id = create_res.json()["id"]

    get_res = client.get(f"/api/v1/reminders/{rem_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Dərman qəbulu"

    patch_res = client.patch(
        f"/api/v1/reminders/{rem_id}",
        json={"status": "completed"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "completed"

    del_res = client.delete(f"/api/v1/reminders/{rem_id}")
    assert del_res.status_code == 204


def test_security_analyze_endpoint(client):
    res = client.post(
        "/api/v1/security/analyze",
        json={
            "message": "Bank hesabınız bloklanıb. Linkə daxil olun və kart məlumatlarını yazın: http://bit.ly/scam"
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["risk_level"] == "high"
    assert body["risk_score"] >= 60
    assert "urgency" in body["indicators"]
    assert "credential_request" in body["indicators"]
    assert "suspicious_link" in body["indicators"]

    get_res = client.get(f"/api/v1/security/result/{body['analysis_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["analysis_id"] == body["analysis_id"]


def test_user_and_preferences_endpoints(client):
    me_res = client.get("/api/v1/users/me")
    assert me_res.status_code == 200
    assert me_res.json()["language"] == "az-AZ"

    pref_res = client.patch(
        "/api/v1/users/preferences",
        json={"voice_speed": 0.9, "theme": "high_contrast"},
    )
    assert pref_res.status_code == 200
    assert pref_res.json()["voice_speed"] == 0.9
    assert pref_res.json()["theme"] == "high_contrast"



def test_order_confirmation_flow(client):
    res = client.post("/api/v1/assistant/message", json={"message": "Taksi çağır"})
    data = res.json()
    assert data["intent"] == "ORDER_TAXI"
    assert data["status"] == "needs_confirmation"

    confirmed = client.post(f"/api/v1/assistant/confirm/{data['action_id']}").json()
    assert confirmed["status"] == "completed"
    assert confirmed["action_data"]["authorized_execution"] == "SIMULATED_ORDER"
    assert "Taksi" in confirmed["response"]


def test_reminder_confirmation_persists(client):
    data = client.post(
        "/api/v1/assistant/message",
        json={"message": "Sabah saat 10-da dərmanımı xatırlat"},
    ).json()
    client.post(f"/api/v1/assistant/confirm/{data['action_id']}")
    reminders = client.get("/api/v1/reminders").json()
    assert any(r["title"] == data["action_data"]["title"] for r in reminders)


def test_voice_endpoint_does_not_invent_transcripts(client):
    res = client.post(
        "/api/v1/assistant/voice",
        files={"audio": ("voice.webm", bytes([0xFF, 0xFE, 0x00, 0x81]), "audio/webm")},
    )
    # Without Gemini the server cannot read raw audio: it must ask again, never guess.
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "needs_clarification"
    assert data["action_data"]["stt_failed"] is True
    assert data["intent"] == "UNKNOWN"
