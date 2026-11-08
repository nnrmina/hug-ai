import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.utils.text_utils import az_lower

BAKU_TZ = timezone(timedelta(hours=4), name="Asia/Baku")

AZ_NUMBER_WORDS = {
    "bir": 1,
    "iki": 2,
    "üç": 3,
    "uc": 3,
    "dörd": 4,
    "dord": 4,
    "beş": 5,
    "bes": 5,
    "altı": 6,
    "alti": 6,
    "yeddi": 7,
    "səkkiz": 8,
    "sekkiz": 8,
    "doqquz": 9,
    "on": 10,
    "on bir": 11,
    "on iki": 12,
}

# Words that are ordinary Azerbaijani words when followed by -da/-də ("onda" = "then",
# "birdə" = "once more"), so they only count as an hour when preceded by "saat".
_AMBIGUOUS_HOUR_WORDS = {"bir", "on"}

AZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr",
]

_NUM = r"(\d{1,3}|yarım|yarim|" + "|".join(
    re.escape(w) for w in sorted(AZ_NUMBER_WORDS, key=len, reverse=True)
) + r")"
_REL_MIN_RE = re.compile(_NUM + r"\s*(?:dəqiqə|deqiqe)\w*\s*(?:sonra|ərzində|erzinde)?")
_REL_HOUR_RE = re.compile(_NUM + r"\s*saat(?:dan|dən)?\s*(?:sonra|ərzində|erzinde)")

_MORNING_WORDS = ("səhər", "seher", "sübh", "subh")
_NIGHT_WORDS = ("gecə", "gece")
_EVENING_WORDS = ("axşam", "axsam")
_NOON_WORDS = ("günorta", "gunorta", "nahar")


def _to_number(token: str) -> Optional[float]:
    if token.isdigit():
        return float(token)
    if token in ("yarım", "yarim"):
        return 0.5
    return float(AZ_NUMBER_WORDS[token]) if token in AZ_NUMBER_WORDS else None


def now_baku() -> datetime:
    """Return current datetime in Asia/Baku (+04:00) timezone."""
    return datetime.now(BAKU_TZ)


def _adjust_day_period(hour: int, lower: str) -> int:
    """Convert a 12-hour spoken hour into 24-hour time using day-period words.

    Without any period word, 1–6 is assumed to be afternoon (13–18): elderly users saying
    "saat 3-də dərman" almost never mean 03:00. The confirmation text shows the resolved
    time, so the user can correct it.
    """
    if any(w in lower for w in _EVENING_WORDS):
        return hour + 12 if 1 <= hour <= 11 else hour
    if any(w in lower for w in _NIGHT_WORDS):
        if 7 <= hour <= 11:
            return hour + 12
        return 0 if hour == 12 else hour
    if any(w in lower for w in _NOON_WORDS):
        return hour + 12 if 1 <= hour <= 6 else hour
    if any(w in lower for w in _MORNING_WORDS):
        return 0 if hour == 12 else hour
    if 1 <= hour <= 6:
        return hour + 12
    return hour


