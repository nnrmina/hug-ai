from app.agents.state import AgentState
from app.agents.tools.contact_tools import prepare_contact_lookup


def contact_node(state: AgentState) -> AgentState:
    """Prepare on-device contact lookup and call/message action (MVP 01 - Voice Contact Agent)."""
    action_data = dict(state.get("action_data") or {})
    alias = action_data.get("contact_alias") or "naməlum kontakt"
    intent = state.get("intent") or "MAKE_CALL"

    tool_result = prepare_contact_lookup(contact_alias=alias, operation=intent)
    merged_action = {**action_data, **tool_result}

    return {
        **state,
        "action_data": merged_action,
        "requires_confirmation": True,
        "confirmation_status": "pending",
    }

