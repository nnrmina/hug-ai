"""
Azerbaijani Text Preprocessing Module for HUG AI.

Preserves Azerbaijani-specific phonemes and alphabetic characters:
'ə', 'ı', 'ö', 'ü', 'ş', 'ç', 'ğ' (and their uppercase counterparts).
Handles Azerbaijani-specific casing quirks (e.g. 'I' -> 'ı', 'İ' -> 'i').
"""

import re
import unicodedata
from typing import List, Optional

# Azerbaijani alphabet characters (both lowercase and uppercase)
AZ_ALPHABET_CHARS = set("abcçdeəfgğhxıijkqlmnoöprsştuüvyzABCÇDEƏFGĞHXIİJKQLMNOÖPRSŞTUÜVYZ")

# Stopwords tailored for conversational voice commands in Azerbaijani
# We keep intent-bearing terms (like 'zəng', 'sifariş', 'kömək') and remove pure fillers.
AZ_CONVERSATIONAL_STOPWORDS = {
    "və", "ilə", "üçün", "da", "də", "ki", "həm", "ya", "yaxud",
    "bəli", "xeyr", "hə", "yox", "bir", "bu", "o", "mən", "sən",
    "biz", "siz", "onlar", "bura", "ora", "artıq", "axı", "daha",
    "bəlkə", "yəni", "çünki", "görə", "kimi", "hər", "öz"
}


def az_lower(text: str) -> str:
    """
    Azerbaijani-aware lowercase conversion.
    Standard Python .lower() converts capital dotted 'İ' to 'i',
    but converts capital undotted 'I' to 'i' instead of 'ı'.
    """
    if not text:
        return ""
    # Explicit mapping for Azerbaijani uppercase I and İ
    mapping = {
        "I": "ı",
        "İ": "i",
    }
    chars = [mapping.get(c, c.lower()) for c in text]
    return "".join(chars)


def normalize_az_text(text: str, preserve_numbers: bool = True) -> str:
    """
    Normalizes conversational Azerbaijani text for NLP:
    1. Unicode normalization (NFKC).
    2. Azerbaijani casing normalization.
    3. Retains all Azerbaijani letters: a-z, ə, ı, ö, ü, ş, ç, ğ.
    4. Cleans extraneous punctuation and duplicate whitespace.
    """
    if not text or not isinstance(text, str):
        return ""

    # Normalize unicode forms
    cleaned = unicodedata.normalize("NFKC", text.strip())

    # Lowercase with Azerbaijani rules
    cleaned = az_lower(cleaned)

    # Standardize common spelling/punctuation variants (e.g. apostrophes, dashes)
    cleaned = re.sub(r"[\'`‘’´]", "", cleaned)
    cleaned = re.sub(r"[-–—]", " ", cleaned)

    # Pattern: keep a-z, Azerbaijani letters, numbers (if enabled), and whitespace
    if preserve_numbers:
        pattern = r"[^a-zçəğıöşü0-9\s]"
    else:
        pattern = r"[^a-zçəğıöşü\s]"

    cleaned = re.sub(pattern, " ", cleaned)

    # Collapse multiple spaces into single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def tokenize_az_text(text: str, remove_stopwords: bool = False) -> List[str]:
    """
    Splits normalized text into tokens, optionally filtering conversational stopwords.
    """
    normalized = normalize_az_text(text)
    tokens = normalized.split()
    if remove_stopwords:
        tokens = [t for t in tokens if t not in AZ_CONVERSATIONAL_STOPWORDS]
    return tokens


class AzerbaijaniTextPreprocessor:
    """
    Scikit-learn compatible preprocessor / transformer callable.
    Can be plugged directly into TfidfVectorizer(preprocessor=...).
    """

    def __init__(self, remove_stopwords: bool = False, preserve_numbers: bool = True):
        self.remove_stopwords = remove_stopwords
        self.preserve_numbers = preserve_numbers

    def __call__(self, text: str) -> str:
        tokens = tokenize_az_text(
            text,
            remove_stopwords=self.remove_stopwords,
        )
        return " ".join(tokens)

