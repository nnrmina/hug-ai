import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

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


def now_baku() -> datetime:
    """Return current datetime in Asia/Baku (+04:00) timezone."""
    return datetime.now(BAKU_TZ)


def parse_azerbaijani_datetime(
    text: str,
    reference_time: Optional[datetime] = None,
) -> Tuple[datetime, str]:
    """Extract scheduled datetime (Asia/Baku) and cleaned title from Azerbaijani command text."""
    base = (reference_time or now_baku()).astimezone(BAKU_TZ)
    lower = text.lower().strip()

    days_offset = 0
    if "birigün" in lower or "biri gün" in lower:
        days_offset = 2
    elif "sabah" in lower:
        days_offset = 1
    elif "bu gün" in lower or "bugün" in lower:
        days_offset = 0

    hour = 9
    minute = 0
    matched_time = False

    # Check relative minutes/hours first: e.g., "30 dəqiqədən sonra", "2 saatdan sonra"
    rel_min_match = re.search(r"(\d{1,3})\s*dəqiqə", lower)
    rel_hour_match = re.search(r"(\d{1,2})\s*saat\s*(sonra|ərzində)", lower)
    if rel_min_match:
        scheduled = base + timedelta(minutes=int(rel_min_match.group(1)))
        matched_time = True
    elif rel_hour_match:
        scheduled = base + timedelta(hours=int(rel_hour_match.group(1)))
        matched_time = True
    else:
        # Check explicit HH:MM pattern (e.g., "10:30", "09:00")
        colon_match = re.search(r"\b(\d{1,2}):(\d{2})\b", lower)
        if colon_match:
            hour = int(colon_match.group(1))
            minute = int(colon_match.group(2))
            matched_time = True
        else:
            # Check numeric hour with suffix: e.g., "saat 10-da", "9-da", "8-də"
            num_hour_match = re.search(
                r"(?:saat\s*)?(\d{1,2})\s*(?:-\s*(?:da|də|a|ə)|da\b|də\b)",
                lower,
            )
            if num_hour_match:
                hour = int(num_hour_match.group(1))
                matched_time = True
            else:
                # Check Azerbaijani word hours: e.g., "saat doqquzda", "beşdə"
                for word, val in sorted(AZ_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
                    pattern = rf"\b{re.escape(word)}(?:da|də|-da|-də)?\b"
                    if re.search(pattern, lower):
                        hour = val
                        matched_time = True
                        break

        # Adjust for evening/afternoon keywords ("axşam", "günorta")
        if ("axşam" in lower or "axsam" in lower or "gecə" in lower) and 1 <= hour <= 11:
            hour += 12
        elif ("günorta" in lower or "gunorta" in lower) and 1 <= hour <= 6:
            hour += 12

        if not matched_time and days_offset == 0:
            # Default to next day 09:00 if no time was mentioned, or +1 hour if today
            days_offset = 1
            hour = 9
            minute = 0

        target_date = (base + timedelta(days=days_offset)).date()
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))
        scheduled = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            hour,
            minute,
            0,
            tzinfo=BAKU_TZ,
        )
        if scheduled <= base and days_offset == 0:
            scheduled += timedelta(days=1)

    title = extract_reminder_title(text)
    return scheduled, title


def extract_reminder_title(text: str) -> str:
    """Extract clean human-readable reminder title in Azerbaijani."""
    cleaned = text.strip()
    patterns_to_remove = [
        r"(?i)^yaxın[\s,]*",
        r"(?i)\bsabah\b",
        r"(?i)\bbu\s*gün\b",
        r"(?i)\bbugün\b",
        r"(?i)\baxşam\b",
        r"(?i)\bsəhər\b",
        r"(?i)\bgünorta\b",
        r"(?i)\bsaat\s*\d{1,2}(:\d{2})?\s*(-\s*(da|də|a|ə)|da|də)?\b",
        r"(?i)\b\d{1,2}(:\d{2})?\s*-\s*(da|də|a|ə)\b",
        r"(?i)\bsaat\s*(bir|iki|üç|uc|dörd|dord|beş|bes|altı|alti|yeddi|səkkiz|sekkiz|doqquz|on\s*bir|on\s*iki|on)(da|də|-da|-də)?\b",
        r"(?i)\bmənə\b",
        r"(?i)\bxatırlatma\s*yarat\b",
        r"(?i)\bxatırlat\b",
        r"(?i)\byadıma\s*sal\b",
    ]
    for pat in patterns_to_remove:
        cleaned = re.sub(pat, " ", cleaned)

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-?!")

    # Normalize common verb endings into clean action titles
    lower_clean = cleaned.lower()
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



AZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr",
]


def format_az_datetime(value, reference_time: Optional[datetime] = None) -> str:
    """Human, speakable Azerbaijani form of a datetime, e.g. 'sabah saat 10:00'."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    if not isinstance(value, datetime):
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=BAKU_TZ)
    local = value.astimezone(BAKU_TZ)
    today = (reference_time or now_baku()).astimezone(BAKU_TZ).date()

    delta_days = (local.date() - today).days
    if delta_days == 0:
        day = "bu gün"
    elif delta_days == 1:
        day = "sabah"
    elif delta_days == 2:
        day = "birigün"
    else:
        day = f"{local.day} {AZ_MONTHS[local.month - 1]}"
    return f"{day} saat {local:%H:%M}"
