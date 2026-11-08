from typing import Dict, Any


def create_reminder(
    title: str,
    scheduled_at: str,
    timezone: str = "Asia/Baku",
) -> Dict[str, Any]:
    """Create a structured reminder action payload for the user (Section 9.5)."""
    return {
        "success": True,
        "action_type": "CREATE_REMINDER",
        "title": title,
        "scheduled_at": scheduled_at,
        "timezone": timezone,
    }

