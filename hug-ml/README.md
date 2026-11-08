# HUG – Azerbaijani Voice-Intent ML Pipeline (TF-IDF + Calibrated Linear Classifier)

<p align="center">
  <b>MVP Machine Learning pipeline for voice-intent classification and entity extraction for elderly Azerbaijani users, trained on a <u>synthetic</u> dataset.</b>
</p>

---

## 1. Project Objective

**HUG** is an AI-powered digital life assistant designed primarily for elderly citizens in Azerbaijan. When an elderly user speaks naturally in Azerbaijani (e.g., *"Mənə Wolt-dan 2 kilo alma sifariş et"* or *"Mamama zvanok elə"*), the system must:

1. Ingest the speech-to-text Azerbaijani transcript.
2. Normalize and preserve native Azerbaijani letters (`ə`, `ı`, `ö`, `ü`, `ş`, `ç`, `ğ`) with Azerbaijani casing (`İ→i`, `I→ı`).
3. Classify the user's intent with a trained scikit-learn pipeline (word + char TF-IDF → `LinearSVC` wrapped in `CalibratedClassifierCV`).
4. Extract structured entities (products, quantities, units) if the intent is an order.
5. Decide whether user clarification is required (`CLARIFY`).
6. Apply a safety guardrail for medical and household emergencies (`EMERGENCY_DISPATCH`).
7. Return a structured JSON payload to the backend and mobile interface.

> **Honesty note:** the entire dataset is **synthetic** (template-generated and hand-written by the team; every row has `source=synthetic_*`). No real elderly users and no real speech-recognition (ASR) transcripts were used. The metrics below describe performance on clean synthetic text and are **optimistic** for production. Before relying on this model, collect and label real (consented, anonymised) ASR transcripts from elderly Azerbaijani speakers – with disfluencies, dialect, Russian code-switching and ASR errors – and re-evaluate and re-tune.

---

## 2. Project Directory Structure

```text
hug-ml/
├── data/
│   ├── hug_intent_dataset.csv          # 1,041 synthetic utterances (+ template_id group column)
│   ├── hug_entity_dataset.jsonl        # Order entity annotations (items, qty, unit)
│   └── processed/                      # Group-split train (728) / val (152) / test (161)
├── notebooks/exploratory_data_analysis.ipynb
├── src/
│   ├── data/generate_dataset.py        # Synthetic generator (emits template_id per row)
│   ├── data/validate_dataset.py        # Schema, duplicate & character validation
│   ├── preprocessing/text_preprocessing.py  # az_lower / normalize_az_text
│   ├── models/train.py                 # Group split, model/feature search, threshold tuning
│   ├── models/evaluate.py              # Model-only + end-to-end test metrics, DT baseline
│   ├── models/end_to_end.py            # Scores IntentPredictor.predict() (guardrail + threshold)
│   ├── models/predict.py               # Calibrated confidence, clarification, emergency guardrail
│   ├── entities/extract_entities.py    # Products, multi-word numbers, units
│   └── api/main.py                     # FastAPI (/predict, /health, /model-info, mock checkout)
├── models/
│   ├── intent_pipeline.joblib          # Trained scikit-learn Pipeline
│   └── model_metadata.json             # Selected config, search trials, tuned threshold
├── reports/
│   ├── classification_report.txt      # Model-only + end-to-end reports and error lists
│   ├── confusion_matrix.png            # Model-only and end-to-end confusion matrices
│   └── metrics.json                    # Machine-readable metrics
├── tests/test_pipeline.py              # 38 pytest tests
└── requirements.txt
```

---

## 3. Dataset (`data/hug_intent_dataset.csv`)

**1,041 unique, fully synthetic Azerbaijani utterances** across 6 intent classes. Many rows are template fills (one sentence frame × many products / names / days / symptoms), so the generator writes a `template_id` for every row; it is used to keep near-duplicates on the same side of the split.

