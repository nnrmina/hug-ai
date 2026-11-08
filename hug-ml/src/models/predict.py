"""
Inference and Decision Logic Module for HUG AI Voice Assistant.

Combines:
1. Genuine trained Decision Tree pipeline (TF-IDF + DecisionTreeClassifier).
2. Probabilistic confidence estimation via predict_proba().
3. Configurable confidence thresholds (returns CLARIFY if uncertain).
4. Separate safety workflow for EMERGENCY detection (rule-augmented guardrail).
5. Integration with Order Entity Extractor for structured downstream dispatch.
"""

import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import joblib
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "decision_tree_pipeline.joblib"

sys.path.insert(0, str(BASE_DIR))
from src.entities.extract_entities import extract_order_entities
from src.preprocessing.text_preprocessing import normalize_az_text

# High-priority emergency trigger keywords for critical safety guardrail
EMERGENCY_SAFETY_KEYWORDS = [
    r"\bölürəm\b", r"\bolurem\b", r"\btəcili yardım\b", r"\btecili yardim\b",
    r"\bnəfəs ala bilmirəm\b", r"\bnefes ala bilmirem\b", r"\bboğuluram\b", r"\bboguluram\b",
    r"\b103\b", r"\b112\b", r"\bhuşumu itirirəm\b", r"\bhushumu itirirem\b",
    r"\bqanaxma\b", r"\byıxılmışam\b", r"\byixilmisam\b", r"\bdura bilmirəm\b",
    r"\byanğın\b", r"\byangin\b", r"\bqaz iyi\b", r"\bskorıy\b", r"\bskoriy\b",
    r"\bürəyim dayanır\b", r"\bureyim dayanir\b", r"\binsult\b", r"\binfarkt\b"
]


class IntentPredictor:
    """
    Production inference engine with confidence scoring, safety guardrails,
    and entity enrichment.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        confidence_threshold: float = 0.45,
    ):
        self.model_path = Path(model_path)
        self.confidence_threshold = confidence_threshold
        self._pipeline = None
        self._classes = []
        self._load_model()

    def _load_model(self):
        if self.model_path.exists():
            self._pipeline = joblib.load(self.model_path)
            self._classes = list(self._pipeline.named_steps["dt"].classes_)
        else:
            self._pipeline = None
            self._classes = []

    def check_emergency_safety_guardrail(self, text: str) -> bool:
        """
        Independent safety check for severe medical distress or household disasters.
        Ensures emergency situations are never dropped or misclassified due to ambiguity.
        """
        lowered = text.lower()
        for kw_pattern in EMERGENCY_SAFETY_KEYWORDS:
            if re.search(kw_pattern, lowered, re.IGNORECASE):
                return True
        return False

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
        if self._pipeline is None:
            self._load_model()

        if self._pipeline is not None:
            probas = self._pipeline.predict_proba([text])[0]
            max_idx = int(np.argmax(probas))
            predicted_intent = self._classes[max_idx]
            confidence = float(probas[max_idx])
        else:
            predicted_intent = "OTHER"
            confidence = 0.0

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
            requires_clarification = False
            recommended_action = "INITIATE_CALL"

        elif predicted_intent == "REMINDER":
            requires_clarification = False
            recommended_action = "SCHEDULE_REMINDER"

        elif predicted_intent == "INFORMATION":
            requires_clarification = False
            recommended_action = "FETCH_INFORMATION"

        else:
            requires_clarification = False
            recommended_action = "ENGAGE_CHITCHAT"

        return {
            "intent": predicted_intent,
            "confidence": round(confidence, 4),
            "requires_clarification": requires_clarification,
            "entities": entities,
            "recommended_action": recommended_action,
            "safety_escalation": safety_escalation,
        }
