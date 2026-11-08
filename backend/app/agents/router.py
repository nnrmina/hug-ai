from app.agents.state import AgentState
from app.agents.tools.order_tools import ORDER_INTENTS


def route_by_intent(state: AgentState) -> str:
    """Route workflow execution to the appropriate specialized agent node based on detected intent."""
    intent = state.get("intent") or "UNKNOWN"
    action_data = state.get("action_data") or {}

    if action_data.get("blocked_action") or state.get("status") == "needs_clarification":
        return "validation_node"

    if intent in ("MAKE_CALL", "SEND_VOICE_MESSAGE"):
        return "contact_node"
    if intent == "CREATE_REMINDER":
        return "reminder_node"
    if intent == "ANALYZE_MESSAGE":
        return "security_node"
    if intent in ORDER_INTENTS:
        return "order_node"

    return "validation_node"

