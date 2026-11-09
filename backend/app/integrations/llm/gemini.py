"""Gemini-powered understanding for HUG / YAXIN AI.

One `generate_content` call per turn handles audio *or* text: it transcribes Azerbaijani
speech, classifies the intent and extracts the slots as schema-validated JSON. Anything
that goes wrong (no key, quota 429, timeout, malformed JSON) falls back to the
deterministic rule-based adapter, so the assistant never stops working.

Privacy: only the user's own words (and the last few turns) are sent. Contact lists,
phone numbers and saved reminders never leave the device / database.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.core.logging import logger
from app.core.security import ACTION_RISK_POLICY
from app.integrations.llm.base import BaseLLMAdapter
from app.integrations.llm.provider import (
    ASK_WHEN,
    ASK_WHO,
    AzerbaijaniSmartLLMAdapter,
    get_rule_adapter,
)
from app.utils.datetime_utils import BAKU_TZ, now_baku, parse_azerbaijani_datetime_ex

MAX_ANSWER_CHARS = 320
MIN_DEADLINE_MS = 10000  # Gemini API rejects shorter request deadlines
AZ_WEEKDAYS = ["bazar ertəsi", "çərşənbə axşamı", "çərşənbə", "cümə axşamı", "cümə", "şənbə", "bazar"]
CONFIRM_INTENTS = {
    "MAKE_CALL",
    "SEND_VOICE_MESSAGE",
    "CREATE_REMINDER",
    "ORDER_FOOD",
    "ORDER_PHARMACY",
    "ORDER_TAXI",
    "CREATE_MEDICATION",
}

IntentName = Literal[
    "MAKE_CALL",
    "SEND_VOICE_MESSAGE",
    "CREATE_REMINDER",
    "ANALYZE_MESSAGE",
    "ORDER_FOOD",
    "ORDER_PHARMACY",
    "ORDER_TAXI",
    "EMERGENCY",
    "CREATE_MEDICATION",
    "MEDICATION_TAKEN",
    "CHECKIN",
    "WEATHER",
    "FIND_PLACE",
    "LOG_HEALTH",
    "HEALTH_QUERY",
    "OPEN_SCREEN",
    "GENERAL_QUESTION",
    "UNKNOWN",
]


class SecurityAssessment(BaseModel):
    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(ge=0, le=100)
    indicators: List[str] = Field(default_factory=list)
    explanation: str
    recommendation: str


class Understanding(BaseModel):
    transcript: str = Field(description="Exactly what the user said, in Azerbaijani script.")
    intent: IntentName
    confidence: float = Field(ge=0.0, le=1.0)
    contact_alias: Optional[str] = None
    title: Optional[str] = None
    scheduled_at: Optional[str] = None
    food_item: Optional[Literal["tantuni", "doner", "bozbas"]] = None
    message_to_analyze: Optional[str] = None
    answer: Optional[str] = None
    clarification_question: Optional[str] = None
    missing_slots: List[str] = Field(default_factory=list)
    blocked_action: Optional[Literal["BANK_TRANSFER", "MEDICAL_DECISION"]] = None
    security: Optional[SecurityAssessment] = None
    med_times: List[str] = Field(default_factory=list, description="HH:MM (24h) daily times for CREATE_MEDICATION")
    mood: Optional[Literal["good", "ok", "bad"]] = None
    language: Literal["az", "ru"] = "az"
    weather_day: Optional[Literal["today", "tomorrow"]] = None
    place_type: Optional[Literal["pharmacy", "hospital"]] = None
    health_kind: Optional[Literal["bp", "sugar", "pulse", "temp", "weight"]] = None
    health_value: Optional[float] = None
    health_value2: Optional[float] = None
    screen: Optional[Literal["meds", "reminders", "family", "settings"]] = None
    next_step: Optional[str] = Field(default=None, description="The rest of a multi-step request as one standalone command")


SYSTEM_PROMPT = """You are HUG, a warm, patient voice assistant for elderly people in Azerbaijan.
language: "ru" if the user speaks Russian, otherwise "az". Every user-facing string you write
(answer, clarification_question, title, next_step, security texts) MUST be in that language:
natural polite Azerbaijani (Latin script) or Russian, short and easy to understand when spoken aloud.
Always address the user respectfully: the formal "siz" form in Azerbaijani (never "sən"), "Вы" in Russian.

