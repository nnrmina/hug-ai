"""
Entity Extraction Module for HUG AI Voice Assistant.

Extracts structured items from Azerbaijani order queries:
- Products / groceries / medicines / dishes
- Quantities (digits or Azerbaijani number words: "bir", "iki", "yarım", etc.)
- Measurement units (kg, litr, ədəd, paket, qutu, banka, pors)

Identifies incomplete orders that require user clarification.
"""

import re
from typing import Dict, List, Optional, Tuple, Any

# Number words mapping in Azerbaijani
AZ_NUMBER_WORDS = {
    "yarım": 0.5,
    "bir": 1.0,
    "iki": 2.0,
    "üç": 3.0,
    "dörd": 4.0,
    "beş": 5.0,
    "altı": 6.0,
    "yeddi": 7.0,
    "səkkiz": 8.0,
    "doqquz": 9.0,
    "on": 10.0,
    "iyirmi": 20.0,
    "otuz": 30.0,
    "əlli": 50.0,
    "yüz": 100.0,
    "beş yüz": 500.0,
    "min": 1000.0,
}

# Unit normalizations
UNIT_NORMALIZATION = {
    "kilo": "kg",
    "kq": "kg",
    "kilogram": "kg",
    "kg": "kg",
    "qram": "qram",
    "qr": "qram",
    "gr": "qram",
    "g": "qram",
    "litr": "litr",
    "litrlik": "litr",
    "l": "litr",
    "ədəd": "ədəd",
    "eded": "ədəd",
    "dənə": "ədəd",
    "dene": "ədəd",
    "tənə": "ədəd",
    "paket": "paket",
    "paçka": "paket",
    "packa": "paket",
    "qutu": "qutu",
    "banka": "banka",
    "şüşə": "şüşə",
    "suse": "şüşə",
    "pors": "pors",
    "porsiya": "pors",
    "baş": "baş",
    "plitka": "plitka",
    "boşqab": "boşqab",
    "dilim": "dilim",
}

# Common grocery, medicine, and food vocabulary in Azerbaijani
KNOWN_PRODUCTS = [
    # Fruits & Vegetables
    "alma", "armud", "portağal", "naringi", "banan", "limon", "üzüm",
    "çiyələk", "qarpız", "yemiş", "şaftalı", "kartof", "soğan", "pomidor",
    "xiyar", "kök", "kələm", "badımcan", "bibər", "sarımsaq", "göyərti",
    "zəncəfil", "kərəviz",
    # Dairy & Groceries
    "çörək", "qara çörək", "təndir çörəyi", "lavaş", "süd", "qatıq", "pendir",
    "kərə yağı", "zeytun yağı", "günəbaxan yağı", "yumurta", "kənd yumurtası",
    "xama", "kəsmik", "lor", "şor", "qənd", "şəkər tozu", "çay", "qara çay",
    "yaşıl çay", "un", "düyü", "qarabaşaq", "makaron", "duz", "noxud",
    "su", "içməli su", "mineral su", "kompot",
    # Meat & Prepared Food
    "mal əti", "toyuq əti", "toyuq filesi", "toyuq dönəri", "ət dönəri",
    "dönər", "lülə kabab", "tikə kabab", "kabab", "mərci şorbası", "toyuq şorbası",
    "düşbərə", "aş", "plov", "pizza", "lahmacun", "qutab", "ət qutabı",
    "göy qutabı", "yarpaq dolması", "dolma", "paytaxt salatı", "salat",
    "ayran", "dovğa",
    # Pharmacy & Medical
    "kardiomaqnil", "analqin", "parasetamol", "aspirin kardio", "aspirin",
    "validol", "noşpa", "vitamin c", "vitamin", "göz damcısı", "öskürək siropu",
    "boğaz spreyi", "steril bint", "bint", "spirt", "təzyiq dərmanı", "dərman"
]

ORDER_STOPWORDS = {
    "mənə", "mene", "bizə", "bize", "evə", "eve", "üçün", "ucun",
    "zəhmət", "olmasa", "zehmet", "xahiş", "edirəm", "edirem",
    "wolt", "dan", "dən", "bazarstore", "bravo", "marketdən", "marketden",
    "aptekdən", "aptekden", "restorandan", "kafedən", "kafedan",
    "sifariş", "sifaris", "et", "elə", "ele", "ver", "gətirsinlər",
    "getirsinler", "gətizdir", "al", "alarsan", "göndərsinlər", "gondersinler",
    "istəyirəm", "isteyirem", "lazımdır", "lazimdir", "təcili", "tecili",
    "və", "ve", "bir", "də", "de", "ilə", "ile", "zakaz", "dostavka",
    "qadan", "alım", "alim", "ay", "bala", "balam", "əzizim", "ezizim",
    "oğlum", "oglum", "qızım", "qizim", "canım", "canim"
}


