from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.reminder import Reminder
from app.repositories.user_repository import UserRepository
from app.repositories.reminder_repository import ReminderRepository
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderService:
    """Business logic for creating, listing, updating, and deleting user reminders.

    user_id always comes from the authenticated token, never from the request body.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.reminder_repo = ReminderRepository(db)

    def create_reminder(self, data: ReminderCreate, user_id: str) -> Reminder:
        # Direct creation is itself an explicit user action (form + submit), so it does not go
        # through the voice-assistant confirmation step; it is bound to the token's user.
        reminder = self.reminder_repo.create(user_id=user_id, data=data)
        self.user_repo.log_agent_event(user_id=user_id, intent="CREATE_REMINDER", status="completed")
        return reminder

    def list_reminders(self, user_id: str) -> List[Reminder]:
        return self.reminder_repo.list_by_user(user_id)

    def get_reminder(self, reminder_id: str, user_id: str) -> Reminder:
        reminder = self.reminder_repo.get_for_user(reminder_id, user_id)
        # Another user's reminder is reported as "not found" so its existence is not leaked.
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Xatırlatma tapılmadı.",
            )
        return reminder

    def update_reminder(self, reminder_id: str, data: ReminderUpdate, user_id: str) -> Reminder:
        reminder = self.get_reminder(reminder_id, user_id)
        return self.reminder_repo.update(reminder, data)

    def delete_reminder(self, reminder_id: str, user_id: str) -> None:
        reminder = self.get_reminder(reminder_id, user_id)
        self.reminder_repo.delete(reminder)