| Intent | Samples | Example |
| :--- | :---: | :--- |
| `ORDER` | 175 | *"Mənə Wolt-dan 2 kilo alma və bir litr süd sifariş et."* |
| `CALL` | 175 | *"Böyük qızım Leylaya zəng elə görüm necədir."* |
| `REMINDER` | 176 | *"Saat 3-də təzyiq dərmanımı içməyi mənə xatırlat."* |
| `EMERGENCY` | 161 | *"Ürəyim bərk sıxılır, nəfəs ala bilmirəm, təcili 103 çağır!"* |
| `INFORMATION` | 177 | *"Bu gün Bakıda hava necə olacaq?"*, *"103-ə zəng etmək pulsuzdur?"* |
| `OTHER` | 177 | *"Allah razı olsun səndən bala, çox sağ ol."* |

Styles covered (all written, not recorded): polite elderly phrasing (*"ay bala"*, *"qızım"*), Baku colloquialisms and Russian loanwords (*"zvanok"*, *"zakaz"*, *"skorıy"*), short commands, and unaccented spellings (*"sifaris et"*, *"corek"*).

---

## 4. Model & Evaluation

### Pipeline
`utterance → normalize_az_text → [TF-IDF word 1–2 grams, token_pattern (?u)\b\w+\b] ⊕ [TF-IDF char_wb 2–5 grams] → LinearSVC(C=0.5, class_weight=balanced) → CalibratedClassifierCV(sigmoid, group-aware folds)`

1. **Leakage-safe split.** Rows are grouped by `template_id`; near-duplicates (token Jaccard ≥ 0.6) are merged into the same group (merging capped at 30 rows per group). `StratifiedGroupKFold` gives Train 728 / Val 152 / Test 161 with **no group shared between splits**. The previous random split let fills of the same template land in both train and test.
2. **Search on validation.** Features word / char_wb / word+char × LogisticRegression (C 1, 4, 16) and calibrated LinearSVC (C 0.1, 0.5, 2). Selection = 0.7·macro-F1 + 0.3·EMERGENCY recall, tie-break log-loss. The old DecisionTree is kept as a non-selectable reference (val macro-F1 0.67).
3. **Clarification threshold** tuned end-to-end (through `IntentPredictor.predict`, including the guardrail) on grouped 5-fold out-of-fold predictions over train+val, minimising a cost of 1.0 per wrong executed action, 0.25 per clarification, 5.0 per missed emergency. Chosen threshold: **0.475**, stored in `model_metadata.json` and loaded by `predict.py`.

### Results (synthetic data only)

| Evaluation | Accuracy | Macro-F1 | Notes |
| :--- | :---: | :---: | :--- |
| Old DecisionTree, old random split (previous README) | 0.936 | 0.936 | Inflated by template leakage |
| DecisionTree baseline, new group split, same test set | 0.882 | 0.872 | ECE 0.088, mean confidence 0.96 |
| **New model, grouped 5-fold OOF over train+val (880 rows)** | **0.971** | **0.971** | Most reliable estimate available; log-loss 0.21 |
| New model, end-to-end OOF (guardrail + threshold) | 0.975 | – | 3 of 22 errors routed to `CLARIFY`; coverage 99.3% |
| New model, held-out group-split test set (161 rows) | 1.000 | 1.000 | ECE 0.055; end-to-end also 1.000 |

How to read this:
- The perfect test score comes from a small, homogeneous synthetic test fold. It is **not** a production accuracy estimate; the OOF number (~0.97) is the better one, and both are on synthetic text.
- EMERGENCY recall is mostly carried by the rule guardrail (it fires on 99% of synthetic EMERGENCY rows and on 0% of the other classes).
- Only 3 of the 22 OOF errors fall below the threshold, so many errors are still confident. Real transcripts are needed both to measure accuracy and to re-tune the threshold.

Full numbers: `reports/metrics.json` (`model_only`, `end_to_end`, `baseline_decision_tree`), `reports/classification_report.txt`, `models/model_metadata.json`.

---

## 5. Decision Logic & Emergency Guardrail (`src/models/predict.py`)

