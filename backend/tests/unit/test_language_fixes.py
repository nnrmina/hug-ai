from datetime import datetime

import pytest

from app.integrations.llm.provider import AzerbaijaniSmartLLMAdapter
from app.utils.datetime_utils import BAKU_TZ, format_az_datetime, parse_azerbaijani_datetime
from app.utils.text_utils import az_lower

# Monday 9 Nov 2026, 10:00 Baku
REF = datetime(2026, 11, 9, 10, 0, tzinfo=BAKU_TZ)


def _p(text):
    return parse_azerbaijani_datetime(text, reference_time=REF)


def test_az_lower():
    assert az_lower("QIZIMA ZƏNG ET") == "qızıma zəng et"
    assert az_lower("İKİ") == "iki"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2 saatdan sonra dərmanı xatırlat", datetime(2026, 11, 9, 12, 0, tzinfo=BAKU_TZ)),
        ("yarım saat sonra xatırlat", datetime(2026, 11, 9, 10, 30, tzinfo=BAKU_TZ)),
        ("15 dəqiqədən sonra xatırlat", datetime(2026, 11, 9, 10, 15, tzinfo=BAKU_TZ)),
        ("Sabah saat 10:30-da həkimə getməyi xatırlat", datetime(2026, 11, 10, 10, 30, tzinfo=BAKU_TZ)),
        # 1–6 without a day-period word means afternoon
        ("saat 3-də dərmanımı xatırlat", datetime(2026, 11, 9, 15, 0, tzinfo=BAKU_TZ)),
        ("səhər saat 6-da məni oyat", datetime(2026, 11, 10, 6, 0, tzinfo=BAKU_TZ)),
        ("axşam saat 9-da xatırlat", datetime(2026, 11, 9, 21, 0, tzinfo=BAKU_TZ)),
        ("gecə saat 11-də xatırlat", datetime(2026, 11, 9, 23, 0, tzinfo=BAKU_TZ)),
        ("gecə saat 2-də xatırlat", datetime(2026, 11, 10, 2, 0, tzinfo=BAKU_TZ)),
        ("saat 14:00-da xatırlat", datetime(2026, 11, 9, 14, 0, tzinfo=BAKU_TZ)),
        # "bir"/"onda" are ordinary words here, not hours -> default tomorrow 09:00
        ("bir dəfə də xatırlat sabah", datetime(2026, 11, 10, 9, 0, tzinfo=BAKU_TZ)),
        ("onda mənə xatırlat", datetime(2026, 11, 10, 9, 0, tzinfo=BAKU_TZ)),
    ],
)
def test_parse_times(text, expected):
    assert _p(text)[0] == expected


def test_relative_title_is_clean():
    assert _p("2 saatdan sonra dərmanımı xatırlat")[1] == "Dərman qəbulu"


def test_format_az_datetime():
    assert format_az_datetime("2026-11-10T09:00:00+04:00", reference_time=REF) == "sabah, 10 noyabr, saat 09:00"
    assert format_az_datetime("2026-11-09T21:00:00+04:00", reference_time=REF) == "bu gün, 9 noyabr, saat 21:00"


@pytest.mark.parametrize(
    "text, intent",
    [
        ("QIZIMA ZƏNG ET", "MAKE_CALL"),
        ("Zəngin kodu nədir", "UNKNOWN"),
        ("Zəngli saatı sabah 7-yə qur", "CREATE_REMINDER"),
        ("Ürəyim ağrıyır", "EMERGENCY_CALL"),
        ("Təcili yardım çağır", "EMERGENCY_CALL"),
        ("103-ə zəng et", "EMERGENCY_CALL"),
        ("112 nömrəsi neçədir?", "GENERAL_QUESTION"),
        ("Təcili yardımın nömrəsi nədir?", "GENERAL_QUESTION"),
    ],
)
def test_intents(text, intent):
    assert AzerbaijaniSmartLLMAdapter().detect_intent(text)["intent"] == intent


def test_security_short_tokens_are_whole_words():
    adapter = AzerbaijaniSmartLLMAdapter()
    # "pin" inside "spinning", "kod" inside "Bakıda kodlaşdırma kursu" should not matter for low risk.
    low = adapter.analyze_security_text("Sabah spinning dərsinə gəlirsən?")
    assert "credential_request" not in low["indicators"]
    high = adapter.analyze_security_text("Təcili! SMS kodunu bizə göndərin, hesabınız bloklanacaq")
    assert "credential_request" in high["indicators"]
    assert high["risk_level"] == "high"
