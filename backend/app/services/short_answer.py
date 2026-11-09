"""Short spoken answers: "hə / yox" on the confirm screen, "birinci / ikinci" for the SIM.

The browser's own speech recognition is unreliable here: inside the Android app (WebView) it
does not work at all, and in Chrome it often misses one-syllable Azerbaijani words like "hə".
So the client records the answer and Gemini transcribes + classifies it. Without Gemini (no
key, quota, timeout) the browser's transcript hint is classified with simple word rules.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import logger

Answer = Literal["yes", "no", "unclear"]


class ShortAnswer(BaseModel):
    transcript: str = Field(default="", description="Exactly what the user said, in its own language")
    answer: Answer = Field(default="unclear", description="yes / no / unclear for a confirmation question")


PROMPT = """You hear an elderly user's SHORT spoken reply to a question from a voice assistant.
The user speaks Azerbaijani (sometimes Russian). Transcribe the reply exactly, then classify it.

answer:
- "yes": agreement, e.g. bəli, hə, həə, hə də, he, olar, olsun, yaxşı, düzdür, razıyam, əlbəttə,
  elə, et, zəng et, göndər, da, ага, конечно, давай.
- "no": refusal, e.g. yox, xeyr, istəmirəm, lazım deyil, ləğv et, etmə, dayan, нет, не надо.
- "unclear": silence, noise, or anything else (also when the reply names an option such as
  "birinci", "ikinci", "Azercell" — keep it in transcript).
Never guess "yes" from noise: a call or order must only happen on a clear yes."""

# --- rule fallback (mirrors public/static/js/audio/webspeech.js) --------------------------
_FOLD = str.maketrans({"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ğ": "g", "ş": "s", "ç": "c"})
YES = {
    "beli", "bel", "he", "ha", "hehe", "heri", "aha", "eha", "ehe", "ahe", "hede",
    "oldu", "olar", "olsun", "olsunda", "yaxsi", "yaxsidir", "duzdur", "dogrudur", "duz", "dogru",
    "razi", "raziyam", "elbete", "elbette", "tesdiq", "tesdiqle", "tesdiqleyirem", "tesdiqledim",
    "et", "ele", "elesin", "edin", "zeng", "yarat", "yaradin", "sifaris", "gonder", "gonderin", "ver",
    "isteyirem", "lazimdir", "mumkundur", "yes", "ok", "okey", "okay", "da", "aqa",
    "да", "ага", "угу", "конечно", "давай", "хорошо", "звони", "можно", "ладно",
}
NO = {
    "xeyr", "xeir", "xeyir", "yox", "yoxe", "yo", "yoh", "legv", "istemirem", "lazim", "deyil",
    "dayan", "imtina", "gerekmez", "no", "nope", "olmaz", "etme", "eleme",
    "нет", "не", "неа", "отмена", "отмени", "стоп",
}


def _fold(word: str) -> str:
    # Azerbaijani capital İ/I must lower to i/ı before folding
    w = word.replace("İ", "i").replace("I", "ı").lower().translate(_FOLD)
    return re.sub(r"(.)\1+", r"\1", w)


def classify_yes_no(text: Optional[str]) -> Answer:
    words = [_fold(w) for w in re.split(r"[\s,.!?;:|\-]+", text or "") if w]
    if any(w in NO for w in words):
        return "no"
    if any(w in YES for w in words):
        return "yes"
    return "unclear"


def understand_short_answer(
    audio: Optional[bytes],
    mime_type: Optional[str],
    question: Optional[str] = None,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    """→ {"transcript": str, "answer": "yes" | "no" | "unclear", "engine": str}"""
    hint = (hint or "").strip()
    if audio and settings.gemini_key:
        try:
            from google.genai import types

            from app.integrations.llm.gemini import get_gemini_adapter

            contents = []
            if question:
                contents.append(f"The assistant asked: {question[:300]}")
            contents.append(types.Part.from_bytes(data=audio, mime_type=mime_type or "audio/wav"))
            if hint:
                contents.append(f"(Browser speech recognition heard: {hint[:200]})")
            response = get_gemini_adapter().client.models.generate_content(
                model=settings.LLM_MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=PROMPT,
                    response_mime_type="application/json",
                    response_schema=ShortAnswer,
                    temperature=0,
                    http_options=types.HttpOptions(timeout=max(10000, settings.LLM_TIMEOUT_TEXT_MS)),
                ),
            )
            parsed = ShortAnswer.model_validate_json(getattr(response, "text", None) or "")
            transcript = parsed.transcript.strip() or hint
            answer = parsed.answer
            # A clear rule match on the words wins over a model "unclear" ("hə" → yes)
            if answer == "unclear":
                answer = classify_yes_no(transcript)
            return {"transcript": transcript, "answer": answer, "engine": "gemini"}
        except Exception as exc:  # quota, timeout, bad JSON → rule fallback below
            logger.warning("short answer: gemini unavailable (%s)", type(exc).__name__)
    return {"transcript": hint, "answer": classify_yes_no(hint), "engine": "rule_based"}
