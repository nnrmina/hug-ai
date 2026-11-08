from app.agents.state import AgentState
from app.agents.tools.security_tools import analyze_message


def security_node(state: AgentState) -> AgentState:
    """Analyze suspicious message and extract risk indicators (MVP 03 - Digital Shield Agent)."""
    action_data = dict(state.get("action_data") or {})
    message_text = action_data.get("message_to_analyze") or state["user_message"]

    tool_result = analyze_message(message_text)
    merged_action = {**action_data, **tool_result}

    return {
        **state,
        "action_data": merged_action,
        "requires_confirmation": False,
        "confirmation_status": "not_required",
    }

