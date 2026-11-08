"""
FastAPI Service for HUG Machine Learning Intent & Entity Pipeline.

Endpoints:
- POST /predict: Predicts intent, calculates model confidence, extracts entities,
                 and computes recommended action.
- POST /orders/mock-checkout: Mock execution service simulating Wolt delivery order.
- GET /health: Service and model status.
- GET /model-info: Returns model metadata and performance metrics.
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.models.predict import IntentPredictor, ModelNotLoadedError

app = FastAPI(
    title="HUG Machine Learning Intent API",
    description="Azerbaijani Voice-Intent Classifier & Entity Extractor (TF-IDF + calibrated linear model MVP)",
    version="1.0.0",
)

# CORS: origins are configurable via ALLOWED_ORIGINS (comma-separated, default "*").
# Credentials are never allowed: a wildcard origin combined with credentials is unsafe
# (and rejected by browsers); this API is called server-to-server and needs no cookies.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if o.strip()
] or ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Instantiate predictor with trained model
predictor = IntentPredictor()


class PredictRequest(BaseModel):
    text: str = Field(..., description="Azerbaijani spoken or typed utterance", json_schema_extra={"example": "Mənə 2 kilo alma sifariş et"})


class OrderItem(BaseModel):
    product: str
    quantity: Optional[float] = None
    unit: Optional[str] = None


class EntityPayload(BaseModel):
    items: List[OrderItem] = []


class PredictResponse(BaseModel):
    intent: str
    confidence: float
    requires_clarification: bool
    entities: EntityPayload
    recommended_action: str
    safety_escalation: Optional[bool] = False


class MockCheckoutRequest(BaseModel):
    items: List[OrderItem]
    delivery_address: str = "Bakı şəhəri, Nəsimi rayonu"
    customer_notes: Optional[str] = None


class MockCheckoutResponse(BaseModel):
    order_id: str
    status: str
    store: str
    items: List[OrderItem]
    estimated_total_azn: float
    delivery_address: str
    message: str


@app.get("/health")
def health():
    loaded = predictor.is_ready
    return {
        "status": "healthy" if loaded else "degraded",
        "model_loaded": loaded,
        "model_path": str(predictor.model_path),
        "classes": predictor._classes,
        "clarification_threshold": predictor.confidence_threshold,
        **({} if loaded else {"detail": "Model file missing - run `python src/models/train.py`."}),
    }


@app.get("/model-info")
def model_info():
    metrics_path = BASE_DIR / "reports" / "metrics.json"
    if metrics_path.exists():
        import json
        with open(metrics_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"message": "Metrics report not yet generated. Run evaluation."}


@app.post("/predict", response_model=PredictResponse)
def predict_intent(payload: PredictRequest):
    """
    Receives user utterance in Azerbaijani, normalizes phonemes,
    runs intent inference, extracts entities, and applies safety logic.
    Returns 503 if the model artifact is missing (unless the emergency guardrail fires,
    in which case the EMERGENCY result is still returned).
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Mətn boş ola bilməz.")

    try:
        return predictor.predict(payload.text)
    except ModelNotLoadedError:
        raise HTTPException(
            status_code=503,
            detail="Intent model is not loaded (model file missing). Run training first.",
        )


@app.post("/orders/mock-checkout", response_model=MockCheckoutResponse)
def mock_checkout(payload: MockCheckoutRequest):
    """
    Mock order processing service for Wolt / Bazarstore food & grocery ordering.
    Simulates delivery order confirmation without real payment execution.
    """
    if not payload.items:
        raise HTTPException(status_code=400, detail="Sifarişdə ən azı bir məhsul olmalıdır.")

    # Calculate simulated pricing
    total_azn = 0.0
    for it in payload.items:
        qty = it.quantity or 1.0
        # Simulated unit price between 2.00 - 8.00 AZN
        total_azn += round(qty * 3.50, 2)

    total_azn += 2.50  # Delivery fee

    import uuid
    order_id = f"WOLT-MOCK-{uuid.uuid4().hex[:8].upper()}"

    return {
        "order_id": order_id,
        "status": "CONFIRMED",
        "store": "Wolt Partner Market (Simulyasiya)",
        "items": payload.items,
        "estimated_total_azn": round(total_azn, 2),
        "delivery_address": payload.delivery_address,
        "message": f"Sifarişiniz qəbul olundu. Kuryer təxminən 30-40 dəqiqəyə çatdıracaq."
    }
