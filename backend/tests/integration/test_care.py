"""SOS, family circle, medicines and daily check-in — with pushes captured, not sent."""
from datetime import datetime, timedelta, timezone

import pytest

import app.services.care_service as care_mod
from app.services.care_service import CareService, _slot_utc, baku_day

ELDER = {"X-HUG-Device": "elder-device-0000000001"}
OTHER = {"X-HUG-Device": "other-device-0000000002"}


@pytest.fixture()
def pushes(monkeypatch):
    sent = []
    monkeypatch.setattr(care_mod, "push_to_elder", lambda db, uid, p: sent.append(("elder", uid, p)) or 1)
    monkeypatch.setattr(care_mod, "push_to_family", lambda db, uid, p, **k: sent.append(("family", uid, p)) or 1)
    return sent


def _setup_family(client, headers=ELDER):
    client.put("/api/v1/care/profile", json={"name": "Səadət xanım"}, headers=headers)
    return client.post("/api/v1/care/family", json={"name": "Sevinc", "relation": "qızım", "phone": "+994 50 123 45 67"},
                       headers=headers).json()


def test_devices_are_isolated(client):
    client.post("/api/v1/reminders", json={"title": "x", "scheduled_at": "2030-01-01T10:00:00+04:00",
                                           "user_id": "elder-device-0000000001"})
    _setup_family(client)
    assert len(client.get("/api/v1/reminders", headers=ELDER).json()) == 1
    assert client.get("/api/v1/reminders", headers=OTHER).json() == []
    assert client.get("/api/v1/care/state", headers=OTHER).json()["family"] == []


def test_family_member_gets_private_link_and_view(client):
    member = _setup_family(client)
    assert member["invite_url"].endswith("/f/" + member["invite_url"].rsplit("/", 1)[1])
    token = member["invite_url"].rsplit("/", 1)[1]
    view = client.get(f"/api/v1/family/{token}").json()
    assert view["elder"]["name"] == "Səadət xanım"
    assert view["member"]["relation"] == "qızım"
    assert client.get("/api/v1/family/not-a-real-token").status_code == 404
    assert client.get(f"/f/{token}").status_code == 200  # family page HTML


def test_sos_notifies_family_with_location(client, pushes):
    _setup_family(client)
    res = client.post("/api/v1/care/sos", json={"lat": 40.4093, "lon": 49.8671, "reason": "Yıxıldım"}, headers=ELDER)
    assert res.status_code == 200
    assert res.json()["family"][0]["phone"] == "+994501234567"
    kind, _, payload = pushes[-1]
    assert kind == "family" and "SOS" in payload["title"] and "maps.google.com" in payload["body"]


def test_medicine_due_then_missed_then_family_alert(client, pushes, db_session):
    _setup_family(client)
    med = client.post("/api/v1/care/medications", json={"name": "Kardiomaqnil", "times": ["9:00", "21:00"], "dose": "1 həb"},
                      headers=ELDER).json()
    assert med["times"] == ["09:00", "21:00"]
    svc = CareService(db_session)
    uid = "elder-device-0000000001"
    day = baku_day()
    t9 = _slot_utc(day, "09:00")

    svc.tick(now=t9 + timedelta(minutes=1))                     # due → elder push
    assert any(k == "elder" and "Dərman vaxtı" in p["title"] for k, _, p in pushes)
    svc.tick(now=t9 + timedelta(minutes=5))                     # not re-sent
    assert sum(1 for k, _, p in pushes if "Dərman vaxtı" in p["title"]) == 1

    svc.tick(now=t9 + timedelta(minutes=31))                    # missed → family push
    doses = {d["time"]: d for d in svc.doses_today(uid, now=t9)}
    assert doses["09:00"]["status"] == "missed"
    assert any(k == "family" and "içməyib" in p["title"] for k, _, p in pushes)

    # taking it late still records it
    taken = client.post(f"/api/v1/care/doses/{doses['09:00']['id']}/taken", headers=ELDER).json()
    assert taken["status"] == "taken"


