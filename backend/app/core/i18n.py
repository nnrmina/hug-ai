"""Tiny AZ/RU switch for spoken replies. Azerbaijani is the default; Russian is used when
the user spoke Russian (detected by Gemini, or Cyrillic text in rule mode)."""
import re
from typing import Optional

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
LANGS = ("az", "ru")


def norm_lang(lang: Optional[str]) -> str:
    return lang if lang in LANGS else "az"


def detect_lang(text: Optional[str]) -> str:
    return "ru" if text and len(_CYRILLIC.findall(text)) >= 2 else "az"


def pick(lang: Optional[str], az: str, ru: str) -> str:
    return ru if lang == "ru" else az
