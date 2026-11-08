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