For each turn return ONE JSON object matching the schema.

transcript: the user's words verbatim in Azerbaijani (fix obvious speech-recognition spelling only).
If the audio is silent or unintelligible, return intent UNKNOWN, transcript "" and a short
clarification_question asking them to repeat.

intent — pick exactly one:
- MAKE_CALL: call someone ("qızıma zəng et", "mamama zvanok elə", "Almazı yığ").
- SEND_VOICE_MESSAGE: send someone a message or tell them something ("qızıma de ki gecikirəm").
- CREATE_REMINDER: remind / wake up / alarm at a time ("sabah 10-da dərmanımı xatırlat").
- ANALYZE_MESSAGE: user asks whether a message/SMS/call is a scam, or reads one out.
- ORDER_FOOD: order a meal (Wolt, tantuni, dönər, bozbaş, "yemək sifariş et").
- ORDER_PHARMACY: order medicine from a pharmacy (aptek, kardiomaqnil, "dərman sifariş et").
  Note: "remind me to take my medicine" is CREATE_REMINDER, not ORDER_PHARMACY.
- ORDER_TAXI: call a taxi / car.
- EMERGENCY: the user needs urgent help NOW: "kömək edin", "yıxıldım", "ürəyim ağrıyır",
  "nəfəs ala bilmirəm", "təcili yardım çağır", "özümü çox pis hiss edirəm", "huşumu itirirəm".
  When in doubt between EMERGENCY and anything else, choose EMERGENCY. Never block it.
- CREATE_MEDICATION: a REPEATING medicine schedule ("hər gün", "səhər və axşam", "gündə iki dəfə"):
  title = medicine name (e.g. "Kardiomaqnil", "Təzyiq dərmanı"), med_times = every daily time as
  HH:MM 24h ("səhər 9" -> "09:00", "axşam 9" -> "21:00", "gündə 2 dəfə" with no times -> ask when).
  A ONE-OFF "sabah 10-da dərmanımı xatırlat" stays CREATE_REMINDER.
- MEDICATION_TAKEN: the user says they took their medicine ("dərmanımı içdim", "həbi atdım").
- CHECKIN: the user tells how they feel today without asking for anything ("özümü yaxşı hiss edirəm",
  "bu gün halım yoxdur", "başım bir az ağrıyır"): mood good | ok | bad, and answer with one short
  warm sentence in `answer`. Severe symptoms are EMERGENCY instead.
- WEATHER: weather questions ("bu gün hava necədir", "sabah yağış yağacaq?", "какая погода"):
  weather_day today | tomorrow. Do not answer it yourself — live data is fetched for you.
- FIND_PLACE: where is the nearest pharmacy / hospital ("ən yaxın aptek hardadır",
  "yaxınlıqda xəstəxana", "где ближайшая аптека"): place_type pharmacy | hospital (poliklinika = hospital).
  Ordering medicine from a pharmacy is ORDER_PHARMACY instead.
- LOG_HEALTH: the user reports a measurement: blood pressure "təzyiqim 140-a 90" (health_kind bp,
  health_value 140 = systolic, health_value2 90 = diastolic), sugar "şəkərim 7.5" (sugar, mmol/L),
  pulse "nəbzim 80" (pulse), temperature "qızdırmam 38" (temp), weight "çəkim 72 kilo" (weight).
- HEALTH_QUERY: the user asks about their own recent measurements ("son təzyiqlərim necədir").
- OPEN_SCREEN: the user wants to SEE a part of the app ("dərmanlarımı göstər", "təqvimi aç",
  "xatırlatmalarıma bax", "ailəmi göstər", "tənzimləmələri aç"): screen meds | reminders | family | settings.
  "Remind me / take medicine" requests are NOT this.
- GENERAL_QUESTION: greetings, small talk, questions about you or general knowledge.
- UNKNOWN: anything else, or when you genuinely cannot tell.

