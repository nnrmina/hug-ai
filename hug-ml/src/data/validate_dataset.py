"""
Dataset Validation and Quality Assurance for HUG Intent & Entity Datasets.

Validates:
1. Missing-value checks across all required fields.
2. Duplicate text detection (exact and normalized duplicates).
3. Class balance and distribution analysis (verifies >=150 per class).
4. Label schema integrity (ORDER, CALL, REMINDER, EMERGENCY, INFORMATION, OTHER).
5. Azerbaijani character set preservation (ensures ə, ı, ö, ü, ş, ç, ğ are intact).
6. Entity dataset structure and schema compliance.
"""

import csv
import json
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.preprocessing.text_preprocessing import az_lower  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
INTENT_CSV_PATH = DATA_DIR / "hug_intent_dataset.csv"
ENTITY_JSONL_PATH = DATA_DIR / "hug_entity_dataset.jsonl"

VALID_INTENTS = {"ORDER", "CALL", "REMINDER", "EMERGENCY", "INFORMATION", "OTHER"}
AZ_SPECIAL_CHARS = set("çəğıöşüÇƏĞIİÖŞÜ")


def validate_intent_dataset(csv_path: Path = INTENT_CSV_PATH) -> Dict:
    """
    Validates data/hug_intent_dataset.csv against quality rules.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Intent dataset not found at {csv_path}")

    total_rows = 0
    missing_values = 0
    invalid_labels = []
    class_counts: Dict[str, int] = {k: 0 for k in VALID_INTENTS}
    source_counts: Dict[str, int] = {}
    seen_texts: Set[str] = set()
    exact_duplicates = 0
    az_char_count = 0

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_cols = {"id", "text", "intent", "source", "is_reviewed"}
        if not required_cols.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV missing required columns: {required_cols - set(reader.fieldnames or [])}")

        for row_num, row in enumerate(reader, start=2):
            total_rows += 1
            text = (row.get("text") or "").strip()
            intent = (row.get("intent") or "").strip()
            source = (row.get("source") or "").strip()
            is_reviewed = (row.get("is_reviewed") or "").strip()

            # Missing value check
            if not text or not intent or not source or not is_reviewed:
                missing_values += 1

            # Label validation
            if intent not in VALID_INTENTS:
                invalid_labels.append((row_num, intent))
            else:
                class_counts[intent] += 1

            # Source count
            source_counts[source] = source_counts.get(source, 0) + 1

            # Exact duplicate check
            norm_key = az_lower(text)
            if norm_key in seen_texts:
                exact_duplicates += 1
            else:
                seen_texts.add(norm_key)

            # Azerbaijani characters preservation check
            if any(ch in AZ_SPECIAL_CHARS for ch in text):
                az_char_count += 1

    # Quality assessments
    underrepresented = {k: v for k, v in class_counts.items() if v < 150}
    is_valid = (
        missing_values == 0
        and len(invalid_labels) == 0
        and len(underrepresented) == 0
        and exact_duplicates == 0
    )

    report = {
        "is_valid": is_valid,
        "total_rows": total_rows,
        "missing_values": missing_values,
        "invalid_labels": invalid_labels,
        "exact_duplicates": exact_duplicates,
        "class_distribution": class_counts,
        "underrepresented_classes": underrepresented,
        "source_distribution": source_counts,
        "rows_with_az_characters": az_char_count,
        "az_character_coverage_pct": round(az_char_count / max(total_rows, 1) * 100, 2),
    }

    return report


def validate_entity_dataset(jsonl_path: Path = ENTITY_JSONL_PATH) -> Dict:
    """
    Validates data/hug_entity_dataset.jsonl against schema rules.
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Entity dataset not found at {jsonl_path}")

    total_records = 0
    invalid_records = []
    item_count = 0
    missing_unit_or_qty = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            total_records += 1
            try:
                data = json.loads(line)
                text = data.get("text", "")
                intent = data.get("intent", "")
                entities = data.get("entities", {})
                items = entities.get("items", [])

                if intent != "ORDER" or not isinstance(items, list):
                    invalid_records.append((idx, "Invalid intent or items schema"))
                    continue

                for it in items:
                    item_count += 1
                    if "product" not in it:
                        invalid_records.append((idx, "Missing product key"))
                    if it.get("quantity") is None or it.get("unit") is None:
                        missing_unit_or_qty += 1

            except Exception as e:
                invalid_records.append((idx, str(e)))

    report = {
        "is_valid": len(invalid_records) == 0 and total_records >= 50,
        "total_records": total_records,
        "total_items_annotated": item_count,
        "unspecified_qty_or_unit_records": missing_unit_or_qty,
        "invalid_records": invalid_records,
    }
    return report


if __name__ == "__main__":
    print("--- Validating Intent Dataset ---")
    intent_rep = validate_intent_dataset()
    for k, v in intent_rep.items():
        print(f"{k}: {v}")

    print("\n--- Validating Entity Dataset ---")
    entity_rep = validate_entity_dataset()
    for k, v in entity_rep.items():
        print(f"{k}: {v}")

