"""
Model Training Script for the HUG Azerbaijani Intent Classifier.

Workflow:
1. Loads the (synthetic) dataset from data/hug_intent_dataset.csv.
2. Builds leakage-safe groups: the generator's template_id, further merged with any
   utterances whose token-set Jaccard similarity is >= 0.6 (union-find), so that
   near-duplicate template fills never span train / validation / test.
3. Stratified *group* split (~70% train / ~15% validation / ~15% test) persisted to
   data/processed/ for reproducible benchmarking.
4. Hyperparameter / feature search on the validation set:
   - TF-IDF word n-grams (1-2, keeps 1-char tokens), char_wb n-grams (2-5), or both
   - LogisticRegression (multinomial, C grid) and
     LinearSVC wrapped in CalibratedClassifierCV (sigmoid, group-aware CV folds)
   - The old DecisionTree configuration is kept as a reference baseline.
5. Selects the best model by 0.7 * macro-F1 + 0.3 * EMERGENCY recall (tie-break: log-loss).
6. Tunes the clarification threshold on development data (grouped 5-fold out-of-fold
   predictions over train+val) using the end-to-end IntentPredictor logic
   (guardrail + threshold) and the cost model in end_to_end.py.
7. Refits the selected configuration on train+val and saves models/intent_pipeline.joblib
   and models/model_metadata.json.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score, log_loss
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
MODEL_FILENAME = "intent_pipeline.joblib"

sys.path.insert(0, str(BASE_DIR))
from src.models.end_to_end import score_end_to_end  # noqa: E402
from src.models.predict import IntentPredictor, fold_az_text  # noqa: E402
from src.preprocessing.text_preprocessing import normalize_az_text  # noqa: E402

RANDOM_SEED = 42
JACCARD_GROUP_THRESHOLD = 0.6
MAX_GROUP_SIZE = 30  # cap on Jaccard merging (template groups themselves are never split)
TOKEN_PATTERN = r"(?u)\b\w+\b"  # keep 1-char tokens (e.g. "2", "o")
THRESHOLD_GRID = [round(x, 3) for x in np.arange(0.20, 0.801, 0.025)]


# ---------------------------------------------------------------------------
# Leakage-safe grouping and splitting
# ---------------------------------------------------------------------------
def build_groups(
    df: pd.DataFrame,
    threshold: float = JACCARD_GROUP_THRESHOLD,
    max_group_size: int = MAX_GROUP_SIZE,
) -> np.ndarray:
    """template_id groups merged by token-set Jaccard >= threshold (union-find, size-capped)."""
    n = len(df)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    if "template_id" in df.columns:
        first_of_template: Dict[str, int] = {}
        for i, tid in enumerate(df["template_id"].fillna("").astype(str)):
            if not tid:
                continue
            if tid in first_of_template:
                union(first_of_template[tid], i)
            else:
                first_of_template[tid] = i

    size = [0] * n
    for i in range(n):
        size[find(i)] += 1

    # Collect near-duplicate pairs and merge strongest first. Without a cap, chains of
    # pairwise-similar fills (e.g. all "<day> səhər saat 10-da ... xatırlat" variants)
    # collapse into one giant group that makes stratified splitting impossible.
    token_sets = [set(fold_az_text(t).split()) for t in df["text"]]
    pairs = []
    for i in range(n):
        a = token_sets[i]
        if not a:
            continue
        for j in range(i + 1, n):
            b = token_sets[j]
            if b:
                jac = len(a & b) / len(a | b)
                if jac >= threshold:
                    pairs.append((jac, i, j))
    pairs.sort(reverse=True)
    for _, i, j in pairs:
        ri, rj = find(i), find(j)
        if ri == rj or size[ri] + size[rj] > max_group_size:
            continue
        parent[rj] = ri
        size[ri] += size[rj]

    roots = [find(i) for i in range(n)]
    remap = {r: k for k, r in enumerate(dict.fromkeys(roots))}
    return np.array([remap[r] for r in roots])


def _group_fold(X, y, groups, n_splits: int, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    sgkf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    rest_idx, held_idx = next(sgkf.split(X, y, groups))
    return rest_idx, held_idx


def load_and_split_data(
    csv_path: Path = DATA_DIR / "hug_intent_dataset.csv",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stratified group split: ~15% test, ~15% val, ~70% train (no group spans two splits)."""
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["text", "intent"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"].str.len() > 0].reset_index(drop=True)
    df["group"] = build_groups(df)

    # 1/7 ~= 14.3% test
    rest_idx, test_idx = _group_fold(df["text"], df["intent"], df["group"], 7, RANDOM_SEED)
    rest = df.iloc[rest_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    # 1/6 of the remaining ~85.7% ~= 14.3% val
    tr_idx, val_idx = _group_fold(rest["text"], rest["intent"], rest["group"], 6, RANDOM_SEED)
    train_df = rest.iloc[tr_idx].reset_index(drop=True)
    val_df = rest.iloc[val_idx].reset_index(drop=True)

    assert not (set(train_df["group"]) & set(test_df["group"]))
    assert not (set(train_df["group"]) & set(val_df["group"]))
    assert not (set(val_df["group"]) & set(test_df["group"]))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED_DIR / "train.csv", index=False)
    val_df.to_csv(PROCESSED_DIR / "val.csv", index=False)
    test_df.to_csv(PROCESSED_DIR / "test.csv", index=False)

    return train_df, val_df, test_df


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------
def make_vectorizer(kind: str):
    word = TfidfVectorizer(
        preprocessor=normalize_az_text,
        token_pattern=TOKEN_PATTERN,
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
    )
    char = TfidfVectorizer(
        preprocessor=normalize_az_text,
        analyzer="char_wb",
        ngram_range=(2, 5),
        min_df=1,
        sublinear_tf=True,
    )
    if kind == "word":
        return word
    if kind == "char":
        return char
    if kind == "word+char":
        return FeatureUnion([("word", word), ("char", char)])
    raise ValueError(kind)


def make_classifier(config: Dict, groups: Optional[np.ndarray], n_samples: int):
    clf = config["classifier"]
    if clf == "logreg":
        return LogisticRegression(
            C=config["C"], class_weight=config.get("class_weight"),
            max_iter=5000, random_state=RANDOM_SEED,
        )
    if clf == "linearsvc_calibrated":
        # Group-aware calibration folds so calibration is not fit on near-duplicates
        cv = 5
        if groups is not None:
            cv = list(GroupKFold(n_splits=5).split(np.zeros(n_samples), groups=groups))
        return CalibratedClassifierCV(
            LinearSVC(C=config["C"], class_weight=config.get("class_weight"), random_state=RANDOM_SEED),
            method="sigmoid",
            cv=cv,
        )
    if clf == "decision_tree_baseline":
        return DecisionTreeClassifier(
            max_depth=50, min_samples_split=4, min_samples_leaf=2, random_state=RANDOM_SEED,
        )
    raise ValueError(clf)


def build_pipeline(config: Dict, groups: Optional[np.ndarray], n_samples: int) -> Pipeline:
    vec_kind = config.get("features", "word")
    if config["classifier"] == "decision_tree_baseline":
        # Old configuration: default token_pattern, word 1-2 grams
        vec = TfidfVectorizer(preprocessor=normalize_az_text, ngram_range=(1, 2), sublinear_tf=True)
    else:
        vec = make_vectorizer(vec_kind)
    return Pipeline([("tfidf", vec), ("clf", make_classifier(config, groups, n_samples))])


def candidate_configs() -> List[Dict]:
    configs: List[Dict] = [{"classifier": "decision_tree_baseline", "features": "word"}]
    for features in ["word", "char", "word+char"]:
        for C in [1.0, 4.0, 16.0]:
            configs.append({"classifier": "logreg", "features": features, "C": C, "class_weight": "balanced"})
        for C in [0.1, 0.5, 2.0]:
            configs.append({"classifier": "linearsvc_calibrated", "features": features, "C": C, "class_weight": "balanced"})
    return configs


def predictor_from_pipeline(pipe: Pipeline, threshold: float) -> IntentPredictor:
    pred = IntentPredictor(model_path=MODELS_DIR / "__nonexistent__.joblib", confidence_threshold=threshold)
    pred._pipeline = pipe
    pred._classes = [str(c) for c in pipe.classes_]
    return pred


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
def train_and_select_best_model(train_df: pd.DataFrame, val_df: pd.DataFrame) -> Tuple[Pipeline, Dict]:
    X_train, y_train = train_df["text"], train_df["intent"]
    X_val, y_val = val_df["text"], val_df["intent"]
    groups = train_df["group"].values if "group" in train_df else None

    best = None
    records = []
    for config in candidate_configs():
        pipe = build_pipeline(config, groups, len(train_df))
        pipe.fit(X_train, y_train)
        y_pred = pipe.predict(X_val)
        proba = pipe.predict_proba(X_val)

        macro_f1 = f1_score(y_val, y_pred, average="macro", zero_division=0)
        rep = classification_report(y_val, y_pred, output_dict=True, zero_division=0)
        emergency_recall = rep.get("EMERGENCY", {}).get("recall", 0.0)
        ll = log_loss(y_val, proba, labels=pipe.classes_)
        selection_metric = 0.70 * macro_f1 + 0.30 * emergency_recall

        rec = {
            "params": config,
            "val_accuracy": round(float((y_pred == y_val.values).mean()), 4),
            "val_macro_f1": round(macro_f1, 4),
            "val_emergency_recall": round(emergency_recall, 4),
            "val_log_loss": round(ll, 4),
            "selection_metric": round(selection_metric, 4),
        }
        records.append(rec)
        print(f"  {config} -> macroF1={macro_f1:.4f} emergR={emergency_recall:.3f} logloss={ll:.3f}")

        if config["classifier"] == "decision_tree_baseline":
            continue  # reference only
        key = (round(selection_metric, 4), -ll)
        if best is None or key > best[0]:
            best = (key, config, pipe)

    _, best_config, best_pipe = best
    return best_pipe, {
        "best_params": best_config,
        "best_selection_metric": best[0][0],
        "selection_rule": "0.7 * val macro-F1 + 0.3 * val EMERGENCY recall, tie-break lower log-loss; "
                          "decision tree is a reference baseline and is not selectable",
        "trials": records,
    }


class _OOFProbaLookup:
    """Minimal pipeline stand-in returning precomputed out-of-fold probabilities by text."""

    def __init__(self, classes, proba_by_text: Dict[str, np.ndarray]):
        self.classes_ = np.array(classes)
        self._proba = proba_by_text

    def predict_proba(self, texts):
        return np.vstack([self._proba[t] for t in texts])


def tune_clarification_threshold(config: Dict, dev_df: pd.DataFrame, n_splits: int = 5) -> Dict:
    """
    Tunes the clarification threshold on development data (train+val) using grouped
    out-of-fold probabilities, so every development utterance is scored by a model that
    never saw its template group. The single 15% validation split alone contains too
    few errors to tune a threshold reliably.
    """
    proba_by_text: Dict[str, np.ndarray] = {}
    classes = None
    gkf = GroupKFold(n_splits=n_splits)
    for tr_idx, ho_idx in gkf.split(dev_df["text"], dev_df["intent"], dev_df["group"]):
        tr, ho = dev_df.iloc[tr_idx], dev_df.iloc[ho_idx]
        pipe = build_pipeline(config, tr["group"].values, len(tr))
        pipe.fit(tr["text"], tr["intent"])
        if classes is None:
            classes = list(pipe.classes_)
        assert list(pipe.classes_) == classes
        for t, pr in zip(ho["text"], pipe.predict_proba(ho["text"])):
            proba_by_text[t] = pr
    lookup = _OOFProbaLookup(classes, proba_by_text)

    oof_pred = [classes[int(np.argmax(proba_by_text[t]))] for t in dev_df["text"]]
    oof_model_only = {
        "accuracy": round(float(np.mean(np.array(oof_pred) == dev_df["intent"].values)), 4),
        "f1_macro": round(f1_score(dev_df["intent"], oof_pred, average="macro", zero_division=0), 4),
        "log_loss": round(log_loss(dev_df["intent"], lookup.predict_proba(dev_df["text"]), labels=classes), 4),
    }

    rows = []
    for th in THRESHOLD_GRID:
        m = score_end_to_end(predictor_from_pipeline(lookup, th), dev_df["text"], dev_df["intent"])
        m.pop("errors")
        rows.append({"threshold": th, **m})
    best = min(rows, key=lambda r: (r["decision_cost_per_utterance"], r["threshold"]))
    return {
        "chosen_threshold": best["threshold"],
        "objective": "min decision_cost_per_utterance (wrong action=1.0, clarification=0.25, "
                     "missed emergency=5.0) on grouped 5-fold out-of-fold predictions over train+val",
        "chosen_oof_metrics": best,
        "oof_model_only_metrics": oof_model_only,
        "grid": rows,
    }


def run_training():
    print("Step 1: Building leakage-safe groups and splitting dataset...")
    train_df, val_df, test_df = load_and_split_data()
    print(f"Dataset split: Train={len(train_df)}, Val={len(val_df)}, Test={len(test_df)}; "
          f"groups={train_df['group'].nunique() + val_df['group'].nunique() + test_df['group'].nunique()}")

    print("\nStep 2: Model/feature search on validation data...")
    best_pipe, search = train_and_select_best_model(train_df, val_df)
    print(f"Selected: {search['best_params']} (metric {search['best_selection_metric']:.4f})")

    print("\nStep 3: Tuning clarification threshold (end-to-end, grouped OOF on train+val)...")
    train_val_df = pd.concat([train_df, val_df], ignore_index=True)
    threshold_info = tune_clarification_threshold(search["best_params"], train_val_df)
    th = threshold_info["chosen_threshold"]
    cm = threshold_info["chosen_oof_metrics"]
    print(f"Threshold={th}: OOF coverage={cm['coverage']}, acc_on_executed={cm['accuracy_on_executed']}, "
          f"error_capture={cm['error_capture_rate']}, e2e_acc={cm['intent_accuracy']}")
    print(f"Grouped 5-fold OOF (model only): {threshold_info['oof_model_only_metrics']}")

    print("\nStep 4: Refitting selected configuration on Train+Val...")
    final_pipe = build_pipeline(search["best_params"], train_val_df["group"].values, len(train_val_df))
    final_pipe.fit(train_val_df["text"], train_val_df["intent"])

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = MODELS_DIR / MODEL_FILENAME
    joblib.dump(final_pipe, model_path)
    print(f"Model saved to {model_path}")

    params = search["best_params"]
    meta = {
        "model_type": f"{params['classifier']} (C={params.get('C')}, class_weight={params.get('class_weight')})",
        "vectorizer": {
            "word": f"TfidfVectorizer(ngram_range=(1,2), token_pattern={TOKEN_PATTERN!r}, sublinear_tf=True)",
            "char": "TfidfVectorizer(analyzer='char_wb', ngram_range=(2,5), sublinear_tf=True)",
            "word+char": "FeatureUnion(word, char)",
        }[params["features"]],
        "model_file": MODEL_FILENAME,
        "classes": sorted(str(c) for c in final_pipe.classes_),
        "hyperparameters": params,
        "clarification_threshold": th,
        "split": {
            "method": "StratifiedGroupKFold (test 1/7, val 1/6 of remainder); groups = generator "
                      f"template_id merged by token Jaccard >= {JACCARD_GROUP_THRESHOLD}",
            "train": len(train_df), "val": len(val_df), "test": len(test_df),
        },
        "dataset_note": "Fully synthetic, template-generated data. Not representative of real "
                        "elderly ASR transcripts; metrics are optimistic for production.",
        "validation_search": search,
        "threshold_tuning": threshold_info,
    }
    with open(MODELS_DIR / "model_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    run_training()