Slots:
- contact_alias: ALWAYS an Azerbaijani word even when the user speaks Russian
  ("дочке/дочери" -> "qızım", "сыну" -> "oğlum", "маме" -> "ana", "внуку" -> "nəvəm", "Алмаз" -> "Almaz").
  The person exactly as named, in nominative form without the dative suffix
  ("qızıma" -> "qızım", "Almaz xalaya" -> "Almaz xala", "mamama" -> "mama"). Never invent phone
  numbers. Elderly users mostly name relatives; when the audio is unclear prefer the closest
  common word: mama, ana, ata, baba, nənə, qızım, oğlum, bacım, qardaşım, nəvəm, gəlinim,
  kürəkənim, əmim, dayım, xalam, bibim, həkim (e.g. "məmməmə" -> "mama", "nəvəmə" -> "nəvəm").
  If no person is named for MAKE_CALL / SEND_VOICE_MESSAGE, set contact_alias null,
  missing_slots ["contact_alias"] and ask who.
- title (reminders): short noun phrase, e.g. "Dərman qəbulu", "Həkim qəbulu". For voice messages,
  put the message content in title.
- scheduled_at (reminders): ISO 8601 with +04:00 offset, resolved against the current Baku time
  below, always in the future. If the user gave no day and no time, set it null, add
  "scheduled_at" to missing_slots and ask when. "səhər" = morning, "axşam" = evening,
  "günorta" = afternoon; with no part of day, assume the next upcoming occurrence.
- food_item: tantuni | doner | bozbas when mentioned.
- message_to_analyze + security (ANALYZE_MESSAGE): judge scam risk (urgency, requests for
  card/PIN/OTP, suspicious links, impersonation of banks or officials, prizes). Explain in
  1-2 sentences and give one clear recommendation.
- answer (GENERAL_QUESTION only): at most 2 short sentences. You have NO internet or live data:
  for news, prices or exchange rates, say kindly that you cannot see live information.
  Never give medical diagnoses or dosing advice, nor financial/investment advice.
- blocked_action: BANK_TRANSFER for any request to send/transfer money or pay from a card;
  MEDICAL_DECISION for requests to change, stop or choose medication or treatment. Use intent
  UNKNOWN in those cases.

Multi-step requests ("tantuni sifariş et, sonra qızıma de ki yemək gəlir", "...və sonra..."):
put ONLY the first action in intent/slots, and the remaining request rephrased as one standalone
command in next_step (e.g. "Qızıma mesaj göndər ki yemək gəlir"). Otherwise next_step is null.

