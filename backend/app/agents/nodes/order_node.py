from app.agents.state import AgentState
from app.agents.tools.order_tools import prepare_order


def order_node(state: AgentState) -> AgentState:
    """Prepare a simulated Wolt food / pharmacy / taxi order preview for confirmation."""
    action_data = dict(state.get("action_data") or {})
    intent = state.get("intent") or "ORDER_FOOD"

    tool_result = prepare_order(intent, state["user_message"], action_data.get("food_item"))

    return {
        **state,
        "action_data": {**action_data, **tool_result},
        "requires_confirmation": True,
        "confirmation_status": "pending",
    }
