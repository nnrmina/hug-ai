from app.agents.state import AgentState


def route_by_intent(state: AgentState) -> str:
    """Route workflow execution to the appropriate specialized agent node based on detected intent."""
    intent = state.get("intent") or "UNKNOWN"
    action_data = state.get("action_data") or {}

    if action_data.get("blocked_action"):
        return "validation_node"

    if intent in ("MAKE_CALL", "SEND_VOICE_MESSAGE"):
        return "contact_node"
    if intent == "CREATE_REMINDER":
        return "reminder_node"
    if intent == "ANALYZE_MESSAGE":
        return "security_node"

    return "validation_node"

