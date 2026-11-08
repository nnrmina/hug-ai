"""
Unit and Integration Tests for HUG Machine Learning Pipeline.

Covers:
1. Azerbaijani text preprocessing & character integrity.
2. Dataset schema and quality validation.
3. Order entity extraction (quantities, units, products, multi-item).
4. Decision logic & emergency safety guardrails.
5. FastAPI /predict and mock order endpoints.
"""

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.preprocessing.text_preprocessing import (
    az_lower,
    normalize_az_text,
    tokenize_az_text,
    AzerbaijaniTextPreprocessor,
)
from src.entities.extract_entities import (
    extract_order_entities,
    parse_quantity_and_unit,
)
from src.models.predict import IntentPredictor
from src.api.main import app


# ---------------------------------------------------------
# Test 1: Azerbaijani Text Preprocessing & Character Preservation
# ---------------------------------------------------------
def test_az_lower():
    assert az_lower("İSTANBUL") == "istanbul"
    assert az_lower("IŞIQ") == "ışıq"
    assert az_lower("ƏLİ VƏ ALMAZ") == "əli və almaz"


def test_az_character_preservation():
    raw_text = "Həkimə zəng et, təcili yardım çağır! Qızım Şəhla gəlsin."
    normalized = normalize_az_text(raw_text)

    # Verify every critical Azerbaijani character is preserved
    expected_chars = ["ə", "i", "ı", "ş"]
    for ch in expected_chars:
        assert ch in normalized, f"Character '{ch}' was lost in normalization!"

    assert "!" not in normalized
    assert "," not in normalized
    assert "." not in normalized


def test_preprocessor_callable():
    prep = AzerbaijaniTextPreprocessor()
    result = prep("Mənə 2 kilo ALMA sifariş et!")
    assert "2 kilo alma sifaris et" in result or "2 kilo alma sifariş et" in result


# ---------------------------------------------------------
# Test 2: Order Entity Extraction
# ---------------------------------------------------------
def test_single_item_extraction():
    res = extract_order_entities("Mənə Wolt-dan 2 kilo alma sifariş et")
    assert res["is_complete"] is True
    assert len(res["items"]) == 1
    item = res["items"][0]
    assert item["product"] == "alma"
    assert item["quantity"] == 2.0
    assert item["unit"] == "kg"


def test_multi_item_extraction():
    res = extract_order_entities("Mənə 2 kilo alma və 1 kilo pomidor sifariş et.")
    assert res["is_complete"] is True
    assert len(res["items"]) == 2
    prods = {it["product"]: it for it in res["items"]}
    assert "alma" in prods
    assert prods["alma"]["quantity"] == 2.0
    assert prods["alma"]["unit"] == "kg"
    assert "pomidor" in prods
    assert prods["pomidor"]["quantity"] == 1.0
    assert prods["pomidor"]["unit"] == "kg"


def test_spelled_out_numbers():
    res = extract_order_entities("Bazarstore-dan bir litr süd gətirsinlər.")
    assert res["is_complete"] is True
    assert len(res["items"]) == 1
    assert res["items"][0]["quantity"] == 1.0
    assert res["items"][0]["unit"] == "litr"


def test_incomplete_order_triggers_clarification():
    # Missing quantity and unit
    res = extract_order_entities("Mənə alma sifariş et.")
    assert len(res["items"]) == 1
    assert res["is_complete"] is False
    assert len(res["missing_fields"]) > 0


# ---------------------------------------------------------
# Test 3: Emergency Safety Guardrail
# ---------------------------------------------------------
def test_emergency_guardrail_detection():
    predictor = IntentPredictor()
    # High-distress phrase must trigger safety guardrail
    assert predictor.check_emergency_safety_guardrail("Özümü çox pis hiss edirəm, təcili yardım çağır!") is True
    assert predictor.check_emergency_safety_guardrail("Ürəyim bərk sıxılır, nəfəs ala bilmirəm") is True
    assert predictor.check_emergency_safety_guardrail("Boğuluram, 103-ü yığ!") is True
    assert predictor.check_emergency_safety_guardrail("Salam, necəsən?") is False


def test_emergency_overrides_to_emergency_action():
    predictor = IntentPredictor()
    res = predictor.predict("Özümü çox pis hiss edirəm, 103 təcili yardım çağır!")
    assert res["intent"] == "EMERGENCY"
    assert res["requires_clarification"] is False
    assert res["recommended_action"] == "EMERGENCY_DISPATCH"
    assert res["safety_escalation"] is True


from src.api.main import (
    health,
    predict_intent,
    mock_checkout,
    PredictRequest,
    MockCheckoutRequest,
    OrderItem,
)


# ---------------------------------------------------------
# Test 4: FastAPI Endpoints Integration
# ---------------------------------------------------------
def test_health_endpoint():
    data = health()
    assert "status" in data
    assert data["status"] == "healthy"
    assert data["model_loaded"] is True
    assert len(data["classes"]) == 6


def test_predict_endpoint_order():
    req = PredictRequest(text="Mənə 2 kilo alma sifariş et")
    res = predict_intent(req)
    assert res["intent"] == "ORDER"
    assert res["confidence"] > 0.45
    assert res["recommended_action"] == "PROCESS_ORDER"
    assert len(res["entities"]["items"]) == 1
    assert res["entities"]["items"][0]["product"] == "alma"


def test_mock_checkout_endpoint():
    req = MockCheckoutRequest(
        items=[
            OrderItem(product="alma", quantity=2.0, unit="kg"),
            OrderItem(product="pomidor", quantity=1.0, unit="kg")
        ],
        delivery_address="Nizami küçəsi 45, Bakı"
    )
    res = mock_checkout(req)
    assert res["status"] == "CONFIRMED"
    assert "WOLT-MOCK" in res["order_id"]
    assert res["estimated_total_azn"] > 0
    assert len(res["items"]) == 2


