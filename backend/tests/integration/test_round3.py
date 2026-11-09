"""Russian replies, weather, nearest places, health log and multi-step requests."""
from types import SimpleNamespace

import pytest

import app.services.assistant_service as asst_mod
import app.services.care_service as care_mod
from app.integrations.llm.provider import get_rule_adapter
from app.services import places_service, weather_service
from app.services.care_service import classify_health
from tests.unit.test_gemini_adapter import make_adapter, understanding

ELDER = {"X-HUG-Device": "elder-device-0000000003"}

OPEN_METEO = {
    "current": {"temperature_2m": 12.4, "weather_code": 3, "wind_speed_10m": 9},
    "daily": {"temperature_2m_max": [15.2, 17.8], "temperature_2m_min": [8.9, 9.6],
              "precipitation_probability_max": [10, 65], "weather_code": [3, 61]},
}
OVERPASS = {"elements": [
    {"type": "node", "lat": 40.4200, "lon": 49.8700, "tags": {"amenity": "pharmacy", "name": "Uzaq Aptek"}},
    {"type": "node", "lat": 40.4095, "lon": 49.8672, "tags": {"amenity": "pharmacy", "name": "Zəfəran Aptek",
                                                           "phone": "+994 12 555 55 55"}},
    {"type": "way", "center": {"lat": 40.4110, "lon": 49.8690}, "tags": {"amenity": "pharmacy"}},
    {"type": "node", "lat": 40.4300, "lon": 49.9000, "tags": {"amenity": "pharmacy", "name": "Ən Uzaq"}},
]}


NOMINATIM = [
    {"lat": "40.4200", "lon": "49.8700", "category": "amenity", "type": "pharmacy", "name": "Uzaq Aptek"},
    {"lat": "40.4095", "lon": "49.8672", "category": "amenity", "type": "pharmacy", "name": "Zəfəran Aptek",
     "extratags": {"phone": "+994 12 555 55 55"}, "address": {"road": "Nizami küçəsi", "house_number": "5"}},
    {"lat": "40.4110", "lon": "49.8690", "category": "amenity", "type": "pharmacy", "name": ""},
    {"lat": "40.4300", "lon": "49.9000", "category": "amenity", "type": "pharmacy", "name": "Ən Uzaq"},
    {"lat": "40.4096", "lon": "49.8673", "category": "shop", "type": "chemist", "name": "Not a pharmacy"},
]


class FakeResp:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


@pytest.fixture()
def pushes(monkeypatch):
    sent = []
    monkeypatch.setattr(care_mod, "push_to_family", lambda db, uid, p, **k: sent.append(p) or 1)
    return sent


@pytest.fixture()
def net(monkeypatch):
    weather_service._cache.clear()
    places_service._cache.clear()
    def fake_get(url, *a, **k):
        return FakeResp(NOMINATIM if "nominatim" in url else OPEN_METEO)
    monkeypatch.setattr(weather_service.httpx, "get", fake_get)
    monkeypatch.setattr(places_service.httpx, "post", lambda *a, **k: FakeResp(OVERPASS))


def say(client, text, **extra):
    return client.post("/api/v1/assistant/message", json={"message": text, **extra}, headers=ELDER).json()


# ---------------------------------------------------------------- rules
@pytest.mark.parametrize("text,intent", [
    ("Sabah hava necə olacaq?", "WEATHER"),
    ("Ən yaxın aptek haradadır", "FIND_PLACE"),
    ("Yaxınlıqda xəstəxana var?", "FIND_PLACE"),
    ("Təzyiqim 150-yə 95", "LOG_HEALTH"),
    ("Şəkərim 7,5", "LOG_HEALTH"),
    ("Son təzyiqlərim necədir", "HEALTH_QUERY"),
    ("Aptekdən kardiomaqnil sifariş et", "ORDER_PHARMACY"),
    ("Sabah 10-da dərmanımı xatırlat", "CREATE_REMINDER"),
])
def test_rule_intents(text, intent):
    assert get_rule_adapter().understand(text=text)["intent"] == intent


