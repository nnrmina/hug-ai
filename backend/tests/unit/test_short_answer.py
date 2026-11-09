"""Short spoken answers on the confirm screen ("hə" / "yox") and the SIM choice."""
import pytest

from app.core.config import settings
from app.services.short_answer import classify_yes_no


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hə", "yes"), ("Həə", "yes"), ("hə də", "yes"), ("he", "yes"), ("Bəli", "yes"),
        ("olar", "yes"), ("yaxşı", "yes"), ("düzdür", "yes"), ("zəng et", "yes"), ("да", "yes"),
        ("yox", "no"), ("Xeyr", "no"), ("istəmirəm", "no"), ("zəng etmə", "no"),
        ("lazım deyil", "no"), ("yox da", "no"), ("нет", "no"),
        ("həkim", "unclear"), ("hmm", "unclear"), ("", "unclear"), ("birinci", "unclear"),
        ("İSTƏMİRƏM", "no"),
    ],
)
def test_classify_yes_no(text, expected):
    assert classify_yes_no(text) == expected


def test_endpoint_without_gemini_uses_transcript(client, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None, raising=False)
    monkeypatch.setattr(settings, "LLM_API_KEY", None, raising=False)
    res = client.post("/api/v1/assistant/short-answer", data={"transcript": "hə", "question": "Zəng edilsin?"})
    assert res.status_code == 200
    assert res.json()["answer"] == "yes"
    assert res.json()["transcript"] == "hə"


def test_endpoint_requires_audio_or_transcript(client):
    assert client.post("/api/v1/assistant/short-answer", data={}).status_code == 400


def test_endpoint_rejects_unknown_audio_type(client):
    res = client.post(
        "/api/v1/assistant/short-answer",
        files={"audio": ("a.exe", b"MZ\x90\x00", "application/octet-stream")},
        data={"mime_type": "application/octet-stream"},
    )
    assert res.status_code == 415
