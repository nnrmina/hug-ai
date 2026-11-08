"""
End-to-end scoring of the full IntentPredictor.predict() decision logic
(ML model + emergency guardrail + clarification threshold + order-detail checks).

Shared by train.py (threshold tuning on validation) and evaluate.py (test report).
"""

from typing import Dict, Iterable, List

import numpy as np

# Cost model used to tune the clarification threshold on validation data:
# executing a wrong action is far worse than asking the user to repeat/clarify.
COST_WRONG_ACTION = 1.0
COST_CLARIFICATION = 0.25
# Missing a real emergency is the worst outcome.
COST_MISSED_EMERGENCY = 5.0


def score_end_to_end(predictor, texts: Iterable[str], labels: Iterable[str]) -> Dict:
    texts = list(texts)
    labels = list(labels)
    results = [predictor.predict(t) for t in texts]

    n = len(labels)
    intents = [r["intent"] for r in results]
    low_conf_clarify = [r["recommended_action"] == "CLARIFY" for r in results]
    any_clarify = [bool(r["requires_clarification"]) for r in results]
    correct = [p == y for p, y in zip(intents, labels)]

    wrong_executed = sum(1 for c, cl in zip(correct, low_conf_clarify) if not c and not cl)
    wrong_total = sum(1 for c in correct if not c)
    wrong_caught = sum(1 for c, cl in zip(correct, low_conf_clarify) if not c and cl)
    executed = [not cl for cl in low_conf_clarify]
    executed_correct = sum(1 for c, e in zip(correct, executed) if c and e)

    emerg_idx = [i for i, y in enumerate(labels) if y == "EMERGENCY"]
    emerg_hit = sum(1 for i in emerg_idx if intents[i] == "EMERGENCY")
    pred_emerg = [i for i, p in enumerate(intents) if p == "EMERGENCY"]
    emerg_prec_hit = sum(1 for i in pred_emerg if labels[i] == "EMERGENCY")

    missed_emergencies = len(emerg_idx) - emerg_hit
    cost = (
        COST_WRONG_ACTION * wrong_executed
        + COST_CLARIFICATION * sum(low_conf_clarify)
        + COST_MISSED_EMERGENCY * missed_emergencies
    ) / max(n, 1)

    errors: List[Dict] = [
        {
            "text": t,
            "true_intent": y,
            "predicted_intent": r["intent"],
            "confidence": r["confidence"],
            "recommended_action": r["recommended_action"],
        }
        for t, y, r, c in zip(texts, labels, results, correct)
        if not c
    ]

    return {
        "samples": n,
        "intent_accuracy": round(float(np.mean(correct)) if n else 0.0, 4),
        "clarification_rate_low_confidence": round(sum(low_conf_clarify) / max(n, 1), 4),
        "clarification_rate_any": round(sum(any_clarify) / max(n, 1), 4),
        "coverage": round(sum(executed) / max(n, 1), 4),
        "accuracy_on_executed": round(executed_correct / max(sum(executed), 1), 4),
        "wrong_predictions": wrong_total,
        "wrong_predictions_sent_to_clarification": wrong_caught,
        "wrong_actions_executed": wrong_executed,
        "error_capture_rate": round(wrong_caught / wrong_total, 4) if wrong_total else 1.0,
        "emergency_recall": round(emerg_hit / len(emerg_idx), 4) if emerg_idx else None,
        "emergency_precision": round(emerg_prec_hit / len(pred_emerg), 4) if pred_emerg else None,
        "decision_cost_per_utterance": round(cost, 4),
        "errors": errors,
    }
