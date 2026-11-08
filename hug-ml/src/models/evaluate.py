"""
Model Evaluation Module for the HUG Azerbaijani Intent Classifier.

Evaluates on the untouched, group-split test set (data/processed/test.csv):
1. Model-only: the raw ML pipeline (argmax of calibrated probabilities).
2. End-to-end: IntentPredictor.predict() = ML + emergency guardrail +
   clarification threshold + order-detail checks (what the API actually returns).
3. Reference baseline: the previous DecisionTree configuration retrained on the
   same train+val data and scored on the same test set.

Generates:
- reports/metrics.json
- reports/classification_report.txt
- reports/confusion_matrix.png (model-only and end-to-end)
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

sys.path.insert(0, str(BASE_DIR))
from src.models.end_to_end import score_end_to_end  # noqa: E402
from src.models.predict import MODEL_PATH, IntentPredictor  # noqa: E402
from src.models.train import build_pipeline  # noqa: E402


def expected_calibration_error(y_true, proba, classes, n_bins: int = 10) -> float:
    conf = proba.max(axis=1)
    pred = np.array(classes)[proba.argmax(axis=1)]
    correct = (pred == np.asarray(y_true)).astype(float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def _classification_block(y_true, y_pred, classes) -> Dict:
    rep = classification_report(y_true, y_pred, labels=classes, output_dict=True, zero_division=0)
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision_macro": round(precision_score(y_true, y_pred, average="macro", zero_division=0), 4),
        "recall_macro": round(recall_score(y_true, y_pred, average="macro", zero_division=0), 4),
        "f1_macro": round(f1_score(y_true, y_pred, average="macro", zero_division=0), 4),
        "f1_weighted": round(f1_score(y_true, y_pred, average="weighted", zero_division=0), 4),
        "emergency_recall": round(rep.get("EMERGENCY", {}).get("recall", 0.0), 4),
        "emergency_f1": round(rep.get("EMERGENCY", {}).get("f1-score", 0.0), 4),
        "class_level_metrics": {
            c: {
                "precision": round(rep[c]["precision"], 4),
                "recall": round(rep[c]["recall"], 4),
                "f1_score": round(rep[c]["f1-score"], 4),
                "support": int(rep[c]["support"]),
            }
            for c in classes if c in rep
        },
    }


def run_evaluation(
    model_path: Path = MODEL_PATH,
    test_csv: Path = PROCESSED_DIR / "test.csv",
) -> Dict:
    if not model_path.exists():
        raise FileNotFoundError(f"Model file not found at {model_path}. Run training first.")
    if not test_csv.exists():
        raise FileNotFoundError(f"Test CSV not found at {test_csv}. Run training split first.")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    pipeline = joblib.load(model_path)
    test_df = pd.read_csv(test_csv)
    X_test = test_df["text"].astype(str)
    y_test = test_df["intent"].astype(str)
    classes = [str(c) for c in pipeline.classes_]

    # ---- 1. Model-only ----
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)
    model_only = _classification_block(y_test, y_pred, classes)
    model_only["log_loss"] = round(log_loss(y_test, y_proba, labels=classes), 4)
    model_only["expected_calibration_error"] = round(expected_calibration_error(y_test, y_proba, classes), 4)
    model_only["mean_confidence"] = round(float(y_proba.max(axis=1).mean()), 4)
    model_errors: List[Dict] = [
        {"text": t, "true_intent": yt, "predicted_intent": yp, "predicted_confidence": round(float(pr.max()), 4)}
        for t, yt, yp, pr in zip(X_test, y_test, y_pred, y_proba) if yt != yp
    ]

    # ---- 2. End-to-end (IntentPredictor.predict) ----
    predictor = IntentPredictor(model_path=model_path)
    e2e = score_end_to_end(predictor, X_test, y_test)
    e2e_pred = [predictor.predict(t)["intent"] for t in X_test]
    e2e.update({k: v for k, v in _classification_block(y_test, e2e_pred, classes).items()
                if k in ("f1_macro", "class_level_metrics")})
    e2e["clarification_threshold"] = predictor.confidence_threshold

    # ---- 3. Reference baseline: previous DecisionTree config on the same split ----
    baseline = None
    train_csv, val_csv = PROCESSED_DIR / "train.csv", PROCESSED_DIR / "val.csv"
    if train_csv.exists() and val_csv.exists():
        dev = pd.concat([pd.read_csv(train_csv), pd.read_csv(val_csv)], ignore_index=True)
        dt = build_pipeline({"classifier": "decision_tree_baseline"}, None, len(dev))
        dt.fit(dev["text"].astype(str), dev["intent"].astype(str))
        dt_pred = dt.predict(X_test)
        dt_proba = dt.predict_proba(X_test)
        baseline = _classification_block(y_test, dt_pred, classes)
        baseline.pop("class_level_metrics")
        baseline["expected_calibration_error"] = round(expected_calibration_error(y_test, dt_proba, classes), 4)
        baseline["mean_confidence"] = round(float(dt_proba.max(axis=1).mean()), 4)
        baseline["note"] = "DecisionTree(max_depth=50, min_samples_split=4, min_samples_leaf=2), same split"

    # ---- Reports ----
    with open(REPORTS_DIR / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write("=== HUG INTENT CLASSIFICATION REPORT ===\n")
        f.write("Dataset: SYNTHETIC template-generated utterances (not real elderly ASR transcripts).\n")
        f.write("Split: stratified GROUP split (template groups never span train/val/test).\n\n")
        f.write(f"Test samples: {len(test_df)}\n\n")
        f.write("--- 1. Model only (raw classifier) ---\n")
        f.write(f"Accuracy: {model_only['accuracy']:.4f} | Macro F1: {model_only['f1_macro']:.4f} | "
                f"EMERGENCY recall: {model_only['emergency_recall']:.4f} | ECE: {model_only['expected_calibration_error']:.4f}\n\n")
        f.write(classification_report(y_test, y_pred, labels=classes, zero_division=0))
        f.write("\n--- 2. End-to-end IntentPredictor.predict() (guardrail + threshold) ---\n")
        f.write(f"Intent accuracy: {e2e['intent_accuracy']:.4f} | Macro F1: {e2e['f1_macro']:.4f} | "
                f"Threshold: {e2e['clarification_threshold']}\n")
        f.write(f"Coverage (no low-confidence clarification): {e2e['coverage']:.4f} | "
                f"Accuracy on executed: {e2e['accuracy_on_executed']:.4f}\n")
        f.write(f"Wrong predictions: {e2e['wrong_predictions']} (sent to clarification: "
                f"{e2e['wrong_predictions_sent_to_clarification']}) | EMERGENCY recall: {e2e['emergency_recall']} | "
                f"EMERGENCY precision: {e2e['emergency_precision']}\n\n")
        f.write(classification_report(y_test, e2e_pred, labels=classes, zero_division=0))
        if baseline:
            f.write("\n--- 3. Reference: previous DecisionTree on the same split ---\n")
            f.write(f"Accuracy: {baseline['accuracy']:.4f} | Macro F1: {baseline['f1_macro']:.4f} | "
                    f"EMERGENCY recall: {baseline['emergency_recall']:.4f} | ECE: {baseline['expected_calibration_error']:.4f}\n")
        f.write("\n=== MODEL-ONLY ERRORS ===\n")
        for c in model_errors or [{"text": "(none)", "true_intent": "-", "predicted_intent": "-", "predicted_confidence": 0}]:
            f.write(f"- True: {c['true_intent']} | Pred: {c['predicted_intent']} (Conf: {c['predicted_confidence']:.2f})\n"
                    f"  Text: \"{c['text']}\"\n")
        f.write("\n=== END-TO-END ERRORS ===\n")
        for c in e2e["errors"] or [{"text": "(none)", "true_intent": "-", "predicted_intent": "-", "confidence": 0, "recommended_action": "-"}]:
            f.write(f"- True: {c['true_intent']} | Pred: {c['predicted_intent']} (Conf: {c['confidence']:.2f}, "
                    f"action: {c['recommended_action']})\n  Text: \"{c['text']}\"\n")

    fig, axes = plt.subplots(1, 2, figsize=(14, 6), dpi=150)
    for ax, preds, title in [
        (axes[0], y_pred, "Model only"),
        (axes[1], e2e_pred, "End-to-end (guardrail + threshold)"),
    ]:
        cm = confusion_matrix(y_test, preds, labels=classes)
        sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=classes, yticklabels=classes, ax=ax, cbar=False)
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("Predicted Intent")
        ax.set_ylabel("True Intent")
    fig.suptitle("HUG Intent Confusion Matrices (synthetic, group-split test set)", fontsize=12)
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png")
    plt.close(fig)

    e2e_errors = e2e.pop("errors")
    meta_path = MODELS_DIR / "model_metadata.json"
    model_type = None
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            model_type = json.load(f).get("model_type")

    metrics_summary = {
        "dataset_note": "Synthetic template-generated data; group split by template. Real elderly "
                        "ASR transcripts are required before trusting these numbers in production.",
        "model_type": model_type,
        "test_samples": len(test_df),
        "classes": classes,
        # Top-level keys kept for backwards compatibility (model-only numbers)
        "accuracy": model_only["accuracy"],
        "f1_macro": model_only["f1_macro"],
        "emergency_recall": model_only["emergency_recall"],
        "model_only": model_only,
        "end_to_end": e2e,
        "baseline_decision_tree": baseline,
        "total_errors": len(model_errors),
        "confused_samples": model_errors[:20],
        "end_to_end_errors": e2e_errors[:20],
    }
    with open(REPORTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2, ensure_ascii=False)

    return metrics_summary


if __name__ == "__main__":
    metrics = run_evaluation()
    mo, e2e, bl = metrics["model_only"], metrics["end_to_end"], metrics["baseline_decision_tree"]
    print("--- Test Evaluation Finished ---")
    print(f"Model-only:  accuracy={mo['accuracy']} macroF1={mo['f1_macro']} EMERGENCY recall={mo['emergency_recall']} ECE={mo['expected_calibration_error']}")
    print(f"End-to-end:  accuracy={e2e['intent_accuracy']} macroF1={e2e['f1_macro']} coverage={e2e['coverage']} "
          f"acc_on_executed={e2e['accuracy_on_executed']} errors_to_clarify={e2e['wrong_predictions_sent_to_clarification']}/{e2e['wrong_predictions']}")
    if bl:
        print(f"Baseline DT: accuracy={bl['accuracy']} macroF1={bl['f1_macro']} ECE={bl['expected_calibration_error']}")
    print(f"Reports saved to {REPORTS_DIR}")
