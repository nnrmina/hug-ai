from datetime import datetime
from typing import Dict, Any


class LocalNotificationFormatter:
    """Formats local notification payloads for Flutter Local Notifications on Android/iOS."""

    @staticmethod
    def build_reminder_notification(
        reminder_id: str,
        title: str,
        scheduled_at: datetime,
        timezone: str = "Asia/Baku",
    ) -> Dict[str, Any]:
        return {
            "notification_id": reminder_id,
            "channel_id": "yaxin_reminders_channel",
            "channel_name": "YAXIN AI Xatırlatmalar",
            "title": "YAXIN AI Xatırlatma",
            "body": title,
            "scheduled_at": scheduled_at.isoformat(),
            "timezone": timezone,
            "require_interaction": True,
        }

