"""Gemini adapter behaviour with a fake client — the real API is never called in tests."""
import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.agents.graph import run_agent_workflow
from app.integrations.llm.gemini import GeminiLLMAdapter
from app.utils.datetime_utils import BAKU_TZ

NOW = datetime(2026, 11, 9, 14, 30, tzinfo=BAKU_TZ)


class FakeModels:
    def __init__(self, reply):
        self.reply = reply
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        if isinstance(self.reply, Exception):
            raise self.reply
        text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply, ensure_ascii=False)
        return SimpleNamespace(text=text)


def make_adapter(reply):
    models = FakeModels(reply)
    return GeminiLLMAdapter(client=SimpleNamespace(models=models), model="test-model"), models


def understanding(**fields):
    base = {"transcript": "", "intent": "UNKNOWN", "confidence": 0.9, "missing_slots": []}
    base.update(fields)
    return base


def test_call_maps_alias_and_never_sends_contacts():
    adapter, models = make_adapter(
        understanding(transcript="Mamama zvanok elə", intent="MAKE_CALL", contact_alias="mama")
    )
    out = adapter.understand(text="Mamama zvanok elə", now=NOW)

    assert out["engine"] == "gemini"
    assert out["intent"] == "MAKE_CALL"
    assert out["contact_alias"] == "mama"
    assert out["requires_confirmation"] is True
    assert "mama" in out["search_candidates"]
    sent = " ".join(str(c) for c in models.calls[0]["contents"])
    assert "+994" not in sent and "Sevinc" not in sent  # no device contacts / numbers leave the phone


def test_reminder_uses_gemini_time_when_valid():
    when = (NOW + timedelta(days=1)).replace(hour=10, minute=0)
    adapter, _ = make_adapter(
        understanding(
            transcript="Sabah saat 10-da dərmanımı xatırlat",
            intent="CREATE_REMINDER",
            title="Dərman qəbulu",
            scheduled_at=when.isoformat(),
        )
    )
    out = adapter.understand(text="Sabah saat 10-da dərmanımı xatırlat", now=NOW)
    assert out["scheduled_at"] == when.isoformat()
    assert out["title"] == "Dərman qəbulu"
    assert "clarification_question" not in out


@pytest.mark.parametrize("bad_time", ["2020-01-01T10:00:00+04:00", "2026-11-10T10:00:00", "not-a-date"])
def test_reminder_invalid_time_falls_back_to_parser(bad_time):
    text = "Sabah saat 10-da dərmanımı xatırlat"
    adapter, _ = make_adapter(
        understanding(transcript=text, intent="CREATE_REMINDER", title="Dərman qəbulu", scheduled_at=bad_time)
    )
    out = adapter.understand(text=text, now=NOW)
    assert out["scheduled_at"] == "2026-11-10T10:00:00+04:00"


def test_reminder_without_any_time_asks_when():
    adapter, _ = make_adapter(
        understanding(transcript="Dərmanımı xatırlat", intent="CREATE_REMINDER", title="Dərman qəbulu")
    )
    out = adapter.understand(text="Dərmanımı xatırlat", now=NOW)
    assert "scheduled_at" not in out
    assert out["missing_slots"] == ["scheduled_at"]
    assert out["clarification_question"]

    state = run_agent_workflow("user-1", "Dərmanımı xatırlat", llm_parsed=out)
    assert state["status"] == "needs_clarification"
    assert state["response"] == out["clarification_question"]


@pytest.mark.parametrize(
    "error",
    [
        errors.APIError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}}),
        errors.APIError(503, {"error": {"code": 503, "message": "overloaded", "status": "UNAVAILABLE"}}),
        TimeoutError("timed out"),
        ConnectionError("offline"),
    ],
)
def test_api_failures_fall_back_to_rules(error):
    adapter, _ = make_adapter(error)
    out = adapter.understand(text="Qızıma zəng et", now=NOW)
    assert out["engine"] == "rule_based"
    assert out["intent"] == "MAKE_CALL"
    assert out["contact_alias"] == "qızım"
    assert out["fallback_reason"]


def test_malformed_json_falls_back_to_rules():
    adapter, _ = make_adapter("{not json")
    out = adapter.understand(text="Taksi çağır", now=NOW)
    assert out["engine"] == "rule_based"
    assert out["intent"] == "ORDER_TAXI"


def test_audio_failure_without_text_reports_stt_failed():
    adapter, _ = make_adapter(TimeoutError("slow"))
    out = adapter.understand(audio=b"RIFF....WAVE", mime_type="audio/wav", now=NOW)
    assert out["stt_failed"] is True