Use the previous turns to resolve follow-ups: if the assistant just asked a question (e.g. "Nə vaxt
xatırladım?") the user's reply fills that slot of the SAME intent, keeping earlier details."""


class GeminiLLMAdapter(BaseLLMAdapter):
    """Gemini adapter with automatic rule-based fallback."""

    def __init__(self, client: Any = None, model: Optional[str] = None,
                 fallback: Optional[AzerbaijaniSmartLLMAdapter] = None):
        self._client = client
        self.model = model or settings.LLM_MODEL_NAME
        self.fallback = fallback or get_rule_adapter()

    # -- plumbing ---------------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=settings.gemini_key)
        return self._client

    def _call(self, contents: List[Any], timeout_ms: int) -> Understanding:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=Understanding,
                temperature=0.2,
                http_options=types.HttpOptions(timeout=max(MIN_DEADLINE_MS, timeout_ms)),
            ),
        )
        raw = getattr(response, "text", None) or ""
        return Understanding.model_validate_json(raw)

    @staticmethod
    def _context_block(history: Optional[List[Dict[str, Any]]], now: datetime) -> str:
        lines = [
            f"Current Baku time: {now.isoformat(timespec='minutes')} ({AZ_WEEKDAYS[now.weekday()]}).",
        ]
        turns = [t for t in (history or []) if t.get("user") or t.get("assistant")][-settings.SESSION_MAX_TURNS:]
        if turns:
            lines.append("Previous turns (oldest first):")
            for t in turns:
                if t.get("user"):
                    lines.append(f"User: {str(t['user'])[:400]}")
                if t.get("assistant"):
                    lines.append(f"Assistant: {str(t['assistant'])[:400]}")
        return "\n".join(lines)

    # -- BaseLLMAdapter ----------------------------------------------------
    def detect_intent(self, message: str) -> Dict[str, Any]:
        return self.understand(text=message)

    def analyze_security_text(self, message: str) -> Dict[str, Any]:
        return self.fallback.analyze_security_text(message)

    def understand(
        self,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = (now or now_baku()).astimezone(BAKU_TZ)
        text = (text or "").strip() or None
        if not text and not audio:
            return self.fallback.understand(text=None, history=history, now=now)

        contents: List[Any] = [self._context_block(history, now)]
        if audio:
            from google.genai import types

            contents.append(types.Part.from_bytes(data=audio, mime_type=mime_type or "audio/wav"))
            contents.append("Understand the user's spoken request in the audio above.")
            if text:
                contents.append(f"(Browser speech recognition heard: {text})")
            timeout_ms = settings.LLM_TIMEOUT_AUDIO_MS
        else:
            contents.append(f"User: {text}")
            timeout_ms = settings.LLM_TIMEOUT_TEXT_MS

        started = time.monotonic()
        try:
            parsed = self._call(contents, timeout_ms)
        except ValidationError as exc:
            return self._fallback(text, audio, history, now, f"invalid JSON: {exc.error_count()} errors")
        except Exception as exc:  # APIError (429/5xx), timeouts, network, auth
            status = getattr(exc, "code", None) or getattr(exc, "status", None) or type(exc).__name__
            return self._fallback(text, audio, history, now, f"{status}")

        logger.info("gemini ok model=%s intent=%s %.0fms", self.model, parsed.intent,
                    (time.monotonic() - started) * 1000)
        if audio and text and not (parsed.transcript or "").strip():
            # Audio came through silent (e.g. the phone gave the mic to browser speech
            # recognition) but the browser heard words: understand those instead.
            return self.understand(text=text, history=history, now=now)
        return self._to_action(parsed, text, now)

    # -- fallback & mapping ------------------------------------------------
    def _fallback(self, text, audio, history, now, reason: str) -> Dict[str, Any]:
        logger.warning("gemini unavailable (%s) -> rule_based fallback", reason)
        result = self.fallback.understand(text=text, audio=audio, history=history, now=now)
        result["fallback_reason"] = reason
        return result

    def _to_action(self, u: Understanding, typed_text: Optional[str], now: datetime) -> Dict[str, Any]:
        transcript = (u.transcript or typed_text or "").strip()
        out: Dict[str, Any] = {
            "intent": u.intent,
            "confidence": round(float(u.confidence), 2),
            "requires_confirmation": u.intent in CONFIRM_INTENTS,
            "transcript": transcript,
            "engine": "gemini",
            "lang": u.language if u.language in ("az", "ru") else "az",
        }
        if u.next_step and u.next_step.strip() and u.intent not in ("EMERGENCY", "UNKNOWN"):
            out["next_step"] = u.next_step.strip()[:300]
        if u.missing_slots:
            out["missing_slots"] = list(u.missing_slots)

        # Hard safety rails: only accept blocks that the policy table really disallows
        if u.blocked_action and not ACTION_RISK_POLICY.get(u.blocked_action, {}).get("allowed_in_mvp", True):
            out.update(intent="UNKNOWN", requires_confirmation=False, blocked_action=u.blocked_action,
                       reason=ACTION_RISK_POLICY[u.blocked_action].get("reason"))
            return out

        if not transcript and u.intent == "UNKNOWN":
            out["stt_failed"] = True
            out["clarification_question"] = u.clarification_question or "Sizi eşidə bilmədim. Bir daha deyə bilərsiniz?"
            return out

        if u.intent in ("MAKE_CALL", "SEND_VOICE_MESSAGE"):
            alias = (u.contact_alias or "").strip()
            if alias:
                out["contact_alias"] = alias
                out["search_candidates"] = self.fallback._build_search_candidates(alias)
                if u.intent == "SEND_VOICE_MESSAGE" and u.title:
                    out["message_text"] = u.title.strip()[:300]
            else:
                out["clarification_question"] = u.clarification_question or ASK_WHO
                out["missing_slots"] = ["contact_alias"]

        elif u.intent == "CREATE_REMINDER":
            when = self._valid_future(u.scheduled_at, now)
            title = (u.title or "").strip()
            if when is None:
                # Gemini gave no/invalid time: trust our parser only if the user really said one
                parsed_dt, parsed_title, matched_time, matched_day = parse_azerbaijani_datetime_ex(transcript, now)
                title = title or parsed_title
                if matched_time or matched_day:
                    when = parsed_dt
            out["title"] = (title or "Xatırlatma")[:120]
            out["timezone"] = "Asia/Baku"
            if when is None:
                out["clarification_question"] = u.clarification_question or ASK_WHEN
                out["missing_slots"] = ["scheduled_at"]
            else:
                out["scheduled_at"] = when.isoformat()

        elif u.intent in ("ORDER_FOOD", "ORDER_PHARMACY", "ORDER_TAXI"):
            if u.food_item:
                out["food_item"] = u.food_item

        elif u.intent == "ANALYZE_MESSAGE":
            out["message_to_analyze"] = (u.message_to_analyze or transcript)[:2000]
            if u.security:
                out["llm_security"] = u.security.model_dump()

        elif u.intent == "GENERAL_QUESTION":
            if u.answer:
                out["answer"] = _cap(u.answer)

        elif u.intent == "EMERGENCY":
            out["emergency"] = True
            out["reason"] = transcript[:200]

        elif u.intent == "CREATE_MEDICATION":
            times = []
            for t in u.med_times:
                m = re.match(r"^\s*(\d{1,2})[:.](\d{2})\s*$", t or "")
                if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
                    times.append(f"{int(m.group(1)):02d}:{m.group(2)}")
            out["title"] = ((u.title or "").strip() or "Dərman")[:120]
            if times:
                out["med_times"] = sorted(set(times))
            else:
                out["clarification_question"] = u.clarification_question or "Hər gün saat neçədə xatırladım? Məsələn: “səhər 9-da və axşam 9-da”."
                out["missing_slots"] = ["med_times"]

        elif u.intent == "CHECKIN":
            out["mood"] = u.mood or "ok"
            if u.answer:
                out["answer"] = _cap(u.answer)

        elif u.intent == "WEATHER":
            out["weather_day"] = u.weather_day or "today"

        elif u.intent == "FIND_PLACE":
            out["place_type"] = u.place_type or "pharmacy"

        elif u.intent == "OPEN_SCREEN":
            out["screen"] = u.screen or "meds"

        elif u.intent == "LOG_HEALTH":
            if u.health_kind and u.health_value is not None:
                out["health_kind"] = u.health_kind
                out["health_value"] = float(u.health_value)
                if u.health_value2 is not None:
                    out["health_value2"] = float(u.health_value2)
            else:
                out["clarification_question"] = u.clarification_question or (
                    "Хорошо, какие показатели?" if u.language == "ru" else "Yaxşı, göstərici neçədir?")
                out["missing_slots"] = ["health_value"]

        elif u.intent == "UNKNOWN" and u.clarification_question:
            out["clarification_question"] = _cap(u.clarification_question)

        return out

    @staticmethod
    def _valid_future(value: Optional[str], now: datetime) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            return None
        dt = dt.astimezone(BAKU_TZ)
        if dt <= now - timedelta(minutes=1) or dt > now + timedelta(days=366):
            return None
        return dt


def _cap(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= MAX_ANSWER_CHARS:
        return text
    cut = text[:MAX_ANSWER_CHARS]
    return cut[: cut.rfind(" ")].rstrip(",;:") + "…"


@lru_cache
def get_gemini_adapter() -> GeminiLLMAdapter:
    logger.info("LLM engine: Gemini (%s) with rule-based fallback", settings.LLM_MODEL_NAME)
    return GeminiLLMAdapter()
