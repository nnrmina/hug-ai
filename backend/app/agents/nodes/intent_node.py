from app.agents.state import AgentState
from app.integrations.llm.provider import get_llm_adapter


def input_node(state: AgentState) -> AgentState:
    """Validate and normalize incoming user message."""
    cleaned_message = (state.get("user_message") or "").strip()
    return {
        **state,
        "user_message": cleaned_message,
    }


def intent_node(state: AgentState) -> AgentState:
    """Detect user intent and extract initial structured fields using the LLM adapter."""
    adapter = get_llm_adapter()
    parsed = adapter.detect_intent(state["user_message"])

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