def test_audio_is_sent_inline_with_mime_type():
    adapter, models = make_adapter(
        understanding(transcript="Taksi çağır", intent="ORDER_TAXI")
    )
    out = adapter.understand(audio=b"RIFF0000WAVEfmt ", mime_type="audio/wav", now=NOW)
    assert out["transcript"] == "Taksi çağır"
    parts = [c for c in models.calls[0]["contents"] if not isinstance(c, str)]
    assert parts and parts[0].inline_data.mime_type == "audio/wav"


def test_bank_transfer_block_is_enforced():
    adapter, _ = make_adapter(
        understanding(transcript="Kartımdan oğluma 50 manat köçür", intent="UNKNOWN", blocked_action="BANK_TRANSFER")
    )
    out = adapter.understand(text="Kartımdan oğluma 50 manat köçür", now=NOW)
    state = run_agent_workflow("user-1", out["transcript"], llm_parsed=out)
    assert state["status"] == "rejected"


def test_general_answer_is_used_and_capped():
    long_answer = "Mən sizin köməkçinizəm. " * 40
    adapter, _ = make_adapter(
        understanding(transcript="Sən kimsən?", intent="GENERAL_QUESTION", answer=long_answer)
    )
    out = adapter.understand(text="Sən kimsən?", now=NOW)
    assert len(out["answer"]) <= 321
    state = run_agent_workflow("user-1", "Sən kimsən?", llm_parsed=out)
    assert state["response"] == out["answer"]


def test_scam_merge_keeps_the_higher_risk():
    text = "Salam, bu mesaj normaldırmı: kartınız bloklanıb, kodu göndərin"
    adapter, _ = make_adapter(
        understanding(
            transcript=text,
            intent="ANALYZE_MESSAGE",
            message_to_analyze="kartınız bloklanıb, kodu göndərin",
            security={
                "risk_level": "low",
                "risk_score": 10,
                "indicators": ["odd_wording"],
                "explanation": "Normal görünür.",
                "recommendation": "Narahat olmayın.",
            },
        )
    )
    out = adapter.understand(text=text, now=NOW)
    state = run_agent_workflow("user-1", text, llm_parsed=out)
    data = state["action_data"]
    assert data["risk_level"] in ("medium", "high")  # rules saw urgency + code request
    assert "odd_wording" in data["indicators"]
    assert data["explanation"] != "Normal görünür."  # understated LLM wording is not adopted


def test_food_item_selects_catalog_entry():
    adapter, _ = make_adapter(
        understanding(transcript="Mənə bir dönər gətirin", intent="ORDER_FOOD", food_item="doner")
    )
    out = adapter.understand(text="Mənə bir dönər gətirin", now=NOW)
    state = run_agent_workflow("user-1", out["transcript"], llm_parsed=out)
    assert state["action_data"]["order"]["item"].startswith("Dönər")


def test_history_is_included_in_prompt():
    adapter, models = make_adapter(
        understanding(transcript="sabah 9-da", intent="CREATE_REMINDER", title="Dərman qəbulu",
                      scheduled_at=(NOW + timedelta(days=1)).replace(hour=9, minute=0).isoformat())
    )
    history = [{"user": "Dərmanımı xatırlat", "assistant": "Nə vaxt xatırladım?"}]
    adapter.understand(text="sabah 9-da", history=history, now=NOW)
    context = models.calls[0]["contents"][0]
    assert "Nə vaxt xatırladım?" in context and "2026-11-09T14:30" in context


def test_silent_audio_with_browser_hint_reuses_the_text():
    class TwoReplies(FakeModels):
        def generate_content(self, *, model, contents, config):
            self.reply = understanding(transcript="", intent="UNKNOWN") if not self.calls else understanding(
                transcript="Taksi çağır", intent="ORDER_TAXI")
            return super().generate_content(model=model, contents=contents, config=config)

    models = TwoReplies(None)
    adapter = GeminiLLMAdapter(client=SimpleNamespace(models=models), model="m")
    out = adapter.understand(text="Taksi çağır", audio=b"RIFF", mime_type="audio/wav", now=NOW)
    assert out["intent"] == "ORDER_TAXI" and len(models.calls) == 2


def test_capabilities_endpoint(client):
    data = client.get("/api/v1/assistant/capabilities").json()
    assert data["engine"] == "rule_based" and data["audio_understanding"] is False
