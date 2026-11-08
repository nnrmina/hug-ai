from datetime import datetime
from app.integrations.llm.provider import AzerbaijaniSmartLLMAdapter
from app.utils.datetime_utils import parse_azerbaijani_datetime, BAKU_TZ
from app.utils.phone_utils import normalize_az_phone_number, is_valid_az_phone_number


def compute_wer(reference: str, hypothesis: str) -> float:
    """Calculate Word Error Rate: WER = (S + D + I) / N (Section 14.2)."""
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    n = len(ref_words)
    if n == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0

    dp = [[0] * (len(hyp_words) + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(len(hyp_words) + 1):
        dp[0][j] = j

    for i in range(1, n + 1):
        for j in range(1, len(hyp_words) + 1):
            cost = 0 if ref_words[i - 1] == hyp_words[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost,  # substitution
            )
    return dp[n][len(hyp_words)] / n


def test_intent_classification_evaluation_dataset():
    """Verify intent classification accuracy on Azerbaijani test dataset (Section 14.1)."""
    adapter = AzerbaijaniSmartLLMAdapter()
    dataset = [
        ("Qızıma zəng et", "MAKE_CALL"),
        ("Anama zəng etmək istəyirəm", "MAKE_CALL"),
        ("Oğluma zəng vur", "MAKE_CALL"),
        ("Sabah 10-da məni oyat", "CREATE_REMINDER"),
        ("Sabah saat 9-da mənə xatırlat", "CREATE_REMINDER"),
        ("Sabah saat 10-da mənə qızıma zəng etməyi xatırlat", "CREATE_REMINDER"),
        ("Mənə kommunal ödənişimi xatırlat", "CREATE_REMINDER"),
        ("Bu mesaj təhlükəlidir?", "ANALYZE_MESSAGE"),
        ("Bu SMS-i yoxla", "ANALYZE_MESSAGE"),
        ("Bank hesabınız bloklanıb linkə daxil olun", "ANALYZE_MESSAGE"),
        ("Anama səs göndərmək istəyirəm", "SEND_VOICE_MESSAGE"),
        ("Sabah hava necə olacaq?", "GENERAL_QUESTION"),
    ]

    correct = 0
    for text, expected_intent in dataset:
        pred = adapter.detect_intent(text)
        if pred["intent"] == expected_intent:
            correct += 1

    accuracy = correct / len(dataset)
    assert accuracy >= 0.95


def test_azerbaijani_datetime_extraction():
    ref = datetime(2026, 11, 8, 8, 37, 0, tzinfo=BAKU_TZ)
    dt, title = parse_azerbaijani_datetime(
        "Sabah saat 10-da mənə qızıma zəng etməyi xatırlat",
        reference_time=ref,
    )
    assert dt.year == 2026
    assert dt.month == 11
    assert dt.day == 9
    assert dt.hour == 10
    assert dt.minute == 0
    assert "qızıma zəng et" in title.lower()


def test_az_phone_number_utils():
    assert normalize_az_phone_number("050 123 45 67") == "+994501234567"
    assert is_valid_az_phone_number("+994501234567") is True
    assert is_valid_az_phone_number("12345") is False


def test_wer_calculation():
    assert compute_wer("Qızıma zəng et", "Qızıma zəng et") == 0.0
    wer = compute_wer("Sabah saat doqquzda məni oyat", "Sabah saat 9-da məni oyat")
    assert 0.0 < wer <= 0.25