# ---------------------------------------------------------
# Test 5: Regression tests for review findings
# ---------------------------------------------------------
# 1. Azerbaijani casing (İ -> i, I -> ı) in entity extraction and guardrail
def test_entity_extraction_uses_azerbaijani_casing():
    res = extract_order_entities("MƏNƏ İKİ KİLO ALMA SİFARİŞ ET")
    assert res["items"] == [{"product": "alma", "quantity": 2.0, "unit": "kg"}]
    res = extract_order_entities("BİR LİTR SÜD VƏ İKİ ŞÜŞƏ MİNERAL SU")
    prods = {it["product"]: it for it in res["items"]}
    assert prods["süd"]["quantity"] == 1.0 and prods["süd"]["unit"] == "litr"
    assert prods["mineral su"]["quantity"] == 2.0 and prods["mineral su"]["unit"] == "şüşə"


def test_guardrail_uses_azerbaijani_casing():
    predictor = IntentPredictor()
    assert predictor.check_emergency_safety_guardrail("ÜRƏYİM AĞRIYIR") is True
    assert predictor.check_emergency_safety_guardrail("NƏFƏS ALA BİLMİRƏM") is True


# 2. Products are matched on token boundaries, longest match first
def test_product_matching_respects_token_boundaries():
    res = extract_order_entities("Mənə marketdən 1 kilo kökə sifariş et.")
    assert [it["product"] for it in res["items"]] == ["kökə"]
    res = extract_order_entities("İki kilo kök al")
    assert [it["product"] for it in res["items"]] == ["kök"]
    res = extract_order_entities("Bir şüşə zeytun yağı al")
    assert [it["product"] for it in res["items"]] == ["zeytun yağı"]
    res = extract_order_entities("Aptekdən təzyiq dərmanımı sifariş et")
    assert [it["product"] for it in res["items"]] == ["təzyiq dərmanı"]


# 3. Multi-word numbers and no silent default unit
@pytest.mark.parametrize("text,product,qty,unit", [
    ("beş yüz qram pendir al", "pendir", 500.0, "qram"),
    ("iki yüz əlli qram kərə yağı", "kərə yağı", 250.0, "qram"),
    ("min iki yüz qram un", "un", 1200.0, "qram"),
    ("yarım kilo pendir", "pendir", 0.5, "kg"),
    ("2.5 kilo kartof", "kartof", 2.5, "kg"),
    ("500qr pendir", "pendir", 500.0, "qram"),
    ("on beş dənə yumurta", "yumurta", 15.0, "ədəd"),
])
def test_multi_word_numbers(text, product, qty, unit):
    res = extract_order_entities(text)
    assert res["items"] == [{"product": product, "quantity": qty, "unit": unit}]


def test_unit_is_none_when_not_stated():
    qty, unit, rest = parse_quantity_and_unit("2 alma")
    assert (qty, unit, rest) == (2.0, None, "alma")
    res = extract_order_entities("Mənə iki çörək al")
    assert res["items"] == [{"product": "çörək", "quantity": 2.0, "unit": None}]
    assert res["is_complete"] is False
    assert "unit_for_çörək" in res["missing_fields"]


# 4. Guardrail: emergency numbers in information questions are not emergencies
@pytest.mark.parametrize("text", [
    "112 nömrəsi neçədir?",
    "Təcili yardımın nömrəsi neçədir?",
    "Polisin nömrəsi nədir?",
    "103 pulsuzdur?",
    "Həkim Nigar xanıma zəng et",
])
def test_guardrail_ignores_number_questions(text):
    predictor = IntentPredictor()
    assert predictor.check_emergency_safety_guardrail(text) is False
    res = predictor.predict(text)
    assert res["intent"] != "EMERGENCY"
    assert res["safety_escalation"] is False


@pytest.mark.parametrize("text", [
    "Təcili yardım çağır",
    "103-ə zəng et",
    "Ürəyim ağrıyır",
    "Nəfəs ala bilmirəm",
    "Yıxıldım, dura bilmirəm",
    "ureyim agriyir",
    "Təcili yardım!",
])
def test_guardrail_keeps_genuine_emergencies(text):
    predictor = IntentPredictor()
    assert predictor.check_emergency_safety_guardrail(text) is True
    res = predictor.predict(text)
    assert res["intent"] == "EMERGENCY"
    assert res["recommended_action"] == "EMERGENCY_DISPATCH"


# API: missing model -> 503 (but emergencies still dispatched); CORS without credentials
def test_predict_returns_503_when_model_missing(monkeypatch, tmp_path):
    import src.api.main as api_main
    missing = IntentPredictor(model_path=tmp_path / "missing.joblib")
    monkeypatch.setattr(api_main, "predictor", missing)
    client = TestClient(api_main.app)
    assert client.get("/health").json()["model_loaded"] is False
    assert client.post("/predict", json={"text": "Mənə 2 kilo alma sifariş et"}).status_code == 503
    emergency = client.post("/predict", json={"text": "Təcili yardım çağır, nəfəs ala bilmirəm"})
    assert emergency.status_code == 200
    assert emergency.json()["intent"] == "EMERGENCY"


def test_cors_does_not_allow_credentials():
    client = TestClient(app)
    r = client.options("/predict", headers={
        "Origin": "http://example.com", "Access-Control-Request-Method": "POST",
    })
    assert r.headers.get("access-control-allow-credentials") != "true"


def test_predict_response_schema():
    client = TestClient(app)
    body = client.post("/predict", json={"text": "Qızıma zəng et"}).json()
    assert set(body) == {"intent", "confidence", "requires_clarification", "entities",
                         "recommended_action", "safety_escalation"}
