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
    parsed = state.get("llm_parsed") or get_llm_adapter().detect_intent(state["user_message"])

    intent = parsed.get("intent", "UNKNOWN")
    confidence = float(parsed.get("confidence", 0.0))
    requires_confirmation = bool(parsed.get("requires_confirmation", False))

    action_data = dict(state.get("action_data") or {})
    for key, value in parsed.items():
        if key not in ("intent", "confidence", "requires_confirmation"):
            action_data[key] = value

    new_state = {
        **state,
        "intent": intent,
        "confidence": confidence,
        "action_data": action_data,
        "requires_confirmation": requires_confirmation,
    }
    # A required slot is missing (e.g. "Xatırlat" with no time): ask instead of acting
    if action_data.get("clarification_question") and not action_data.get("blocked_action"):
        new_state["requires_confirmation"] = False
        new_state["status"] = "needs_clarification"
    return new_state

