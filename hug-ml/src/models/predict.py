"""
Inference and Decision Logic Module for HUG AI Voice Assistant.

Combines:
1. Trained intent pipeline (TF-IDF + calibrated linear classifier, see train.py).
2. Calibrated probabilistic confidence via predict_proba().
3. A clarification threshold tuned on validation data (stored in model_metadata.json);
   predictions below it return CLARIFY instead of acting.
4. Separate safety workflow for EMERGENCY detection (rule-augmented guardrail).
5. Integration with Order Entity Extractor for structured downstream dispatch.
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "intent_pipeline.joblib"
METADATA_PATH = MODELS_DIR / "model_metadata.json"
DEFAULT_CONFIDENCE_THRESHOLD = 0.45

sys.path.insert(0, str(BASE_DIR))
from src.entities.extract_entities import extract_order_entities  # noqa: E402
from src.preprocessing.text_preprocessing import normalize_az_text  # noqa: E402

_FOLD_TABLE = str.maketrans("əıöüşçğ", "eiouscg")


def fold_az_text(text: str) -> str:
    """normalize_az_text (Azerbaijani-aware casing, punctuation removal) + diacritic folding,
    so that 'Ürəyim ağrıyır' and 'ureyim agriyir' are matched by the same pattern."""
    return normalize_az_text(text).translate(_FOLD_TABLE)


# --- Emergency guardrail patterns (written in folded form, applied to folded text) ---

# Distress signals: on their own they are enough to escalate.
EMERGENCY_DISTRESS_PATTERNS = [
    r"\bolurem\b", r"\bboguluram\b", r"\bbogulma\b",
    r"\bnefes ala bilmirem\b", r"\bnefesim catmir\b", r"\bnefes catismir\b",
    r"\bhusumu itirirem\b", r"\bhusum gedir\b", r"\bhussuz\b",
    r"\bqanaxma\b", r"\bqan acilib\b",
    r"\byixilmisam\b", r"\byixildim\b", r"\bdura bilmirem\b",
    r"\byangin (var|basladi|cixib)\b", r"\bqaz iyi\b", r"\btustu cixir\b",
    r"\bureyim (dayanir|agriyir|sixilir|sancir|partlayir)\b",
    r"\bdos qefesim\w*\b.*\b(agri|sixilma|sanci)\w*\b",
    r"\binsult\b", r"\binfarkt\b", r"\biflic\b", r"\bqicolma\b",
    r"\bkomek (edin|eleyin|cagir|cagirin)\b", r"\bimdad\b",
]

# Mentions of an emergency service / number. These only escalate when combined with an
# action verb (call, dial, send, come) or a distress signal - never on their own, so that
# questions like "112 nömrəsi neçədir?" stay INFORMATION.
EMERGENCY_SERVICE_PATTERNS = [
    r"\b10[1-4]\b", r"\b112\b", r"\btecili (tibbi )?yardim\w*\b", r"\bskoriy\b",
    r"\bskoroy\b", r"\bpolis\w*\b", r"\bxilasedici\w*\b", r"\bpojarni\w*\b",
    r"\breanimasiya\b", r"\bfovqelade\b",
]
# "həkim" alone is too broad ("Həkim Nigar xanıma zəng et" is a CALL): only
# summoning a doctor counts.
EMERGENCY_DISTRESS_PATTERNS += [
    r"\bhekim (cagir\w*|gonder\w*|gelsin|lazimdir)\b",
    r"\btecili hekim\b",
]
EMERGENCY_ACTION_PATTERNS = [
    r"\bcagir\w*\b", r"\bzeng (et|ele|edin|eleyin|vur)\b", r"\byig\b", r"\byigin\b",
    r"\bgelsin\b", r"\bgonder\w*\b", r"\bxeber (ver|ele|edin|verin)\b",
    r"\btez\b", r"\btecili\b.*\b(lazimdir|gelsin|cagir\w*)\b",
]
# "Təcili yardım!" / "Skorıy!" uttered alone is a cry for help, not a question.
EMERGENCY_STANDALONE_PATTERNS = [
    r"^(tecili (tibbi )?yardim|skoriy|komek|imdad)( tez)?$",
]

# Kept for backwards compatibility with code importing the old flat list.
EMERGENCY_SAFETY_KEYWORDS = EMERGENCY_DISTRESS_PATTERNS


def _any(patterns, text: str) -> bool:
    return any(re.search(p, text) for p in patterns)


class ModelNotLoadedError(RuntimeError):
    """Raised when the intent model artifact is missing and no safety rule applies."""


def _load_metadata_threshold(metadata_path: Path) -> Optional[float]:
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            value = json.load(f).get("clarification_threshold")
        return float(value) if value is not None else None
    except (OSError, ValueError, TypeError):
        return None


class IntentPredictor:
    """
    Production inference engine with confidence scoring, safety guardrails,
    and entity enrichment.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        confidence_threshold: Optional[float] = None,
        metadata_path: Path = METADATA_PATH,
    ):
        self.model_path = Path(model_path)
        if confidence_threshold is None:
            confidence_threshold = _load_metadata_threshold(Path(metadata_path))
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else DEFAULT_CONFIDENCE_THRESHOLD
        )
        self._pipeline = None
        self._classes = []
        self._load_model()

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None

    def _load_model(self):
        if self.model_path.exists():
            self._pipeline = joblib.load(self.model_path)
            self._classes = [str(c) for c in self._pipeline.classes_]
        else:
            self._pipeline = None
            self._classes = []

    def check_emergency_safety_guardrail(self, text: str) -> bool:
        """
        Independent safety check for severe medical distress or household disasters.
        Escalates on distress signals, or on an emergency service/number combined with
        an action verb. A bare number or a question about a number does not escalate.
        """
        folded = fold_az_text(text)
        if not folded:
            return False
        if _any(EMERGENCY_DISTRESS_PATTERNS, folded):
            return True
        if _any(EMERGENCY_STANDALONE_PATTERNS, folded):
            return True
        if _any(EMERGENCY_SERVICE_PATTERNS, folded) and _any(EMERGENCY_ACTION_PATTERNS, folded):
            return True
        return False

    def predict_raw(self, text: str):
        """Returns (intent, confidence) from the ML model only (no rules, no threshold)."""
        if self._pipeline is None:
            self._load_model()
        if self._pipeline is None:
            raise ModelNotLoadedError(f"Model file not found at {self.model_path}")
        probas = self._pipeline.predict_proba([text])[0]
        max_idx = int(np.argmax(probas))
        return self._classes[max_idx], float(probas[max_idx])

    def predict(self, text: str) -> Dict[str, Any]:
        """
        Main decision function.
        Returns:
        {
            "intent": str,
            "confidence": float,
            "requires_clarification": bool,
            "entities": dict,
            "recommended_action": str,
            "safety_escalation": bool
        }
        Raises ModelNotLoadedError if the model is missing and the safety guardrail
        did not fire (emergencies are still dispatched without a model).
        """
        if not text or not text.strip():
            return {
                "intent": "OTHER",
                "confidence": 0.0,
                "requires_clarification": True,
                "entities": {},
                "recommended_action": "CLARIFY",
                "safety_escalation": False,
                "message": "Boş mətn daxil edildi. Zəhmət olmasa istəyinizi bildirin."
            }

        # Step 1: Emergency Safety Check (Independent life-safety workflow)
        is_hard_emergency = self.check_emergency_safety_guardrail(text)

        # Step 2: ML Model Inference
        try:
            predicted_intent, confidence = self.predict_raw(text)
        except ModelNotLoadedError:
            if not is_hard_emergency:
                raise
            predicted_intent, confidence = "EMERGENCY", 0.0

        # Override or escalate if safety guardrail triggers
        safety_escalation = False
        if is_hard_emergency:
            predicted_intent = "EMERGENCY"
            confidence = max(confidence, 0.98)
            safety_escalation = True

        # Step 3: Entity Extraction (specifically for ORDER intent)
        entities = {}
        if predicted_intent == "ORDER":
            order_data = extract_order_entities(text)
            entities = {"items": order_data["items"]}

        # Step 4: Decision & Recommended Action Logic
        requires_clarification = False
        recommended_action = "CLARIFY"

        if predicted_intent == "EMERGENCY":
            # Emergency never requires clarification - time is critical
            requires_clarification = False
            recommended_action = "EMERGENCY_DISPATCH"

        elif confidence < self.confidence_threshold:
            # Low confidence - ask user to clarify rather than risk incorrect execution
            requires_clarification = True
            recommended_action = "CLARIFY"

        elif predicted_intent == "ORDER":
            # For orders, check if item information is complete
            items = entities.get("items", [])
            has_incomplete_items = any(
                it.get("quantity") is None or it.get("unit") is None
                for it in items
            )
            if not items or has_incomplete_items:
                requires_clarification = True
                recommended_action = "CLARIFY_ORDER_DETAILS"
            else:
                requires_clarification = False
                recommended_action = "PROCESS_ORDER"

        elif predicted_intent == "CALL":
            recommended_action = "INITIATE_CALL"

        elif predicted_intent == "REMINDER":
            recommended_action = "SCHEDULE_REMINDER"

        elif predicted_intent == "INFORMATION":
            recommended_action = "FETCH_INFORMATION"

        else:
            recommended_action = "ENGAGE_CHITCHAT"

        return {
            "intent": predicted_intent,
            "confidence": round(confidence, 4),
            "requires_clarification": requires_clarification,
            "entities": entities,
            "recommended_action": recommended_action,
            "safety_escalation": safety_escalation,
        }
