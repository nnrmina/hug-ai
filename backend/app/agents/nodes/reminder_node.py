from app.agents.state import AgentState
from app.agents.tools.reminder_tools import create_reminder
from app.utils.datetime_utils import parse_azerbaijani_datetime


def reminder_node(state: AgentState) -> AgentState:
    """Extract reminder parameters and prepare reminder creation (MVP 02 - Smart Reminder Agent)."""
    action_data = dict(state.get("action_data") or {})
    title = action_data.get("title")
    scheduled_at = action_data.get("scheduled_at")
    timezone_str = action_data.get("timezone", "Asia/Baku")

    if not title or not scheduled_at:
        dt, extracted_title = parse_azerbaijani_datetime(state["user_message"])
        title = title or extracted_title
        scheduled_at = scheduled_at or dt.isoformat()

    tool_result = create_reminder(
        title=title,
        scheduled_at=scheduled_at,
        timezone=timezone_str,
    )
    merged_action = {**action_data, **tool_result}

    return {
        **state,
        "action_data": merged_action,
        "requires_confirmation": True,
        "confirmation_status": "pending",
    }