def test_snooze_retimes_dose(client, pushes, db_session):
    client.post("/api/v1/care/medications", json={"name": "Vitamin", "times": ["08:00"]}, headers=ELDER)
    dose = client.get("/api/v1/care/doses/today", headers=ELDER).json()[0]
    res = client.post(f"/api/v1/care/doses/{dose['id']}/snooze", json={"minutes": 10}, headers=ELDER)
    assert res.json()["status"] == "pending"
    after = client.get("/api/v1/care/doses/today", headers=ELDER).json()[0]
    due = datetime.fromisoformat(after["due_at"])
    assert timedelta(minutes=9) < due - datetime.now(timezone.utc) <= timedelta(minutes=10)


def test_other_device_cannot_touch_my_dose(client):
    client.post("/api/v1/care/medications", json={"name": "Vitamin", "times": ["08:00"]}, headers=ELDER)
    dose = client.get("/api/v1/care/doses/today", headers=ELDER).json()[0]
    assert client.post(f"/api/v1/care/doses/{dose['id']}/taken", headers=OTHER).status_code == 404


def test_checkin_prompt_escalation_and_bad_mood(client, pushes, db_session):
    _setup_family(client)
    svc = CareService(db_session)
    start = _slot_utc(baku_day(), "10:00")
    svc.tick(now=start + timedelta(minutes=1))
    assert any(k == "elder" and "Sabahınız" in p["title"] for k, _, p in pushes)
    svc.tick(now=start + timedelta(minutes=125))
    assert any(k == "family" and "əlaqə saxlamayıb" in p["title"] for k, _, p in pushes)
    n = len(pushes)
    svc.tick(now=start + timedelta(minutes=200))                 # no duplicates
    assert len(pushes) == n

    client.post("/api/v1/care/checkin", json={"mood": "bad"}, headers=ELDER)
    assert any(k == "family" and "pis hiss edir" in p["title"] for k, _, p in pushes)
    assert client.get("/api/v1/care/state", headers=ELDER).json()["checkin"]["mood"] == "bad"


def test_family_can_add_medicine_remotely(client):
    member = _setup_family(client)
    token = member["invite_url"].rsplit("/", 1)[1]
    res = client.post(f"/api/v1/family/{token}/medications", json={"name": "Aspirin", "times": ["20:00"]})
    assert res.status_code == 201
    state = client.get("/api/v1/care/state", headers=ELDER).json()
    assert state["medications"][0]["name"] == "Aspirin"


def test_invalid_times_rejected(client):
    res = client.post("/api/v1/care/medications", json={"name": "X", "times": ["25:00"]}, headers=ELDER)
    assert res.status_code == 422


def _say(client, text, session="care-s"):
    return client.post("/api/v1/assistant/message", json={"message": text, "session_id": session}, headers=ELDER).json()


def test_voice_emergency_is_immediate(client):
    data = _say(client, "Kömək edin, yıxıldım!")
    assert data["intent"] == "EMERGENCY" and data["status"] == "completed"
    assert data["action_data"]["emergency"] is True


def test_voice_creates_repeating_medicine(client):
    data = _say(client, "Hər gün səhər 9-da və axşam 9-da təzyiq dərmanımı xatırlat")
    assert data["intent"] == "CREATE_MEDICATION" and data["status"] == "needs_confirmation"
    client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=ELDER)
    meds = client.get("/api/v1/care/state", headers=ELDER).json()["medications"]
    assert meds[0]["times"] == ["09:00", "21:00"]


def test_voice_medicine_follow_up_asks_time(client):
    first = _say(client, "Hər gün dərmanımı xatırlat", session="m2")
    assert first["status"] == "needs_clarification"
    second = _say(client, "səhər 8-də", session="m2")
    assert second["intent"] == "CREATE_MEDICATION" and second["action_data"]["med_times"] == ["08:00"]


def test_voice_checkin_records_mood(client, pushes):
    _setup_family(client)
    data = _say(client, "Bu gün özümü pis hiss edirəm")
    assert data["intent"] == "CHECKIN"
    assert client.get("/api/v1/care/state", headers=ELDER).json()["checkin"]["mood"] == "bad"
    assert any(k == "family" for k, _, _ in pushes)


def test_other_device_cannot_confirm_my_action(client):
    data = _say(client, "Taksi çağır")
    res = client.post(f"/api/v1/assistant/confirm/{data['action_id']}", headers=OTHER)
    assert res.status_code == 404
