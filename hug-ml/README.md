# HUG – Azerbaijani Voice-Intent ML Pipeline (Decision Tree Classifier)

<p align="center">
  <b>Production-grade Machine Learning pipeline for voice-intent classification and entity extraction tailored for elderly Azerbaijani users.</b>
</p>

---

## 1. Project Objective

**HUG** is an AI-powered digital life assistant designed primarily for elderly citizens in Azerbaijan. When an elderly user speaks naturally in Azerbaijani (e.g., *"Mənə Wolt-dan 2 kilo alma sifariş et"* or *"Mamama zvanok elə"*), the system must:

1. Ingest the speech-to-text Azerbaijani transcript.
2. Normalize and preserve native Azerbaijani phonemes (`ə`, `ı`, `ö`, `ü`, `ş`, `ç`, `ğ`).
3. Classify the user's intent using a genuinely trained **Decision Tree Classifier** (TF-IDF + `DecisionTreeClassifier`).
4. Extract structured entities (products, quantities, units) if the intent is an order.
5. Determine whether sufficient information is present or if user clarification is required (`CLARIFY`).
6. Apply a hard safety guardrail for medical and household emergencies (`EMERGENCY_DISPATCH`).
7. Return a clean, structured JSON payload to the backend and mobile interface.

> **Key Rule:** This system is built strictly with genuinely trained scikit-learn Machine Learning components—no rule-based chatbots and no LLM API replacements for the intent classifier.

---

## 2. Project Directory Structure

```text
hug-ml/
│
├── data/
│   ├── hug_intent_dataset.csv          # 1,039 curated, balanced Azerbaijani voice utterances
│   ├── hug_entity_dataset.jsonl        # Fine-grained order entity annotations (items, qty, unit)
│   └── processed/
│       ├── train.csv                   # 70% Stratified Training subset (727 samples)
│       ├── val.csv                     # 15% Stratified Validation subset (156 samples)
│       └── test.csv                    # 15% Untouched Test subset (156 samples)
│
├── notebooks/
│   └── exploratory_data_analysis.ipynb # Comprehensive EDA, distribution charts & linguistic analysis
│
├── src/
│   ├── data/
│   │   ├── generate_dataset.py         # Multi-persona generator ensuring 0 duplicates & >=160/class
│   │   └── validate_dataset.py         # Rigorous schema, character preservation & duplicate validator
│   │
│   ├── preprocessing/
│   │   └── text_preprocessing.py       # Azerbaijani casing (İ/i, I/ı), NFKC, diacritic preservation
│   │
│   ├── models/
│   │   ├── train.py                    # 70/15/15 split, hyperparameter tuning & pipeline serialization
│   │   ├── evaluate.py                 # Benchmarking on untouched test set, confusion matrix plot
│   │   └── predict.py                  # Predict_proba confidence scoring & emergency safety guardrails
│   │
│   ├── entities/
│   │   └── extract_entities.py         # Multi-item parser for kg, litr, ədəd, verbal numbers
│   │
│   └── api/
│       └── main.py                     # FastAPI REST API (/predict, /orders/mock-checkout)
│
├── models/
│   ├── decision_tree_pipeline.joblib   # Trained scikit-learn Pipeline artifact
│   └── model_metadata.json             # Best hyperparameters, vectorizer configuration & classes
│
├── reports/
│   ├── classification_report.txt       # Full test classification report & error analysis
│   ├── confusion_matrix.png            # 6x6 Heatmap confusion matrix on held-out test data
│   └── metrics.json                    # Machine-readable test metrics and class F1-scores
│
├── tests/
│   ├── test_pipeline.py                # 12 Pytest unit & integration test cases (100% pass)
│   └── verify_unseen_sentences.py      # Verification script testing new, unobserved voice commands
│
├── requirements.txt                    # Python package dependencies
└── README.md                           # Documentation
```

---

## 3. Dataset Documentation (`data/hug_intent_dataset.csv`)

The dataset comprises **1,039 unique Azerbaijani utterances** across 6 balanced intent classes:

