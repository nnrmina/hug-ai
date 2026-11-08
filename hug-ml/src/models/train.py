"""
Model Training Script for HUG Decision Tree Intent Classifier.

Workflow:
1. Loads validated dataset from data/hug_intent_dataset.csv.
2. Performs stratified split:
   - 70% Training
   - 15% Validation
   - 15% Testing (held out until final evaluation)
3. Persists split subsets to data/processed/ for reproducible benchmarking.
4. Explores DecisionTreeClassifier hyperparameters on the validation set:
   - max_depth
   - min_samples_split
   - min_samples_leaf
   - class_weight (balanced vs None)
5. Selects the best performing model prioritizing overall Macro F1 and EMERGENCY recall.
6. Serializes the final trained pipeline to models/decision_tree_pipeline.joblib.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Tuple

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import classification_report, f1_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

sys.path.insert(0, str(BASE_DIR))
from src.preprocessing.text_preprocessing import normalize_az_text

RANDOM_SEED = 42


def load_and_split_data(
    csv_path: Path = DATA_DIR / "hug_intent_dataset.csv",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads CSV and performs strict stratified split (70% train, 15% val, 15% test).
    """
    df = pd.read_csv(csv_path)

    # Clean missing or empty rows
    df = df.dropna(subset=["text", "intent"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 0]

    # First split: 85% train_val, 15% test
    train_val_df, test_df = train_test_split(
        df,
        test_size=0.15,
        stratify=df["intent"],
        random_state=RANDOM_SEED,
    )

    # Second split: 70% train, 15% val of the original total (15 / 85 = 0.17647)
    val_ratio_of_train_val = 0.15 / 0.85
    train_df, val_df = train_test_split(
        train_val_df,
        test_size=val_ratio_of_train_val,
        stratify=train_val_df["intent"],
        random_state=RANDOM_SEED,
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)

    return train_df, val_df, test_df


def train_and_select_best_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
) -> Tuple[Pipeline, Dict]:
    """
    Performs hyperparameter search on the validation set to choose
    the optimal Decision Tree configuration.
    """
    X_train, y_train = train_df["text"], train_df["intent"]
    X_val, y_val = val_df["text"], val_df["intent"]

    param_grid = [
        {"max_depth": 25, "min_samples_split": 2, "min_samples_leaf": 1, "class_weight": None},
        {"max_depth": 35, "min_samples_split": 2, "min_samples_leaf": 1, "class_weight": None},
        {"max_depth": 50, "min_samples_split": 2, "min_samples_leaf": 1, "class_weight": None},
        {"max_depth": 50, "min_samples_split": 4, "min_samples_leaf": 2, "class_weight": None},
        {"max_depth": None, "min_samples_split": 2, "min_samples_leaf": 1, "class_weight": None},
        {"max_depth": None, "min_samples_split": 4, "min_samples_leaf": 1, "class_weight": "balanced"},
        {"max_depth": 40, "min_samples_split": 2, "min_samples_leaf": 1, "class_weight": "balanced"},
    ]

    best_pipeline = None
    best_score = -1.0
    best_params = {}
    validation_records = []

    for params in param_grid:
        pipe = Pipeline([
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=normalize_az_text,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "dt",
                DecisionTreeClassifier(
                    max_depth=params["max_depth"],
                    min_samples_split=params["min_samples_split"],
                    min_samples_leaf=params["min_samples_leaf"],
                    class_weight=params["class_weight"],
                    random_state=RANDOM_SEED,
                ),
            ),
        ])

        pipe.fit(X_train, y_train)
        y_val_pred = pipe.predict(X_val)

        macro_f1 = f1_score(y_val, y_val_pred, average="macro", zero_division=0)
        weighted_f1 = f1_score(y_val, y_val_pred, average="weighted", zero_division=0)

        # Compute emergency specific recall
        report_dict = classification_report(y_val, y_val_pred, output_dict=True, zero_division=0)
        emergency_recall = report_dict.get("EMERGENCY", {}).get("recall", 0.0)

        # Composite score weighting safety: 70% macro F1 + 30% emergency recall
        selection_metric = 0.70 * macro_f1 + 0.30 * emergency_recall

        record = {
            "params": params,
            "val_macro_f1": round(macro_f1, 4),
            "val_weighted_f1": round(weighted_f1, 4),
            "val_emergency_recall": round(emergency_recall, 4),
            "selection_metric": round(selection_metric, 4),
        }
        validation_records.append(record)

        if selection_metric > best_score:
            best_score = selection_metric
            best_pipeline = pipe
            best_params = params

    search_summary = {
        "best_params": best_params,
        "best_selection_metric": best_score,
        "trials": validation_records,
    }

    return best_pipeline, search_summary


def run_training():
    print("Step 1: Loading and splitting dataset (70% train, 15% val, 15% test)...")
    train_df, val_df, test_df = load_and_split_data()
    print(f"Dataset split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}")

    print("\nStep 2: Training Decision Tree models with hyperparameter search on validation data...")
    best_pipe, search_results = train_and_select_best_model(train_df, val_df)
    print(f"Optimal parameters selected: {search_results['best_params']}")
    print(f"Validation Selection Metric (Macro F1 + Emergency): {search_results['best_selection_metric']:.4f}")

    # Retrain best configuration on Train+Val to leverage all available developmental data
    # (keeping test set completely pristine)
    print("\nStep 3: Refitting best model configuration on combined Train+Val set...")
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    best_pipe.fit(train_val_df["text"], train_val_df["intent"])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / "decision_tree_pipeline.joblib"
    joblib.dump(best_pipe, model_path)
    print(f"Model saved successfully to {model_path}")

    # Save training metadata
    meta = {
        "model_type": "DecisionTreeClassifier",
        "vectorizer": "TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)",
        "classes": sorted(list(best_pipe.named_steps["dt"].classes_)),
        "hyperparameters": search_results["best_params"],
        "validation_search": search_results,
    }
    with open(MODELS_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    run_training()

