"""
Model Evaluation Module for HUG Decision Tree Intent Classifier.

Evaluates the trained model on the untouched test set (data/processed/test.csv).
Generates:
- reports/metrics.json
- reports/classification_report.txt
- reports/confusion_matrix.png
- Detailed qualitative error analysis of confused classes.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

sys.path.insert(0, str(BASE_DIR))
from src.preprocessing.text_preprocessing import normalize_az_text


def run_evaluation(
    model_path: Path = MODELS_DIR / "decision_tree_pipeline.joblib",
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

    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)

    classes = list(pipeline.named_steps["dt"].classes_)

    # Quantitative metrics
    acc = accuracy_score(y_test, y_pred)
    prec_macro = precision_score(y_test, y_pred, average="macro", zero_division=0)
    prec_weighted = precision_score(y_test, y_pred, average="weighted", zero_division=0)
    rec_macro = recall_score(y_test, y_pred, average="macro", zero_division=0)
    rec_weighted = recall_score(y_test, y_pred, average="weighted", zero_division=0)
    f1_mac = f1_score(y_test, y_pred, average="macro", zero_division=0)
    f1_wgt = f1_score(y_test, y_pred, average="weighted", zero_division=0)

    # Class-level metrics
    clf_report_dict = classification_report(y_test, y_pred, output_dict=True, zero_division=0)
    clf_report_text = classification_report(y_test, y_pred, zero_division=0)

    cm = confusion_matrix(y_test, y_pred, labels=classes)

    # Identify confused pairs
    confused_cases: List[Dict] = []
    for i, (true_label, pred_label, text) in enumerate(zip(y_test, y_pred, X_test)):
        if true_label != pred_label:
            confused_cases.append({
                "text": text,
                "true_intent": true_label,
                "predicted_intent": pred_label,
                "predicted_confidence": float(np.max(y_proba[i]))
            })

    # Save classification report text
    with open(REPORTS_DIR / "classification_report.txt", "w", encoding="utf-8") as f:
        f.write("=== HUG DECISION TREE INTENT CLASSIFICATION REPORT ===\n\n")
        f.write(f"Test Dataset Samples: {len(test_df)}\n")
        f.write(f"Overall Accuracy:     {acc:.4f}\n")
        f.write(f"Macro F1-Score:       {f1_mac:.4f}\n")
        f.write(f"Weighted F1-Score:    {f1_wgt:.4f}\n")
        f.write(f"Macro Recall:         {rec_macro:.4f}\n")
        f.write(f"EMERGENCY Recall:     {clf_report_dict.get('EMERGENCY', {}).get('recall', 0.0):.4f}\n\n")
        f.write(clf_report_text)
        f.write("\n\n=== CONFUSED EXAMPLES ANALYSIS ===\n")
        if confused_cases:
            for case in confused_cases:
                f.write(f"- True: {case['true_intent']} | Pred: {case['predicted_intent']} (Conf: {case['predicted_confidence']:.2f})\n")
                f.write(f"  Text: \"{case['text']}\"\n\n")
        else:
            f.write("No classification errors on the test dataset!\n")

    # Plot Confusion Matrix
    plt.figure(figsize=(8, 6), dpi=150)
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=classes,
        yticklabels=classes,
        cbar=True,
    )
    plt.title("HUG Decision Tree Intent Confusion Matrix", fontsize=12, pad=12)
    plt.xlabel("Predicted Intent", fontsize=10)
    plt.ylabel("True Intent", fontsize=10)
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / "confusion_matrix.png")
    plt.close()

    # Save metrics JSON
    metrics_summary = {
        "test_samples": len(test_df),
        "accuracy": round(acc, 4),
        "precision_macro": round(prec_macro, 4),
        "precision_weighted": round(prec_weighted, 4),
        "recall_macro": round(rec_macro, 4),
        "recall_weighted": round(rec_weighted, 4),
        "f1_macro": round(f1_mac, 4),
        "f1_weighted": round(f1_wgt, 4),
        "emergency_recall": round(clf_report_dict.get("EMERGENCY", {}).get("recall", 0.0), 4),
        "emergency_f1": round(clf_report_dict.get("EMERGENCY", {}).get("f1-score", 0.0), 4),
        "classes": classes,
        "class_level_metrics": {
            cls_name: {
                "precision": round(clf_report_dict[cls_name]["precision"], 4),
                "recall": round(clf_report_dict[cls_name]["recall"], 4),
                "f1_score": round(clf_report_dict[cls_name]["f1-score"], 4),
                "support": int(clf_report_dict[cls_name]["support"]),
            }
            for cls_name in classes if cls_name in clf_report_dict
        },
        "total_errors": len(confused_cases),
        "confused_samples": confused_cases[:20],
    }

    with open(REPORTS_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics_summary, f, indent=2, ensure_ascii=False)

    return metrics_summary


if __name__ == "__main__":
    metrics = run_evaluation()
    print("--- Test Evaluation Finished ---")
    print(f"Accuracy:         {metrics['accuracy']}")
    print(f"Macro F1:         {metrics['f1_macro']}")
    print(f"EMERGENCY Recall: {metrics['emergency_recall']}")
    print(f"Report saved to:  {REPORTS_DIR / 'classification_report.txt'}")
    print(f"Matrix saved to:  {REPORTS_DIR / 'confusion_matrix.png'}")

