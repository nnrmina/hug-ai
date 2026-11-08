from app.agents.state import AgentState
from app.integrations.llm.ml_classifier import classify_with_ml
from app.integrations.llm.provider import get_llm_adapter
from app.utils.datetime_utils import parse_azerbaijani_datetime


def input_node(state: AgentState) -> AgentState:
    """Validate and normalize incoming user message."""
    cleaned_message = (state.get("user_message") or "").strip()
    return {
        **state,
        "user_message": cleaned_message,
    }


def _ml_fallback(message: str, adapter) -> dict | None:
    """Ask the optional hug-ml classifier when the rules could not decide."""
    ml = classify_with_ml(message)
    if not ml:
        return None

    intent = ml["intent"]
    parsed: dict = {"intent": intent, "confidence": ml["confidence"], "intent_source": "hug-ml"}
    if intent == "WOLT_ORDER":
        return {
            **parsed,
            "intent": "UNKNOWN",
            "blocked_action": "WOLT_ORDER",
            "requires_confirmation": False,
        }
    if intent == "MAKE_CALL":
        alias = adapter._extract_contact_alias(message)
        parsed.update(
            contact_alias=alias,
            search_candidates=adapter._build_search_candidates(alias),
            requires_confirmation=True,
        )
    elif intent == "CREATE_REMINDER":
        scheduled_at, title = parse_azerbaijani_datetime(message)
        parsed.update(
            title=title,
            scheduled_at=scheduled_at.isoformat(),
            timezone="Asia/Baku",
            requires_confirmation=True,
        )
    elif intent == "EMERGENCY_CALL":
        parsed.update(phone_number="103", requires_confirmation=True)
    else:
        parsed["requires_confirmation"] = False
    return parsed


def intent_node(state: AgentState) -> AgentState:
    """Detect user intent and extract initial structured fields using the LLM adapter."""
    adapter = get_llm_adapter()
    parsed = adapter.detect_intent(state["user_message"])

    if parsed.get("intent") == "UNKNOWN" and not parsed.get("blocked_action"):
        parsed = _ml_fallback(state["user_message"], adapter) or parsed

    intent = parsed.get("intent", "UNKNOWN")
    confidence = float(parsed.get("confidence", 0.0))
    requires_confirmation = bool(parsed.get("requires_confirmation", False))

    action_data = dict(state.get("action_data") or {})
    for key, value in parsed.items():
        if key not in ("intent", "confidence", "requires_confirmation"):
            action_data[key] = value

    return {
        **state,
        "intent": intent,
        "confidence": confidence,
        "action_data": action_data,
        "requires_confirmation": requires_confirmation,
    }