def test_rule_health_values_and_weather_day():
    bp = get_rule_adapter().understand(text="Təzyiqim 150-yə 95")
    assert (bp["health_kind"], bp["health_value"], bp["health_value2"]) == ("bp", 150, 95)
    sugar = get_rule_adapter().understand(text="Şəkərim 7,5")
    assert (sugar["health_kind"], sugar["health_value"]) == ("sugar", 7.5)
    assert get_rule_adapter().understand(text="Sabah hava necə olacaq?")["weather_day"] == "tomorrow"


def test_rule_multi_step_split():
    out = get_rule_adapter().understand(text="Tantuni sifariş et, sonra qızıma zəng et")
    assert out["intent"] == "ORDER_FOOD"
    assert out["next_step"] == "qızıma zəng et"


def test_rule_cyrillic_is_russian():
    out = get_rule_adapter().understand(text="Позвони дочке")
    assert out["lang"] == "ru" and "clarification_question" in out


# ---------------------------------------------------------------- weather & places
def test_weather_turn_uses_live_forecast(client, net):
    today = say(client, "Bu gün hava necədir?")
    assert today["intent"] == "WEATHER" and today["status"] == "completed"
    assert "Bakıda indi +12 dərəcədir" in today["response"] and "buludludur" in today["response"]
    tomorrow = say(client, "Sabah hava necə olacaq?", lat=40.41, lon=49.87)
    assert "Sabah olduğunuz yerdə" in tomorrow["response"]
    assert "+10 ilə +18" in tomorrow["response"] and "65 faiz" in tomorrow["response"]
    assert tomorrow["action_data"]["weather"]["here"] is True


def test_weather_failure_is_graceful(client, monkeypatch):
    weather_service._cache.clear()

    def boom(*a, **k):
        raise TimeoutError("slow")
    monkeypatch.setattr(weather_service.httpx, "get", boom)
    res = say(client, "Bu gün hava necədir?")
    assert res["status"] == "completed" and "ala bilmədim" in res["response"]


def test_nearby_places_sorted_and_limited(client, net):
    res = client.get("/api/v1/places/nearby", params={"lat": 40.4093, "lon": 49.8671, "type": "pharmacy"}).json()
    names = [p["name"] for p in res["places"]]
    assert names[0] == "Zəfəran Aptek" and len(names) == 3 and "Ən Uzaq" not in names
    assert res["places"][0]["distance_m"] < 50 and res["places"][0]["phone"]
    assert names[1] == "Aptek"  # unnamed building falls back to a generic name
    assert res["places"][0]["address"] == "Nizami küçəsi 5"


def test_places_fall_back_to_overpass(client, monkeypatch):
    places_service._cache.clear()

    def down(*a, **k):
        raise TimeoutError("nominatim down")
    monkeypatch.setattr(places_service.httpx, "get", down)
    monkeypatch.setattr(places_service.httpx, "post", lambda *a, **k: FakeResp(OVERPASS))
    res = client.get("/api/v1/places/nearby", params={"lat": 40.4093, "lon": 49.8671}).json()
    assert res["places"][0]["name"] == "Zəfəran Aptek"


def test_places_failure_not_cached(client, monkeypatch):
    places_service._cache.clear()

    def down(*a, **k):
        raise TimeoutError("down")
    monkeypatch.setattr(places_service.httpx, "get", down)
    monkeypatch.setattr(places_service.httpx, "post", down)
    assert client.get("/api/v1/places/nearby", params={"lat": 40.1, "lon": 49.1}).json()["places"] == []
    assert places_service._cache == {}


# ---------------------------------------------------------------- health
def test_health_thresholds():
    assert classify_health("bp", 120, 80) == "normal"
    assert classify_health("bp", 150, 95) == "high"
    assert classify_health("bp", 185, 110) == "critical"
    assert classify_health("sugar", 3.5) == "low"
    assert classify_health("temp", 39.6) == "critical"


