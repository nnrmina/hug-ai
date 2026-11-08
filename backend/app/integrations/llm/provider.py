import re
from typing import Any, Dict, List
from app.integrations.llm.base import BaseLLMAdapter
from app.utils.datetime_utils import parse_azerbaijani_datetime
from app.utils.text_utils import az_lower

INTENTS = [
    "MAKE_CALL",
    "CREATE_REMINDER",
    "ANALYZE_MESSAGE",
    "SEND_VOICE_MESSAGE",
    "EMERGENCY_CALL",
    "GENERAL_QUESTION",
    "UNKNOWN",
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
    "nənəm": "nənəm",
    "nenem": "nənəm",
    "nənəmə": "nənəm",
    "neneme": "nənəm",
    "nənə": "nənəm",
    "nene": "nənəm",
    "nənəyə": "nənəm",
    "neneye": "nənəm",
    "nənəmin": "nənəm",
    "nenemin": "nənəm",
    "babam": "babam",
    "babama": "babam",
    "baba": "babam",
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
    last_lower = az_lower(last)

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
        lower = az_lower(text)

        # 0. Emergencies come first: never let a medical emergency fall through to other intents.
        emergency = self._detect_emergency(lower)
        if emergency:
            return emergency

        # 1. Out-of-scope high-risk actions (Bank transfer / Wolt order)
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

        if any(kw in lower for kw in ["wolt", "yemək sifariş", "ərzaq sifariş"]):
            return {
                "intent": "UNKNOWN",
                "confidence": 0.95,
                "blocked_action": "WOLT_ORDER",
                "simulated": True,
                "requires_confirmation": False,
                "reason": "Real Wolt sifarişi MVP-də aktiv deyil (yalnız simulyasiya rejimindədir).",
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

        # 4. Voice Message intent
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

        # 5. Make Call intent (e.g., "Almaza zəng et", "Qızıma zəng vur", "Almazı yığ")
        # Whole-word patterns: "zəng" must not match "zəngin", "zəngli saat"; "yığ" must not match "yığıncaq".
        call_patterns = [
            r"\bz[əe]ng\b",
            r"\bzvanok\b",
            r"\by[ıi][ğg]\b",
            r"\bn[öo]mr[əe]sini\s+y[ıi][ğg]",
            r"\b[əe]laq[əe]\s+saxla",
        ]
        if any(re.search(p, lower) for p in call_patterns):
            alias = self._extract_contact_alias(text)
            return {
                "intent": "MAKE_CALL",
                "confidence": 0.97,
                "contact_alias": alias,
                "search_candidates": self._build_search_candidates(alias),
                "requires_confirmation": True,
            }

        # 6. General Questions
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

    @staticmethod
    def _detect_emergency(lower: str) -> Dict[str, Any] | None:
        """Detect urgent medical/safety situations (Azerbaijan: 103 ambulance, 112 general)."""
        # Information questions about emergency numbers are not emergencies.
        if re.search(r"\b(neçədir|necedir|nədir|nedir|hansıdır|hansidir)\b", lower):
            return None
        symptoms = [
            "ürəyim ağrıyır", "ureyim agriyir", "ürəyim sancır",
            "nəfəs ala bilmirəm", "nefes ala bilmirem", "nəfəsim çatmır",
            "yıxıldım", "yixildim", "qalxa bilmirəm",
            "huşumu itirirəm", "insult",
            "imdad", "kömək edin",
        ]
        call_for_help = re.search(
            r"(təcili|tecili)\s+yard[ıi]m\w*\s*(çağır|cagir|zəng|zeng|lazım|lazim)"
            r"|\b(103|112)\b[-\w]*\s*(zəng|zeng|yığ|yig|çağır|cagir)"
            r"|(zəng|zeng)\s+(et|vur)\s+(103|112)\b"
            r"|\b(təcili|tecili)\s+yard[ıi]m\s*!?$",
            lower,
        )
        if not (call_for_help or any(s in lower for s in symptoms)):
            return None
        number = "112" if re.search(r"\b112\b|polis|yanğın|yangin", lower) else "103"
        return {
            "intent": "EMERGENCY_CALL",
            "confidence": 0.9,
            "phone_number": number,
            "requires_confirmation": True,
        }

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

        lower = az_lower(cleaned)
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
        base = az_lower(alias.strip())
        candidates = [base]
        if len(base) > 3:
            candidates.append(base[:-1])
        return list(dict.fromkeys(candidates))

    def analyze_security_text(self, message: str) -> Dict[str, Any]:
        """Hybrid rule-based + linguistic scam analysis for Azerbaijani/Russian/English SMS."""
        lower = az_lower(message)
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
                "şifrə",
                "nömrəni təsdiqlə",
                "hesab məlumat",
            ]
        ) or re.search(r"\b(pin|otp|kod\w*)\b", lower):
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


def get_llm_adapter() -> BaseLLMAdapter:
    """Return configured LLM adapter instance."""
    return AzerbaijaniSmartLLMAdapter()