1. **Confidence threshold:** if the calibrated confidence is below the tuned threshold, `recommended_action="CLARIFY"`.
2. **Emergency guardrail.** Text is normalised (Azerbaijani casing + diacritic folding, so `ÜRƏYİM AĞRIYIR` and `ureyim agriyir` both match).
   - *Distress signals* escalate on their own: *"nəfəs ala bilmirəm"*, *"boğuluram"*, *"ürəyim ağrıyır / sıxılır / dayanır"*, *"yıxıldım"*, *"dura bilmirəm"*, *"qanaxma"*, *"qaz iyi"*, *"yanğın var"*, *"insult"*, *"kömək edin"*.
   - *Emergency numbers / services* (103, 112, *təcili yardım*, *skorıy*, *polis*) escalate only together with a call/help verb (*çağır*, *zəng et*, *yığ*, *gəlsin*, *göndər*). So *"Təcili yardım çağır"* and *"103-ə zəng et"* are EMERGENCY, while *"112 nömrəsi neçədir?"* and *"Təcili yardımın nömrəsi neçədir?"* stay INFORMATION.
   - On escalation: `intent=EMERGENCY`, `safety_escalation=true`, `recommended_action="EMERGENCY_DISPATCH"`, never clarification.
3. **Order completeness:** if any item lacks a quantity or a unit → `requires_clarification=true`, `recommended_action="CLARIFY_ORDER_DETAILS"`.

---

## 6. Order Entity Extraction (`src/entities/extract_entities.py`)

- **Numbers:** digits (*"2"*, *"2.5"*, *"2,5"*, *"500qr"*) and Azerbaijani words, including multi-word: *"yarım"* → 0.5, *"beş yüz"* → 500, *"iki yüz əlli"* → 250, *"min iki yüz"* → 1200.
- **Units:** *kilo/kq* → kg, *qram/qr* → qram, *litr/litrlik* → litr, *ədəd/dənə* → ədəd, *paket*, *qutu*, *şüşə*, *banka*, *pors* …
- **No silent default unit:** when no unit is said (*"iki çörək"*), `unit` is `null` and the order asks for clarification.
- **Products:** matched on token boundaries, longest first (*"kökə"* is not read as *"kök"*; *"zeytun yağı"* wins over shorter matches); accusative/possessive suffixes are accepted (*"dərmanımı"*).
- **Multi-item:** split on *"və"*, *"bir də"* and commas.

```json
// "Mənə 2 kilo alma və 1 kilo pomidor sifariş et."
{"items": [{"product": "alma", "quantity": 2.0, "unit": "kg"},
           {"product": "pomidor", "quantity": 1.0, "unit": "kg"}],
 "is_complete": true, "missing_fields": []}
```

---

## 7. FastAPI Service (`src/api/main.py`)

- `POST /predict` `{"text": "..."}` → `{intent, confidence, requires_clarification, entities, recommended_action, safety_escalation}`. Returns **503** if the model file is missing (an utterance that triggers the emergency guardrail is still answered with EMERGENCY).
- `GET /health` → `model_loaded`, `status` (`healthy` / `degraded`), active clarification threshold.
- `GET /model-info` → `reports/metrics.json`.
- `POST /orders/mock-checkout` → simulated Wolt/Bazarstore order (no real payment).
- **CORS:** allowed origins from env `ALLOWED_ORIGINS` (comma-separated, default `*`); `allow_credentials=False`.

```bash
curl -X POST "http://localhost:8001/predict" -H "Content-Type: application/json" \
     -d '{"text": "Mənə 2 kilo alma sifariş et"}'
```

---

## 8. How to Run (from `hug-ml/`)

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # Linux/macOS: .venv/bin/pip
.venv/Scripts/python src/data/generate_dataset.py # optional: regenerate synthetic data
.venv/Scripts/python src/data/validate_dataset.py
.venv/Scripts/python src/models/train.py          # split, search, threshold, save model
.venv/Scripts/python src/models/evaluate.py       # reports/
.venv/Scripts/python -m pytest tests -q
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8001
```

Swagger UI: `http://localhost:8001/docs`. The backend reaches this service through `HUG_ML_URL=http://localhost:8001`.

---

## 9. Status

- [x] 0 duplicates, 0 missing values; 161–177 examples per class.
- [x] Leakage-safe, template-group split.
- [x] Calibrated probabilities (test ECE 0.055 vs 0.088 for the old decision tree).
- [x] End-to-end evaluation of `IntentPredictor.predict()` next to model-only metrics.
- [x] 38/38 pytest tests passing.
- [ ] **Real-world validation not done:** all data is synthetic; labelled real elderly ASR transcripts are required.
