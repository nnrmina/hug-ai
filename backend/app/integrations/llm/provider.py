import re

from app.core.i18n import detect_lang
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional
from app.integrations.llm.base import BaseLLMAdapter
from app.utils.datetime_utils import parse_azerbaijani_datetime, parse_azerbaijani_datetime_ex

ASK_WHEN = "Nə vaxt xatırladım? Məsələn: “sabah saat 9-da”."
ASK_WHO = "Kimə zəng edim? Məsələn: “qızıma” və ya “Almaz xalaya”."
_CALL_VERB_ONLY = re.compile(r"(?i)^(?:zəng|zeng|yığ|yig|zvanok|nömrə|nomre|əlaqə)\b")

INTENTS = [
    "MAKE_CALL",
    "CREATE_REMINDER",
    "ANALYZE_MESSAGE",
    "SEND_VOICE_MESSAGE",
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

_NUM = r"(\d{1,3}(?:[.,]\d)?)"
HEALTH_PATTERNS = [
    ("bp", re.compile(r"t[əe]zyiq\w*\D{0,12}?(\d{2,3})\D{1,8}?(\d{2,3})")),
    ("sugar", re.compile(r"ş[əe]k[əe]r\w*\D{0,12}?" + _NUM)),
    ("pulse", re.compile(r"n[əe]bz\w*\D{0,12}?(\d{2,3})")),
    ("temp", re.compile(r"(?:qızdırma|qizdirma|temperatur|hərarət|hərarət)\w*\D{0,12}?" + _NUM)),
    ("weight", re.compile(r"(?:çəki|ceki)\w*\D{0,12}?" + _NUM)),
]
_STEP_SPLIT = re.compile(r"(?i)\s*,?\s+(?:və\s+)?(?:sonra|ardınca|daha sonra)\s+")
PLACE_WORDS = {"pharmacy": ["aptek", "aptekə", "apteka"], "hospital": ["xəstəxana", "xestexana", "poliklinika", "klinika"]}
NEAR_WORDS = ["yaxın", "yaxin", "harada", "hardadır", "hardadir", "harda", "haradadır", "yaxınlıq"]
WEATHER_WORDS = ["hava ", "hava?", "havanı", "havalar", "yağış", "yagis", "qar yağ", "neçə dərəcə", "temperatur necə"]
OPEN_VERBS = ["göstər", "goster", "aç", "ac ", "bax", "açın", "göstərin"]
SCREEN_WORDS = [
    ("meds", ["dərmanlarım", "dermanlarim", "dərmanları", "dərman siyahı"]),
    ("reminders", ["təqvim", "teqvim", "xatırlatmalar", "xatirlatmalar"]),
    ("family", ["ailəm", "ailəmi", "aile", "kontakt"]),
    ("settings", ["tənzimləmə", "tenzimleme", "parametr", "ayarlar"]),
]
HEALTH_QUERY_WORDS = ["son təzyiq", "təzyiqlərim", "göstəricilərim", "ölçülərim", "son ölçmə"]


def parse_health(lower: str) -> Optional[Dict[str, Any]]:
    for kind, rx in HEALTH_PATTERNS:
        m = rx.search(lower)
        if not m:
            continue
        vals = [float(g.replace(",", ".")) for g in m.groups() if g]
        out = {"health_kind": kind, "health_value": vals[0]}
        if kind == "bp":
            if not (60 <= vals[0] <= 260 and 30 <= vals[1] <= 160):
                continue
            out["health_value2"] = vals[1]
        return out
    return None

EMERGENCY_KEYWORDS = [
    "kömək edin", "kömək et", "komek et", "imdad", "yıxıldım", "yixildim", "təcili yardım",
    "tecili yardim", "ürəyim ağrıyır", "ureyim agriyir", "nəfəs ala bilmirəm", "nefes ala bilmirem",
    "özümü çox pis", "ozumu cox pis", "huşumu itir",
]
TAKEN_KEYWORDS = ["dərmanımı içdim", "dərmanlarımı içdim", "dərmanları içdim", "dermanlarimi icdim", "derman icdim", "dərmanı içdim", "həbi içdim", "həbimi içdim", "içdim dərman"]
MOOD_KEYWORDS = {
    "bad": ["özümü pis hiss", "ozumu pis hiss", "halım yoxdur", "halim yoxdur", "xəstəyəm", "xesteyem"],
    "good": ["özümü yaxşı hiss", "ozumu yaxsi hiss", "yaxşıyam", "yaxsiyam", "əlayam", "kefim yaxşıdır"],
    "ok": ["eləbelə", "elə də", "pis deyiləm", "normalam"],
}
_DAYPART = {"səhər": 0, "seher": 0, "günorta": 12, "gunorta": 12, "axşam": 12, "axsam": 12, "gecə": 12, "gece": 12}


def _daily_times(lower: str) -> List[str]:
    """'səhər 9-da və axşam 9-da' -> ['09:00', '21:00'] (rule-based, best effort)."""
    out = []
    for m in re.finditer(r"(səhər|seher|günorta|gunorta|axşam|axsam|gecə|gece)?\s*(?:saat\s*)?(\d{1,2})(?::(\d{2}))?", lower):
        hour = int(m.group(2))
        if hour > 23:
            continue
        part = m.group(1)
        if part and _DAYPART.get(part) == 12 and hour < 12:
            hour += 12
        out.append(f"{hour:02d}:{m.group(3) or '00'}")
    return sorted(set(out))


def _med_title(text: str) -> str:
    m = re.search(r"(?i)([\wəığöüşçƏIĞÖÜŞÇ]+)\s+(dərman|derman|həb)", text)
    if m and m.group(1).lower() not in ("mənim", "menim", "hər", "her", "gün", "və"):
        return f"{m.group(1).capitalize()} dərmanı"
    return "Dərman"


TAXI_KEYWORDS = ["taksi", "taxi", "maşın çağır", "masin cagir"]
PHARMACY_KEYWORDS = [
    "aptek",
    "kardiomaqnil",
    "dərman sifariş",
    "derman sifariş",
    "derman sifaris",
    "dərman al",
    "dərman gətir",
]
FOOD_KEYWORDS = [
    "wolt",
    "tantuni",
    "chef",
    "dönər",
    "doner",
    "bozbaş",
    "bozbas",
    "yemək",
    "yemek",
    "ərzaq sifariş",
]

# Azerbaijani kinship/contact relationship stems -> canonical alias
CONTACT_ALIAS_MAP = {
    "qızım": "qızım",
    "qizim": "qızım",
    "qızıma": "qızım",
    "qizima": "qızım",
    "oğlum": "oğlum",
    "oglum": "oğlum",
    "oğluma": "oğlum",
    "ogluma": "oğlum",
    "anam": "anam",
    "anama": "anam",
    "ana": "anam",
    "atam": "atam",
    "atama": "atam",
    "ata": "atam",
    "bacım": "bacım",
    "bacima": "bacım",
    "bacıma": "bacım",
    "qardaşım": "qardaşım",
    "qardaşıma": "qardaşım",
    "qardasima": "qardaşım",
    "nəvəm": "nəvəm",
    "nəvəmə": "nəvəm",
    "həkim": "həkim",
    "həkimə": "həkim",
    "hekim": "həkim",
    "hekime": "həkim",
}

# Common Azerbaijani first names ending naturally in -a / -ə so we don't strip their root vowel
NAMES_ENDING_IN_VOWEL = {
    "leyla",
    "aylə",
    "aybəniz",
    "fatimə",
    "xədicə",
    "zəhra",
    "səbinə",
    "ülviyyə",
    "nərminə",
    "narmina",
    "günel",
    "sevda",
    "vəfa",
    "rəna",
    "dilarə",
    "samirə",
    "ilhamə",
    "əli",
    "veli",
    "vəli",
    "isa",
    "musa",
    "mustafa",
}


def strip_azerbaijani_dative(raw_name: str) -> str:
    """Convert an Azerbaijani dative-inflected name into its nominative base form.
    Examples:
      'Almaza' -> 'Almaz'
      'Kamrana' -> 'Kamran'
      'Leylaya' -> 'Leyla'
      'Fatiməyə' -> 'Fatimə'
      'Əliyə' -> 'Əli'
      'Almaz xalaya' -> 'Almaz xala'
      'Ayselə' -> 'Aysel'
    """
    cleaned = raw_name.strip(" ,.!?:;\"'")
    if not cleaned:
        return cleaned

    words = cleaned.split()
    last = words[-1]
    last_lower = last.lower()

    if last_lower in CONTACT_ALIAS_MAP:
        words[-1] = CONTACT_ALIAS_MAP[last_lower]
        return " ".join(words)

    # Honorifics in dative case
    honorific_map = {
        "xalaya": "xala",
        "xanuma": "xanım",
        "xanıma": "xanım",
        "bəyə": "bəy",
        "dayıya": "dayı",
        "əmiyə": "əmi",
        "bibiyə": "bibi",
        "nənəyə": "nənə",
        "babaya": "baba",
    }
    if last_lower in honorific_map:
        words[-1] = honorific_map[last_lower]
        return " ".join(words)

    # Suffix -ya / -yə (attached to vowel-ending stems like Leyla-ya, Fatimə-yə, Əli-yə)
    if len(last) > 4 and last_lower.endswith(("ya", "yə")):
        stem = last[:-2]
        words[-1] = stem[0].upper() + stem[1:]
        return " ".join(words)

    # Suffix -na / -nə (for 3rd-person possessive dative, e.g. xalasına -> xalası)
    if len(last) > 5 and last_lower.endswith(("sına", "sinə", "suna", "sünə")):
        stem = last[:-2]
        words[-1] = stem
        return " ".join(words)

    # Suffix -a / -ə (attached to consonant-ending stems like Almaz-a, Kamran-a, Aysel-ə, Orxan-a)
    if len(last) > 3 and last_lower.endswith(("a", "ə")):
        if last_lower not in NAMES_ENDING_IN_VOWEL:
            stem = last[:-1]
            words[-1] = stem[0].upper() + stem[1:]
            return " ".join(words)

    words[-1] = last[0].upper() + last[1:] if last else last
    return " ".join(words)


class AzerbaijaniSmartLLMAdapter(BaseLLMAdapter):
    """Deterministic + LLM-compatible Azerbaijani language adapter for YAXIN AI."""

    def detect_intent(self, message: str) -> Dict[str, Any]:
        text = message.strip()
        lower = text.lower()

        # 0. Emergencies always win
        if any(kw in lower for kw in EMERGENCY_KEYWORDS):
            return {"intent": "EMERGENCY", "confidence": 0.97, "emergency": True,
                    "reason": text[:200], "requires_confirmation": False}

        # 0b. "I took my medicine" / how I feel today
        if any(kw in lower for kw in TAKEN_KEYWORDS):
            return {"intent": "MEDICATION_TAKEN", "confidence": 0.9, "requires_confirmation": False}
        for mood, kws in MOOD_KEYWORDS.items():
            if any(kw in lower for kw in kws):
                return {"intent": "CHECKIN", "confidence": 0.85, "mood": mood, "requires_confirmation": False}

        # 0c. Repeating medicine schedule ("hər gün səhər 9-da və axşam 9-da ...")
        if any(kw in lower for kw in ("hər gün", "her gun", "gündə", "gunde", "hər səhər", "hər axşam")) and \
                any(kw in lower for kw in ("dərman", "derman", "həb", "heb")):
            times = _daily_times(lower)
            parsed = {"intent": "CREATE_MEDICATION", "confidence": 0.88, "title": _med_title(text),
                      "requires_confirmation": True}
            if times:
                parsed["med_times"] = times
            else:
                parsed["clarification_question"] = "Hər gün saat neçədə xatırladım? Məsələn: “səhər 9-da və axşam 9-da”."
                parsed["missing_slots"] = ["med_times"]
            return parsed

        # 0c2. "Dərmanlarımı göstər", "Təqvimi aç" -> open that screen
        if any(v in lower + " " for v in OPEN_VERBS):
            for screen, words in SCREEN_WORDS:
                if any(w in lower for w in words):
                    return {"intent": "OPEN_SCREEN", "confidence": 0.9, "screen": screen,
                            "requires_confirmation": False}

        # 0d. Health measurements, weather, nearest places
        if any(kw in lower for kw in HEALTH_QUERY_WORDS):
            return {"intent": "HEALTH_QUERY", "confidence": 0.85, "requires_confirmation": False}
        health = parse_health(lower)
        if health:
            return {"intent": "LOG_HEALTH", "confidence": 0.88, "requires_confirmation": False, **health}
        if any(kw in lower + " " for kw in WEATHER_WORDS):
            day = "tomorrow" if ("sabah" in lower and "sabahınız" not in lower) else "today"
            return {"intent": "WEATHER", "confidence": 0.86, "weather_day": day, "requires_confirmation": False}
        if any(kw in lower for kw in NEAR_WORDS):
            for place, words in PLACE_WORDS.items():
                if any(w in lower for w in words):
                    return {"intent": "FIND_PLACE", "confidence": 0.88, "place_type": place,
                            "requires_confirmation": False}

        # 1. Out-of-scope high-risk actions (Bank transfer)
        if any(
            kw in lower
            for kw in ["pul köçür", "pul göndər", "karta pul", "hesaba pul", "bank köçürmə"]
        ):
            return {
                "intent": "UNKNOWN",
                "confidence": 0.95,
                "blocked_action": "BANK_TRANSFER",
                "requires_confirmation": False,
                "reason": "Real bank əməliyyatları və pul köçürmələri MVP-də dəstəklənmir.",
            }

        # 2. Reminder intent
        reminder_keywords = [
            "xatırlat",
            "xatirlat",
            "xatırlatma",
            "yadıma sal",
            "yadima sal",
            "məni oyat",
            "meni oyat",
            "oyat",
            "zəngli saat",
            "bildiriş",
        ]
        if any(kw in lower for kw in reminder_keywords):
            scheduled_at, title = parse_azerbaijani_datetime(text)
            return {
                "intent": "CREATE_REMINDER",
                "confidence": 0.94,
                "title": title,
                "scheduled_at": scheduled_at.isoformat(),
                "timezone": "Asia/Baku",
                "requires_confirmation": True,
            }

        # 3. Security / Scam Analysis intent
        security_keywords = [
            "təhlükəlidir",
            "tehlukelidir",
            "təhlükəli",
            "şübhəli",
            "subheli",
            "fırıldaq",
            "dələduz",
            "sms-i yoxla",
            "mesajı yoxla",
            "mesaji yoxla",
            "bloklanıb",
            "kart məlumat",
            "şifrə",
            "linkə daxil",
            "uduş",
            "priz qazandınız",
        ]
        if any(kw in lower for kw in security_keywords):
            return {
                "intent": "ANALYZE_MESSAGE",
                "confidence": 0.93,
                "message_to_analyze": text,
                "requires_confirmation": False,
            }

        # 4. Simulated Wolt orders (taxi / pharmacy / food) - checked after reminders so that
        #    "dərmanımı xatırlat" stays a reminder, and taxi/pharmacy before the generic "wolt".
        if any(kw in lower for kw in TAXI_KEYWORDS):
            return {"intent": "ORDER_TAXI", "confidence": 0.93, "requires_confirmation": True}
        if any(kw in lower for kw in PHARMACY_KEYWORDS):
            return {"intent": "ORDER_PHARMACY", "confidence": 0.92, "requires_confirmation": True}
        if any(kw in lower for kw in FOOD_KEYWORDS):
            return {"intent": "ORDER_FOOD", "confidence": 0.92, "requires_confirmation": True}

        # 5. Voice Message intent
        voice_msg_keywords = [
            "səs göndər",
            "ses gonder",
            "səsli mesaj",
            "mesaj göndər",
            "mesaj yaz",
        ]
        if any(kw in lower for kw in voice_msg_keywords):
            alias = self._extract_contact_alias(text)
            return {
                "intent": "SEND_VOICE_MESSAGE",
                "confidence": 0.92,
                "contact_alias": alias,
                "search_candidates": self._build_search_candidates(alias),
                "requires_confirmation": True,
            }

        # 6. Make Call intent (e.g., "Almaza zəng et", "Qızıma zəng vur", "Almazı yığ")
        call_keywords = [
            "zəng et",
            "zeng et",
            "zəng elə",
            "zeng ele",
            "zəng vur",
            "zeng vur",
            "zəng",
            "zeng",
            "yığ",
            "yig",
            "əlaqə saxla",
            "zvanok",
            "노mrəsini yığ",
            "nömrəsini yığ",
        ]
        if any(kw in lower for kw in call_keywords):
            alias = self._extract_contact_alias(text)
            return {
                "intent": "MAKE_CALL",
                "confidence": 0.97,
                "contact_alias": alias,
                "search_candidates": self._build_search_candidates(alias),
                "requires_confirmation": True,
            }

        # 7. General Questions
        general_keywords = [
            "hava necə",
            "sən kimsən",
            "nə edə bilirsən",
            "saat neçədir",
            "salam",
            "necəsən",
            "kömək et",
        ]
        if any(kw in lower for kw in general_keywords) or text.endswith("?"):
            return {
                "intent": "GENERAL_QUESTION",
                "confidence": 0.85,
                "requires_confirmation": False,
            }

        return {
            "intent": "UNKNOWN",
            "confidence": 0.40,
            "requires_confirmation": False,
        }

    def understand(
        self,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Rule-based turn understanding with simple slot-filling follow-ups."""
        meta = {"engine": "rule_based"}
        if not text or not text.strip():
            # Without a server-side speech model we cannot read raw audio.
            return {
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "requires_confirmation": False,
                "transcript": "",
                "stt_failed": bool(audio),
                **meta,
            }
        text = text.strip()
        meta["transcript"] = text
        meta["lang"] = detect_lang(text)
        pending = (history[-1].get("pending") if history else None) or {}

        # Multi-step: "tantuni sifariş et, sonra qızıma de ki ..." -> first step now, rest queued
        parts = _STEP_SPLIT.split(text, maxsplit=1)
        if len(parts) == 2 and len(parts[0].split()) >= 2 and len(parts[1].split()) >= 2:
            first = self.understand(text=parts[0], history=history, now=now)
            if first.get("intent") not in ("UNKNOWN", "EMERGENCY"):
                first["next_step"] = parts[1].strip()[:300]
                first["transcript"] = text
                return first

        if meta["lang"] == "ru":
            return {"intent": "UNKNOWN", "confidence": 0.3, "requires_confirmation": False,
                    "clarification_question": "Извините, сейчас я понимаю по-русски только простые фразы. "
                                              "Попробуйте ещё раз или скажите по-азербайджански.",
                    **meta}

        # Follow-up: the previous turn asked "Nə vaxt?" for a reminder
        if pending.get("intent") == "CREATE_REMINDER":
            scheduled, _, matched_time, matched_day = parse_azerbaijani_datetime_ex(text, now)
            if matched_time or matched_day:
                return {
                    "intent": "CREATE_REMINDER",
                    "confidence": 0.9,
                    "title": pending.get("title") or "Xatırlatma",
                    "scheduled_at": scheduled.isoformat(),
                    "timezone": "Asia/Baku",
                    "requires_confirmation": True,
                    **meta,
                }

        # Follow-up: the previous turn asked "Hər gün saat neçədə?" for a medicine
        if pending.get("intent") == "CREATE_MEDICATION":
            times = _daily_times(text.lower())
            if times:
                return {"intent": "CREATE_MEDICATION", "confidence": 0.88, "title": pending.get("title") or "Dərman",
                        "med_times": times, "requires_confirmation": True, **meta}

        parsed = self.detect_intent(text)

        # Follow-up: the previous turn asked "Kimə?" and the user just said a name
        if parsed["intent"] == "UNKNOWN" and not parsed.get("blocked_action") and pending.get("intent") in (
            "MAKE_CALL",
            "SEND_VOICE_MESSAGE",
        ):
            alias = self._extract_contact_alias(text)
            parsed = {
                "intent": pending["intent"],
                "confidence": 0.85,
                "contact_alias": alias,
                "search_candidates": self._build_search_candidates(alias),
                "requires_confirmation": True,
            }

        if parsed["intent"] == "CREATE_REMINDER":
            _, _, matched_time, matched_day = parse_azerbaijani_datetime_ex(text, now)
            if not matched_time and not matched_day:
                parsed["clarification_question"] = ASK_WHEN
                parsed["missing_slots"] = ["scheduled_at"]

        if parsed["intent"] in ("MAKE_CALL", "SEND_VOICE_MESSAGE"):
            alias = (parsed.get("contact_alias") or "").strip()
            if not alias or alias == "naməlum kontakt" or _CALL_VERB_ONLY.match(alias):
                parsed["contact_alias"] = None
                parsed["clarification_question"] = ASK_WHO
                parsed["missing_slots"] = ["contact_alias"]

        parsed.update(meta)
        return parsed

    def _extract_contact_alias(self, text: str) -> str:
        """Extract kinship alias or proper contact name (e.g., 'Almaza zəng et' -> 'Almaz')."""
        cleaned = re.sub(
            r"(?i)^(?:salam\s+)?(?:yaxın|yaxin)[\s,!.]*",
            "",
            text.strip(),
        )
        cleaned = re.sub(
            r"(?i)^(?:zəhmət\s+olmasa|zehmet\s+olmasa|xahiş\s+edirəm)[\s,]*",
            "",
            cleaned,
        ).strip()

        lower = cleaned.lower()
        for token, canonical in CONTACT_ALIAS_MAP.items():
            if re.search(rf"\b{re.escape(token)}\b", lower):
                return canonical

        # Extract target name before action verbs ("zəng", "zeng", "səs", "mesaj", "yığ", "nömrəsini")
        match = re.search(
            r"(?i)^(.+?)\s+(?:üçün\s+)?(?:zəng|zeng|səs|ses|mesaj|yığ|yig|nömrə|nomre|əlaqə)",
            cleaned,
        )
        if match:
            raw_target = match.group(1).strip(" ,.-?!")
            return strip_azerbaijani_dative(raw_target)

        # Or if user said "Zəng et Almaza" (verb first, name second)
        match_after = re.search(
            r"(?i)(?:zəng\s+et|zeng\s+et|zəng\s+vur|zeng\s+vur|zəng\s+elə|yığ)\s+(.+)$",
            cleaned,
        )
        if match_after:
            raw_target = match_after.group(1).strip(" ,.-?!")
            return strip_azerbaijani_dative(raw_target)

        return strip_azerbaijani_dative(cleaned) or "naməlum kontakt"

    @staticmethod
    def _build_search_candidates(alias: str) -> List[str]:
        """Generate lowercase search stems so the Android contact agent matches variations."""
        base = alias.strip().lower()
        candidates = [base]
        if len(base) > 3:
            candidates.append(base[:-1])
        return list(dict.fromkeys(candidates))

    def analyze_security_text(self, message: str) -> Dict[str, Any]:
        """Hybrid rule-based + linguistic scam analysis for Azerbaijani/Russian/English SMS."""
        lower = message.lower()
        indicators: List[str] = []
        score = 10

        if any(
            w in lower
            for w in ["təcili", "tecili", "dərhal", "bloklanıb", "bloklanacaq", "24 saat", "son xəbərdarlıq"]
        ):
            indicators.append("urgency")
            score += 25

        if any(
            w in lower
            for w in [
                "kart məlumat",
                "cvv",
                "pin",
                "şifrə",
                "otp",
                "kod",
                "nömrəni təsdiqlə",
                "hesab məlumat",
            ]
        ):
            indicators.append("credential_request")
            score += 35

        if re.search(r"(https?://\S+|www\.\S+|bit\.ly/\S+|tinyurl\.\S+|\b[a-z0-9-]+\.(xyz|top|click|info|ru)/)", lower) or "linkə daxil" in lower or "keçidə daxil" in lower:
            indicators.append("suspicious_link")
            score += 25

        if any(
            w in lower
            for w in ["bank", "kapital", "abb", "pasha", "leobank", "unibank", "poçt", "azərpoçt"]
        ) and len(indicators) > 0:
            indicators.append("bank_or_institution_impersonation")
            score += 15

        if any(
            w in lower
            for w in ["uduş", "qalib", "mükafat", "lotereya", "pul qazandınız", "hədiyyə"]
        ):
            indicators.append("prize_scam")
            score += 30

        score = min(98, score) if indicators else 8

        if score >= 60:
            risk_level = "high"
            explanation = (
                "Bu mesajda yüksək dələduzluq (fırıldaqçılıq) əlamətləri aşkar edildi: "
                + ", ".join(self._translate_indicators(indicators))
                + ". Rəsmi qurumlar və banklar SMS vasitəsilə şifrə və ya kart məlumatı istəmir."
            )
            recommendation = (
                "Heç bir linkə (keçidə) daxil olmayın, şifrə və ya kart məlumatlarınızı paylaşmayın "
                "və şübhəniz varsa rəsmi bank nömrəsinə birbaşa özünüz zəng edin."
            )
        elif score >= 30:
            risk_level = "medium"
            explanation = (
                "Bu mesajda bəzi şübhəli əlamətlər var: "
                + ", ".join(self._translate_indicators(indicators))
                + ". Ehtiyatlı olmağınız tövsiyə olunur."
            )
            recommendation = (
                "Göndərənin kimliyini dəqiqləşdirmədən şəxsi məlumat göndərməyin və naməlum keçidləri açmayın."
            )
        else:
            risk_level = "low"
            explanation = (
                "Mesajda açıq fırıldaqçılıq və ya fişinq əlaməti aşkar edilmədi. "
                "Bununla belə, şəxsi məlumatlarınızı paylaşarkən həmişə diqqətli olun."
            )
            recommendation = "Mesaj təhlükəsiz görünür, lakin şifrə və kart məlumatlarınızı heç vaxt SMS-lə göndərməyin."

        return {
            "risk_level": risk_level,
            "risk_score": score,
            "indicators": indicators,
            "explanation": explanation,
            "recommendation": recommendation,
        }

    @staticmethod
    def _translate_indicators(indicators: List[str]) -> List[str]:
        mapping = {
            "urgency": "təcili hərəkət və qorxutma tələbi",
            "credential_request": "kart/şifrə məlumatlarının istənilməsi",
            "suspicious_link": "şübhəli xarici keçid (link)",
            "bank_or_institution_impersonation": "bank və ya rəsmi qurum adından istifadə",
            "prize_scam": "saxta uduş/mükafat vədi",
        }
        return [mapping.get(ind, ind) for ind in indicators]


@lru_cache
def get_rule_adapter() -> AzerbaijaniSmartLLMAdapter:
    return AzerbaijaniSmartLLMAdapter()


def get_llm_adapter() -> BaseLLMAdapter:
    """Return the configured adapter: Gemini when a key is set (LLM_PROVIDER=auto|gemini),
    otherwise the deterministic Azerbaijani rule-based parser."""
    from app.core.config import settings

    provider = (settings.LLM_PROVIDER or "auto").lower()
    if provider in ("auto", "gemini") and settings.gemini_key:
        from app.integrations.llm.gemini import get_gemini_adapter

        return get_gemini_adapter()
    return get_rule_adapter()
