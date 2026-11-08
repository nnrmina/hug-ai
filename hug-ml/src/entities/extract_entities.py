"""
Entity Extraction Module for HUG AI Voice Assistant.

Extracts structured items from Azerbaijani order queries:
- Products / groceries / medicines / dishes
- Quantities (digits or Azerbaijani number words, including multi-word numbers:
  "bir", "iki", "yarım", "beş yüz", "iki yüz əlli", "min iki yüz")
- Measurement units (kg, qram, litr, ədəd, paket, qutu, banka, pors)

Identifies incomplete orders that require user clarification. When the user does
not state a unit, the unit is left as None (it is never silently defaulted).
"""

import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.preprocessing.text_preprocessing import az_lower  # noqa: E402

# Number words in Azerbaijani, split by role so multi-word numbers can be composed
# ("beş yüz" -> 500, "iki yüz əlli" -> 250, "min iki yüz" -> 1200).
AZ_DIGIT_WORDS = {
    "sıfır": 0.0, "bir": 1.0, "iki": 2.0, "üç": 3.0, "dörd": 4.0, "beş": 5.0,
    "altı": 6.0, "yeddi": 7.0, "səkkiz": 8.0, "doqquz": 9.0,
}
AZ_TENS_WORDS = {
    "on": 10.0, "iyirmi": 20.0, "otuz": 30.0, "qırx": 40.0, "əlli": 50.0,
    "altmış": 60.0, "yetmiş": 70.0, "səksən": 80.0, "doxsan": 90.0,
}
AZ_HUNDRED_WORD = "yüz"
AZ_THOUSAND_WORD = "min"
AZ_HALF_WORD = "yarım"

# Flat lookup of single-word values (kept for backwards compatibility).
AZ_NUMBER_WORDS = {
    AZ_HALF_WORD: 0.5,
    **AZ_DIGIT_WORDS,
    **AZ_TENS_WORDS,
    AZ_HUNDRED_WORD: 100.0,
    AZ_THOUSAND_WORD: 1000.0,
}

# Unit normalizations
UNIT_NORMALIZATION = {
    "kilo": "kg",
    "kq": "kg",
    "kilogram": "kg",
    "kiloluq": "kg",
    "kg": "kg",
    "qram": "qram",
    "qramlıq": "qram",
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
    # Bakery / sweets (explicit so that e.g. "kökə" is never read as "kök")
    "kökə", "piroq", "paxlava", "şəkərbura", "halva", "burger",
    # Pharmacy & Medical
    "kardiomaqnil", "analqin", "parasetamol", "aspirin kardio", "aspirin",
    "validol", "noşpa", "vitamin c", "vitamin", "göz damcısı", "öskürək siropu",
    "boğaz spreyi", "steril bint", "bint", "spirt", "təzyiq dərmanı", "dərman",
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
    "oğlum", "oglum", "qızım", "qizim", "canım", "canim",
}

# Lead-in words stripped from each order segment before parsing
INTRO_STOPWORDS = {
    "wolt", "woltdan", "dan", "dən", "bazarstore", "bravo", "aptekdən", "aptekden",
    "mənə", "mene", "bizə", "bize", "sifariş", "sifaris", "et", "elə", "ele", "ver",
    "zakaz", "al", "gətirsinlər", "getirsinler", "istəyirəm", "isteyirem",
    "lazımdır", "lazimdir", "zəhmət", "zehmet", "olmasa",
}

# Accusative / possessive / plural suffixes that may follow a product name inside a
# single token ("dərmanımı", "almanı", "almalar"). Dative "-a/-ə" is deliberately NOT
# accepted: "kökə" (a bun) must not be read as "kök" (carrot) + dative.
PRODUCT_SUFFIXES = (
    "ımı", "imi", "umu", "ümü", "ları", "ləri",
    "nı", "ni", "nu", "nü", "mı", "mi", "mu", "mü", "lar", "lər",
    "ı", "i", "u", "ü",
)

_KNOWN_PRODUCTS_BY_LENGTH = sorted(set(KNOWN_PRODUCTS), key=len, reverse=True)
_NUMERIC_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
_GLUED_QTY_UNIT_RE = re.compile(r"^(\d+(?:[.,]\d+)?)([a-zçəğıöşü]+)$")