def test_health_by_voice_and_family_alert(client, pushes):
    client.put("/api/v1/care/profile", json={"name": "Səadət xanım"}, headers=ELDER)
    ok = say(client, "Təzyiqim 130-a 80")
    assert ok["intent"] == "LOG_HEALTH" and "normaldır" in ok["response"] and pushes == []
    bad = say(client, "Təzyiqim 185-ə 115")
    assert "çox yüksək" in bad["response"] and len(pushes) == 1 and "185/115" in pushes[0]["title"]
    state = client.get("/api/v1/care/state", headers=ELDER).json()
    assert [h["text"] for h in state["health"]][:2] == ["185/115", "130/80"]
    summary = say(client, "Son təzyiqlərim necədir")
    assert "185/115" in summary["response"]


def test_health_api_validation(client, pushes):
    assert client.post("/api/v1/care/health", json={"kind": "pulse", "value": 72}, headers=ELDER).status_code == 201
    assert client.post("/api/v1/care/health", json={"kind": "bp", "value": 140}, headers=ELDER).status_code == 422
    assert client.post("/api/v1/care/health", json={"kind": "sugar", "value": 99}, headers=ELDER).status_code == 422
    rid = client.get("/api/v1/care/health", headers=ELDER).json()[0]["id"]
    assert client.delete(f"/api/v1/care/health/{rid}", headers=ELDER).status_code == 204
    assert client.get("/api/v1/care/health", headers=ELDER).json() == []


# ---------------------------------------------------------------- Russian + multi-step via Gemini
def use_gemini(monkeypatch, reply):
    adapter, _ = make_adapter(reply)
    monkeypatch.setattr(asst_mod, "get_llm_adapter", lambda: adapter)


def test_russian_call_confirm_round_trip(client, monkeypatch):
    use_gemini(monkeypatch, understanding(transcript="Позвони дочке", intent="MAKE_CALL",
                                          contact_alias="qızım", language="ru"))
    res = say(client, "Позвони дочке")
    assert res["lang"] == "ru" and res["status"] == "needs_confirmation"
    assert "Позвонить" in res["response"]
    asst_mod._ACTION_STORE.clear()  # force the signed-token path
    done = client.post(f"/api/v1/assistant/confirm/{res['action_id']}",
                       json={"action_token": res["action_token"]}, headers=ELDER).json()
    assert done["response"] == "Звоню."


def test_russian_reminder_text(client, monkeypatch):
    use_gemini(monkeypatch, understanding(transcript="Напомни завтра в 10 про лекарство", intent="CREATE_REMINDER",
                                          title="Лекарство", scheduled_at="2099-01-01T10:00:00+04:00",
                                          language="ru"))
    res = say(client, "Напомни завтра в 10 про лекарство")
    # 2099 is too far out for Gemini's time, so the parser decides; the reply is Russian either way
    assert res["lang"] == "ru"


def test_multi_step_next_step_returned(client, monkeypatch):
    use_gemini(monkeypatch, understanding(transcript="Tantuni sifariş et, sonra qızıma de ki yemək gəlir",
                                          intent="ORDER_FOOD", food_item="tantuni",
                                          next_step="Qızıma mesaj göndər ki yemək gəlir"))
    res = say(client, "Tantuni sifariş et, sonra qızıma de ki yemək gəlir")
    assert res["intent"] == "ORDER_FOOD" and res["next_step"] == "Qızıma mesaj göndər ki yemək gəlir"


def test_tts_russian_voice(client, monkeypatch):
    import app.api.v1.tts as tts_mod
    seen = {}

    async def fake(text, voice):
        seen["voice"] = voice
        return None
    monkeypatch.setattr(tts_mod, "synthesize_mp3", fake)
    client.get("/api/v1/tts", params={"text": "Привет", "lang": "ru"})
    assert seen["voice"] == "ru-RU-SvetlanaNeural"