def parse_quantity_and_unit(text_span: str) -> Tuple[Optional[float], Optional[str], str]:
    """
    Extracts numerical or verbal quantity, standardized unit, and remaining product text.
    """
    span = text_span.strip()

    # Regex matching: digits (e.g. 2, 2.5, 500) or verbal words ("iki", "bir", "yarım")
    # followed by optional unit word
    number_pattern = r"^(\d+(?:[.,]\d+)?)\s*([a-zçəğıöşüA-ZÇƏĞIİÖŞÜ]+)?\s*(.*)$"
    m = re.match(number_pattern, span, re.IGNORECASE)

    if m:
        qty_str, unit_candidate, rest = m.groups()
        qty = float(qty_str.replace(",", "."))
        norm_unit = UNIT_NORMALIZATION.get((unit_candidate or "").lower())
        if norm_unit:
            return qty, norm_unit, rest.strip()
        else:
            # Maybe unit_candidate was part of product name, default to 'ədəd' or inspect
            full_rest = f"{unit_candidate or ''} {rest}".strip()
            return qty, "ədəd", full_rest

    # Check for verbal numbers
    tokens = span.split()
    if tokens:
        first = tokens[0].lower()
        if first in AZ_NUMBER_WORDS:
            qty = AZ_NUMBER_WORDS[first]
            if len(tokens) > 1 and tokens[1].lower() in UNIT_NORMALIZATION:
                unit = UNIT_NORMALIZATION[tokens[1].lower()]
                rest = " ".join(tokens[2:])
                return qty, unit, rest.strip()
            else:
                rest = " ".join(tokens[1:])
                return qty, "ədəd", rest.strip()

    # No explicit quantity found
    return None, None, span


def extract_order_entities(text: str) -> Dict[str, Any]:
    """
    Extracts all ordered products, quantities, and units from a natural language text.
    Returns:
    {
        "items": [
            {"product": "alma", "quantity": 2.0, "unit": "kg"},
            ...
        ],
        "is_complete": bool,
        "missing_fields": List[str]
    }
    """
    if not text:
        return {"items": [], "is_complete": False, "missing_fields": ["empty_input"]}

    cleaned = text.lower()
    # Normalize punctuation and split multi-item requests by "və", "bir də", comma
    delimiters = r"\bvə\b|\bve\b|\bbir də\b|\bbir de\b|,"
    segments = [s.strip() for s in re.split(delimiters, cleaned) if s.strip()]

    items = []
    missing_fields = []

    for seg in segments:
        # Remove common introductory words (wolt-dan, mənə, zəhmət olmasa, sifariş et)
        seg_tokens = seg.split()
        cleaned_tokens = [
            t for t in seg_tokens
            if t not in {"wolt", "woltdan", "wolt-dan", "bazarstore", "bazarstore-dan",
                         "bravo", "aptekdən", "aptekden", "mənə", "mene", "bizə",
                         "sifariş", "sifaris", "et", "elə", "ele", "ver", "zakaz",
                         "al", "gətirsinlər", "istəyirəm", "isteyirem", "lazımdır"}
        ]
        seg_text = " ".join(cleaned_tokens).strip()
        if not seg_text:
            continue

        # Check for known products directly
        found_product = None
        for kp in sorted(KNOWN_PRODUCTS, key=len, reverse=True):
            if kp in seg_text:
                found_product = kp
                break

        qty, unit, rest = parse_quantity_and_unit(seg_text)

        if not found_product and rest:
            clean_rest_tokens = [w for w in rest.split() if w not in ORDER_STOPWORDS and len(w) > 2]
            if clean_rest_tokens:
                found_product = " ".join(clean_rest_tokens)

        # Ignore segments that do not contain a product
        if found_product and found_product not in ORDER_STOPWORDS:
            item_entry = {
                "product": found_product,
                "quantity": qty,
                "unit": unit
            }
            items.append(item_entry)
            if qty is None:
                missing_fields.append(f"quantity_for_{found_product}")
            if unit is None:
                missing_fields.append(f"unit_for_{found_product}")

    is_complete = len(items) > 0 and len(missing_fields) == 0

    return {
        "items": items,
        "is_complete": is_complete,
        "missing_fields": missing_fields
    }