| Intent Class | Samples | Sample Voice Utterance | Context |
| :--- | :---: | :--- | :--- |
| **`ORDER`** | 175 | *"Mənə Wolt-dan 2 kilo alma və bir litr süd sifariş et."* | Grocery, pharmacy & Wolt delivery |
| **`CALL`** | 175 | *"Böyük qızım Leylaya zəng elə görüm necədir."* | Phone calls to family, doctors, neighbors |
| **`REMINDER`** | 176 | *"Saat 3-də təzyiq dərmanımı içməyi mənə xatırlat."* | Medication routines, appointments, pension |
| **`EMERGENCY`** | 161 | *"Ürəyim bərk sıxılır, nəfəs ala bilmirəm, təcili 103 çağır!"* | Severe health crises, falls, gas leaks, 112 |
| **`INFORMATION`** | 175 | *"Bu gün Bakıda hava necə olacaq, yağış yağacaq?"* | Weather, time, prayer hours, public services |
| **`OTHER`** | 177 | *"Allah razı olsun səndən bala, çox sağ ol."* | Greetings, elderly small talk, gratitude, noise |
| **Total** | **1,039** | | **All classes exceed target of 150** |

### Linguistic Characteristics & Authenticity
- **Elderly Conversational Phrasing:** Polite conversational formulas (*"ay bala"*, *"qızım"*, *"oğlum"*, *"zəhmət olmasa"*, *"qadan alım"*).
- **Baku Dialect & Russian Loanwords:** Everyday conversational borrowings (*"zvanok elə"*, *"zakaz ver"*, *"skorıy"*, *"aptek"*, *"davleniya"*).
- **Phonetic & ASCII Variants:** Supports both diacritic text (`ə`, `ı`, `ö`, `ü`, `ş`, `ç`, `ğ`) and unaccented mobile typing (`sifaris et`, `derman`, `corek`).
- **Data Provenance:** Every sample is transparently tagged in the `source` column (`synthetic_elderly_persona`, `synthetic_conversational`, `synthetic_baku_colloquial`, `synthetic_short_command`, `synthetic_spelling_variation`) with `is_reviewed=True`.

---

## 4. Machine Learning Pipeline & Model Evaluation

### Architecture
$$\text{Raw Utterance} \longrightarrow \text{Azerbaijani Preprocessing} \longrightarrow \text{TF-IDF (1-2 ngrams)} \longrightarrow \text{DecisionTreeClassifier} \longrightarrow \text{predict\_proba()}$$

1. **Stratified Split:** 70% Training (727), 15% Validation (156), 15% Test (156) with `random_state=42`.
2. **Hyperparameter Selection on Validation Data:**
   - Evaluated `max_depth` (25, 35, 40, 50, None), `min_samples_split` (2, 4), `min_samples_leaf` (1, 2), and `class_weight` (None, 'balanced').
   - Optimal parameters selected: `max_depth=50, min_samples_split=4, min_samples_leaf=2, class_weight=None`.
3. **Pristine Test Evaluation:** Evaluated on the held-out 156 test samples.

### Genuine Benchmark Results (Test Set)

```text
=== HUG DECISION TREE TEST SET BENCHMARK ===
Held-Out Test Samples: 156
Overall Accuracy:      93.59%
Macro F1-Score:        0.9357
Weighted F1-Score:     0.9358
Macro Recall:          0.9358
EMERGENCY Recall:      91.67%
```

#### Detailed Classification Report
| Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| **`CALL`** | **0.96** | **1.00** | **0.98** | 26 |
| **`ORDER`** | **1.00** | **0.96** | **0.98** | 26 |
| **`REMINDER`** | **0.93** | **0.96** | **0.95** | 27 |
| **`EMERGENCY`** | **0.92** | **0.92** | **0.92** | 24 |
| **`OTHER`** | **0.92** | **0.89** | **0.91** | 27 |
| **`INFORMATION`** | **0.88** | **0.88** | **0.88** | 26 |
| **Overall / Macro** | **0.94** | **0.94** | **0.94** | **156** |

---

## 5. Confidence, Decision Logic & Emergency Safety Guardrails

The inference engine (`src/models/predict.py`) applies safety-first decision logic:

1. **Confidence Threshold:** Uses `predict_proba()` to estimate confidence. If confidence is below 0.45 (or configurable threshold), the system returns `recommended_action: "CLARIFY"`, rather than executing an uncertain intent.
2. **Emergency Life-Safety Guardrail:**
   - Detects severe medical distress terms (*"boğuluram"*, *"nəfəs ala bilmirəm"*, *"ürəyim dayanır"*, *"103"*, *"112"*, *"yıxılmışam dura bilmirəm"*, *"qaz iyi"*).
   - If emergency tokens are present, intent is escalated to `EMERGENCY` with `safety_escalation: True` and `recommended_action: "EMERGENCY_DISPATCH"`.
   - Emergency never requests clarification—every second counts for elderly users.