def _normalize_order_text(text: str) -> str:
    """Azerbaijani-aware lowercase (İ->i, I->ı) + punctuation cleanup keeping decimals/commas."""
    cleaned = unicodedata.normalize("NFKC", text or "")
    cleaned = az_lower(cleaned)
    cleaned = re.sub(r"['`‘’´]", "", cleaned)
    cleaned = re.sub(r"[-–—]", " ", cleaned)
    # Drop periods unless they are decimal separators between digits
    cleaned = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", cleaned)
    cleaned = re.sub(r"[^\w\s.,]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _split_tokens(span: str) -> List[str]:
    """Tokenizes a normalized span, splitting glued quantity+unit tokens like '2kg', '500qr'."""
    tokens: List[str] = []
    for tok in re.sub(r",(?!\d)", " ", span).split():
        m = _GLUED_QTY_UNIT_RE.match(tok)
        if m and m.group(2) in UNIT_NORMALIZATION:
            tokens.extend([m.group(1), m.group(2)])
        else:
            tokens.append(tok)
    return tokens


def _parse_number_run(tokens: List[str], start: int) -> Tuple[Optional[float], int]:
    """
    Parses a (possibly multi-word) number starting at tokens[start].
    Returns (value, tokens_consumed), or (None, 0) if no number starts there.
    Supports digits ("500", "2.5", "2,5") and composed words
    ("beş yüz", "iki yüz əlli", "min iki yüz", "iki yarım", "yarım").
    """
    if start >= len(tokens):
        return None, 0

    tok = tokens[start]
    if _NUMERIC_RE.match(tok):
        value = float(tok.replace(",", "."))
        consumed = 1
        if start + 1 < len(tokens) and tokens[start + 1] == AZ_HALF_WORD:  # "2 yarım" -> 2.5
            value += 0.5
            consumed += 1
        return value, consumed

    total = 0.0
    current = 0.0
    consumed = 0
    last_kind = None
    i = start
    while i < len(tokens):
        w = tokens[i]
        if w in AZ_DIGIT_WORDS and last_kind != "digit":
            current += AZ_DIGIT_WORDS[w]
            last_kind = "digit"
        elif w in AZ_TENS_WORDS and last_kind not in ("digit", "tens"):
            current += AZ_TENS_WORDS[w]
            last_kind = "tens"
        elif w == AZ_HUNDRED_WORD and last_kind not in ("hundred", "tens"):
            current = (current or 1.0) * 100.0
            last_kind = "hundred"
        elif w == AZ_THOUSAND_WORD and total == 0.0 and last_kind != "thousand":
            total += (current or 1.0) * 1000.0
            current = 0.0
            last_kind = "thousand"
        elif w == AZ_HALF_WORD:
            current += 0.5
            consumed += 1
            break
        else:
            break
        consumed += 1
        i += 1

    if consumed == 0:
        return None, 0
    return total + current, consumed


def _match_known_product(tokens: List[str]) -> Optional[Tuple[str, int, int]]:
    """
    Longest-match-first product lookup on token boundaries (no raw substring matching).
    The last token of a product may carry an accusative/possessive/plural suffix.
    Returns (product, start_index, end_index_exclusive) or None.
    """
    for kp in _KNOWN_PRODUCTS_BY_LENGTH:
        kp_tokens = kp.split()
        n = len(kp_tokens)
        for i in range(len(tokens) - n + 1):
            window = tokens[i:i + n]
            if window[:-1] != kp_tokens[:-1]:
                continue
            last, target = window[-1], kp_tokens[-1]
            if last == target or (
                last.startswith(target) and last[len(target):] in PRODUCT_SUFFIXES
            ):
                return kp, i, i + n
    return None


def parse_quantity_and_unit(text_span: str) -> Tuple[Optional[float], Optional[str], str]:
    """
    Extracts numerical or verbal quantity, standardized unit, and remaining product text.
    The unit is None when the user did not state one (no silent default to "ədəd").
    """
    tokens = _split_tokens(_normalize_order_text(text_span))

    qty: Optional[float] = None
    unit: Optional[str] = None
    used = set()

    for i in range(len(tokens)):
        value, consumed = _parse_number_run(tokens, i)
        if value is not None:
            qty = value
            used.update(range(i, i + consumed))
            nxt = i + consumed
            if nxt < len(tokens) and tokens[nxt] in UNIT_NORMALIZATION:
                unit = UNIT_NORMALIZATION[tokens[nxt]]
                used.add(nxt)
            break

    if unit is None:
        # Unit stated without a number ("kilo alma"); quantity stays None.
        for i, tok in enumerate(tokens):
            if i not in used and len(tok) > 1 and tok in UNIT_NORMALIZATION:
                unit = UNIT_NORMALIZATION[tok]
                used.add(i)
                break

    rest = " ".join(t for i, t in enumerate(tokens) if i not in used)
    return qty, unit, rest.strip()


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

    cleaned = _normalize_order_text(text)
    # Split multi-item requests by "və", "bir də", comma (but not decimal commas)
    delimiters = r"\bvə\b|\bve\b|\bbir də\b|\bbir de\b|,(?!\d)"
    segments = [s.strip() for s in re.split(delimiters, cleaned) if s.strip()]

    items = []
    missing_fields = []

    for seg in segments:
        seg_tokens = [t for t in _split_tokens(seg) if t not in INTRO_STOPWORDS]
        if not seg_tokens:
            continue

        qty, unit, rest = parse_quantity_and_unit(" ".join(seg_tokens))

        found_product = None
        match = _match_known_product(rest.split())
        if match:
            found_product = match[0]
        elif rest:
            clean_rest_tokens = [
                w for w in rest.split()
                if w not in ORDER_STOPWORDS and w not in UNIT_NORMALIZATION
                and not _NUMERIC_RE.match(w) and len(w) > 2
            ]
            if clean_rest_tokens:
                found_product = " ".join(clean_rest_tokens)

        # Ignore segments that do not contain a product
        if found_product and found_product not in ORDER_STOPWORDS:
            items.append({
                "product": found_product,
                "quantity": qty,
                "unit": unit,
            })
            if qty is None:
                missing_fields.append(f"quantity_for_{found_product}")
            if unit is None:
                missing_fields.append(f"unit_for_{found_product}")

    is_complete = len(items) > 0 and len(missing_fields) == 0

    return {
        "items": items,
        "is_complete": is_complete,
        "missing_fields": missing_fields,
    }
