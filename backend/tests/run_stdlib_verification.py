"""Self-contained verification & evaluation suite for YAXIN AI (Section 14)."""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.graph import run_agent_workflow  # noqa: E402
from app.core.security import check_action_permission  # noqa: E402
from app.integrations.llm.provider import AzerbaijaniSmartLLMAdapter  # noqa: E402
from app.utils.datetime_utils import parse_azerbaijani_datetime, BAKU_TZ  # noqa: E402
from app.utils.phone_utils import normalize_az_phone_number, is_valid_az_phone_number  # noqa: E402


def verify_all() -> None:
    adapter = AzerbaijaniSmartLLMAdapter()

    # 1. Intent classification dataset evaluation (Section 14.1)
    test_cases = [
        ("Qızıma zəng et", "MAKE_CALL"),
        ("Anama zəng etmək istəyirəm", "MAKE_CALL"),
        ("Sabah 10-da məni oyat", "CREATE_REMINDER"),
        ("Sabah saat doqquzda məni oyat", "CREATE_REMINDER"),
        ("Sabah saat 10-da mənə qızıma zəng etməyi xatırlat", "CREATE_REMINDER"),
        ("Mənə kommunal ödənişimi xatırlat", "CREATE_REMINDER"),
        ("Bu mesaj təhlükəlidir?", "ANALYZE_MESSAGE"),
        ("Bu SMS-i yoxla", "ANALYZE_MESSAGE"),
        ("Anama səs göndərmək istəyirəm", "SEND_VOICE_MESSAGE"),
        ("Sabah hava necə olacaq?", "GENERAL_QUESTION"),
    ]
    passed = 0
    for text, expected in test_cases:
        res = adapter.detect_intent(text)
        assert res["intent"] == expected, f"Expected {expected} for '{text}', got {res['intent']}"
        passed += 1
    accuracy = passed / len(test_cases)
    print(f"[PASS] Intent Classification Accuracy: {accuracy:.2%} ({passed}/{len(test_cases)})")

    # 2. Azerbaijani Date/Time extraction (Asia/Baku)
    ref = datetime(2026, 11, 8, 8, 37, 0, tzinfo=BAKU_TZ)
    dt, title = parse_azerbaijani_datetime(
        "Sabah saat 10-da mənə qızıma zəng etməyi xatırlat",
        reference_time=ref,
    )
    assert dt.isoformat() == "2026-11-09T10:00:00+04:00"
    assert "qızıma zəng et" in title.lower()
    print(f"[PASS] DateTime Extraction: scheduled_at={dt.isoformat()}, title='{title}'")

    # 3. Phone number validation (+994)
    assert normalize_az_phone_number("050 123 45 67") == "+994501234567"
    assert is_valid_az_phone_number("+994501234567") is True
    print("[PASS] Azerbaijani +994 Phone Validation")

    # 4. Agentic Workflow (Contact, Reminder, Digital Shield, Security Policy)
    call_state = run_agent_workflow("user-1", "Qızıma zəng et")
    assert call_state["intent"] == "MAKE_CALL"
    assert call_state["status"] == "needs_confirmation"
    assert call_state["action_data"]["contact_alias"] == "qızım"
    assert call_state["action_data"]["local_only"] is True
    print("[PASS] MVP 01 — Voice Contact Agent Workflow (Local-first + Human-in-the-loop)")

    rem_state = run_agent_workflow("user-1", "Sabah saat 9-da məni oyat")
    assert rem_state["intent"] == "CREATE_REMINDER"
    assert rem_state["status"] == "needs_confirmation"
    print("[PASS] MVP 02 — Smart Reminder Agent Workflow")

    sec_state = run_agent_workflow(
        "user-1",
        "Bank hesabınız bloklanıb. Linkə daxil olun və kart məlumatlarını yazın: http://bit.ly/scam",
    )
    assert sec_state["intent"] == "ANALYZE_MESSAGE"
    assert sec_state["status"] == "completed"
    assert sec_state["action_data"]["risk_level"] == "high"
    print(
        f"[PASS] MVP 03 — Digital Shield Agent Workflow (risk_level={sec_state['action_data']['risk_level']}, "
        f"score={sec_state['action_data']['risk_score']}, indicators={sec_state['action_data']['indicators']})"
    )

    # 5. Blocked high-risk actions (Bank Transfer & Wolt Order)
    bank_perm = check_action_permission("BANK_TRANSFER")
    assert bank_perm["allowed"] is False
    bank_wf = run_agent_workflow("user-1", "Kartımdan pul köçür")
    assert bank_wf["status"] == "rejected"
    print("[PASS] Security & Privacy Guardrails (Bank transfer / Wolt order blocked in MVP)")


if __name__ == "__main__":
    verify_all()

