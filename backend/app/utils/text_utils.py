def az_lower(text: str) -> str:
    """Azerbaijani-aware lowercase.

    Python's str.lower() maps "I" -> "i" and "İ" -> "i̇" (i + combining dot), which breaks
    keyword matching for Azerbaijani ("QIZIMA" must become "qızıma", "İKİ" -> "iki").
    """
    return text.replace("I", "ı").replace("İ", "i").lower()