def parse_azerbaijani_datetime(
    text: str,
    reference_time: Optional[datetime] = None,
) -> Tuple[datetime, str]:
    """Extract scheduled datetime (Asia/Baku) and cleaned title from Azerbaijani command text."""
    base = (reference_time or now_baku()).astimezone(BAKU_TZ)
    lower = az_lower(text).strip()

    days_offset = 0
    if "birigün" in lower or "biri gün" in lower or "birisigün" in lower:
        days_offset = 2
    elif "sabah" in lower:
        days_offset = 1

    # 1. Relative times: "30 dəqiqədən sonra", "2 saatdan sonra", "yarım saat sonra"
    rel_min = _REL_MIN_RE.search(lower)
    rel_hour = _REL_HOUR_RE.search(lower)
    if rel_hour and _to_number(rel_hour.group(1)) is not None:
        scheduled = base + timedelta(hours=_to_number(rel_hour.group(1)))  # type: ignore[arg-type]
        return scheduled.replace(second=0, microsecond=0), extract_reminder_title(text)
    if rel_min:
        minutes = _to_number(rel_min.group(1))
        if minutes is not None and minutes >= 1:
            scheduled = base + timedelta(minutes=minutes)
            return scheduled.replace(second=0, microsecond=0), extract_reminder_title(text)

    # 2. Absolute times
    hour: Optional[int] = None
    minute = 0
    explicit_24h = False

    colon_match = re.search(r"\b(\d{1,2})[:.](\d{2})\b", lower)
    num_hour_match = re.search(r"(?:saat\s*)?\b(\d{1,2})\s*(?:-\s*(?:da|də|a|ə|ya|yə)\b|da\b|də\b)", lower)
    if colon_match and int(colon_match.group(1)) <= 23 and int(colon_match.group(2)) <= 59:
        hour = int(colon_match.group(1))
        minute = int(colon_match.group(2))
        explicit_24h = hour >= 13 or colon_match.group(1).startswith("0")
    elif num_hour_match and 0 <= int(num_hour_match.group(1)) <= 23:
        hour = int(num_hour_match.group(1))
        explicit_24h = hour >= 13
    else:
        for word, val in sorted(AZ_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
            w = re.escape(word)
            with_saat = rf"\bsaat\s+{w}(?:da|də|-da|-də|a|ə)?\b"
            suffix_only = rf"\b{w}(?:da|də|-da|-də)\b"
            if re.search(with_saat, lower) or (
                word not in _AMBIGUOUS_HOUR_WORDS and re.search(suffix_only, lower)
            ):
                hour = val
                break

    if "yarımda" in lower or "yarimda" in lower:
        # "saat 3 yarımda" = 3:30
        minute = 30

    if hour is None:
        # No time mentioned: tomorrow (or the named day) at 09:00.
        target_date = (base + timedelta(days=max(days_offset, 1))).date()
        scheduled = datetime(target_date.year, target_date.month, target_date.day, 9, 0, tzinfo=BAKU_TZ)
        return scheduled, extract_reminder_title(text)

    if not explicit_24h:
        hour = _adjust_day_period(hour, lower)
    hour = max(0, min(23, hour))

    target_date = (base + timedelta(days=days_offset)).date()
    scheduled = datetime(
        target_date.year, target_date.month, target_date.day, hour, minute, 0, tzinfo=BAKU_TZ
    )
    if scheduled <= base and days_offset == 0:
        scheduled += timedelta(days=1)

    return scheduled, extract_reminder_title(text)


def format_az_datetime(value: str | datetime, reference_time: Optional[datetime] = None) -> str:
    """Human-friendly Azerbaijani date/time, e.g. "sabah, 10 noyabr, saat 09:00"."""
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    dt = dt.astimezone(BAKU_TZ) if dt.tzinfo else dt.replace(tzinfo=BAKU_TZ)
    base = (reference_time or now_baku()).astimezone(BAKU_TZ)

    day_diff = (dt.date() - base.date()).days
    date_part = f"{dt.day} {AZ_MONTHS[dt.month - 1]}"
    if dt.year != base.year:
        date_part += f" {dt.year}"
    prefix = {0: "bu gün, ", 1: "sabah, ", 2: "birigün, "}.get(day_diff, "")
    return f"{prefix}{date_part}, saat {dt:%H:%M}"


def extract_reminder_title(text: str) -> str:
    """Extract clean human-readable reminder title in Azerbaijani."""
    cleaned = text.strip()
    num = r"(?:\d{1,3}|yarım|yarim|bir|iki|üç|dörd|beş|altı|yeddi|səkkiz|doqquz|on)"
    patterns_to_remove = [
        r"(?i)^yaxın[\s,]*",
        r"(?i)\bsabah\b",
        r"(?i)\bbirigün\b",
        r"(?i)\bbu\s*gün\b",
        r"(?i)\bbugün\b",
        r"(?i)\baxşam\b",
        r"(?i)\bsəhər\b",
        r"(?i)\bgecə\b",
        r"(?i)\bgünorta\b",
        rf"(?i)\b{num}\s*saat(?:dan|dən)?\s*(?:sonra|ərzində)\b",
        rf"(?i)\b{num}\s*dəqiqə\w*\s*(?:sonra|ərzində)?\b",
        r"(?i)\bsaat\s*\d{1,2}([:.]\d{2})?\s*(-\s*(da|də|a|ə)|da|də)?\b",
        r"(?i)\b\d{1,2}([:.]\d{2})?\s*-\s*(da|də|a|ə|ya|yə)\b",
        r"(?i)\bsaat\s*(bir|iki|üç|uc|dörd|dord|beş|bes|altı|alti|yeddi|səkkiz|sekkiz|doqquz|on\s*bir|on\s*iki|on)(da|də|-da|-də)?\b",
        r"(?i)\byarımda\b",
        r"(?i)\bmənə\b",
        r"(?i)\bxatırlatma\s*yarat\b",
        r"(?i)\bxatırlat\b",
        r"(?i)\byadıma\s*sal\b",
    ]
    for pat in patterns_to_remove:
        cleaned = re.sub(pat, " ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-?!")

    # Normalize common verb endings into clean action titles
    lower_clean = az_lower(cleaned)
    if "məni oyat" in lower_clean or "oyat" == lower_clean:
        return "Yuxudan oyanmaq"
    if "zəng etməyi" in lower_clean:
        cleaned = re.sub(r"(?i)zəng\s+etməyi", "zəng et", cleaned)
    if "ödənişimi" in lower_clean:
        cleaned = re.sub(r"(?i)ödənişimi", "ödənişi", cleaned)
    if "dərmanımı" in lower_clean:
        cleaned = re.sub(r"(?i)dərmanımı", "dərman qəbulu", cleaned)

    if not cleaned:
        return "Xatırlatma"
    return cleaned[0].upper() + cleaned[1:]