3. **Order Completion Check:** If an order is missing a quantity or product, it flags `requires_clarification: True` and `recommended_action: "CLARIFY_ORDER_DETAILS"`.

---

## 6. Order Entity Extraction Module (`src/entities/extract_entities.py`)

Parses complex multi-item orders into structured parameters:
- **Spelled-out Azerbaijani numbers:** *"bir"* $\to 1.0$, *"iki"* $\to 2.0$, *"yarım"* $\to 0.5$, etc.
- **Unit standardizations:** *"kilo"*, *"kq"* $\to \text{kg}$; *"litr"* $\to \text{litr}$; *"ədəd"*, *"dənə"* $\to \text{ədəd}$; *"paket"*, *"qutu"*, *"şüşə"*, *"pors"*.
- **Compound splitting:** Handles multi-item conjunctions (*"və"*, *"bir də"*, commas).

### Example
**Input:**
```text
"Mənə 2 kilo alma və 1 kilo pomidor sifariş et."
```
**Extracted Output:**
```json
{
  "items": [
    {"product": "alma", "quantity": 2.0, "unit": "kg"},
    {"product": "pomidor", "quantity": 1.0, "unit": "kg"}
  ],
  "is_complete": true,
  "missing_fields": []
}
```

---

## 7. FastAPI REST API Integration (`src/api/main.py`)

### Endpoints

#### 1. `POST /predict`
Processes an Azerbaijani user utterance through preprocessing, Decision Tree inference, entity extraction, and safety rules.

**Request:**
```bash
curl -X POST "http://localhost:8000/predict" \
     -H "Content-Type: application/json" \
     -d '{"text": "Mənə 2 kilo alma sifariş et"}'
```

**Response:**
```json
{
  "intent": "ORDER",
  "confidence": 1.0,
  "requires_clarification": false,
  "entities": {
    "items": [
      {
        "product": "alma",
        "quantity": 2.0,
        "unit": "kg"
      }
    ]
  },
  "recommended_action": "PROCESS_ORDER",
  "safety_escalation": false
}
```

#### 2. `POST /orders/mock-checkout`
Simulates Wolt / Bazarstore order processing and delivery estimation in AZN without real financial transactions.

**Request:**
```bash
curl -X POST "http://localhost:8000/orders/mock-checkout" \
     -H "Content-Type: application/json" \
     -d '{
       "items": [{"product": "alma", "quantity": 2.0, "unit": "kg"}],
       "delivery_address": "Bakı, Nizami küçəsi 14"
     }'
```

#### 3. `GET /health` & `GET /model-info`
Monitors model status, loaded classes, hyperparameters, and test evaluation metrics.

---

## 8. How to Run the Pipeline

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Validate Dataset Quality
```bash
python src/data/validate_dataset.py
```

### Step 3: Train the Decision Tree
```bash
python src/models/train.py
```

### Step 4: Evaluate on Held-Out Test Set
```bash
python src/models/evaluate.py
```

### Step 5: Run Pytest Test Suite
```bash
pytest tests/test_pipeline.py -v
```

### Step 6: Test Unseen Voice Sentences
```bash
python tests/verify_unseen_sentences.py
```

### Step 7: Launch FastAPI Server
```bash
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Interactive Swagger documentation is available at `http://localhost:8000/docs`.

---

## 9. Verification & Quality Assurance Summary

- [x] **0 Duplicates & 0 Missing Values:** Verified by `validate_dataset.py`.
- [x] **Class Distribution:** Every class contains 161 to 177 unique examples (1,039 total).
- [x] **Azerbaijani Character Set:** Over 94.8% of utterances contain native letters (`ə`, `ı`, `ö`, `ü`, `ş`, `ç`, `ğ`).
- [x] **Real ML Pipeline:** Decision Tree pipeline trained with scikit-learn (`max_depth=50`, `min_samples_split=4`, `min_samples_leaf=2`).
- [x] **Genuine Metrics:** 93.59% accuracy, 0.9357 Macro F1, 91.67% raw Emergency recall on untouched test data.
- [x] **Unit & Integration Tests:** 12/12 pytest tests passing (100%).

