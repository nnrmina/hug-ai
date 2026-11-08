"""Optional client for the hug-ml intent classifier service (hug-ml/src/api/main.py).

The rule-based adapter stays the primary engine because its decisions are predictable.
The ML model is only consulted when the rules return UNKNOWN, and only a confident
prediction is used. Any network/model failure silently falls back to the rules.
"""
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.core.logging import logger

# hug-ml label -> backend intent
_LABEL_MAP = {
    "CALL": "MAKE_CALL",
    "REMINDER": "CREATE_REMINDER",
    "INFORMATION": "GENERAL_QUESTION",
    "EMERGENCY": "EMERGENCY_CALL",
    "ORDER": "WOLT_ORDER",
    "OTHER": "UNKNOWN",
}


def classify_with_ml(text: str) -> Optional[Dict[str, Any]]:
    """Return {"intent", "confidence"} from hug-ml, or None if disabled/unavailable/unsure."""
    base_url = (settings.HUG_ML_URL or "").rstrip("/")
    if not base_url:
        return None
    try:
        response = httpx.post(
            f"{base_url}/predict",
            json={"text": text},
            timeout=settings.HUG_ML_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("hug-ml unavailable, using rule-based intent only (%s)", type(exc).__name__)
        return None

    label = str(payload.get("intent", "OTHER")).upper()
    confidence = float(payload.get("confidence") or 0.0)
    if payload.get("requires_clarification") or confidence < settings.HUG_ML_MIN_CONFIDENCE:
        return None

    intent = _LABEL_MAP.get(label, "UNKNOWN")
    if intent == "UNKNOWN":
        return None
    return {"intent": intent, "confidence": confidence, "source": "hug-ml"}
