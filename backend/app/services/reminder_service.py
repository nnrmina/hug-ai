from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.reminder import Reminder
from app.repositories.user_repository import UserRepository
from app.repositories.reminder_repository import ReminderRepository
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderService:
    """Business logic for creating, listing, updating, and deleting user reminders."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.reminder_repo = ReminderRepository(db)

    def create_reminder(self, data: ReminderCreate) -> Reminder:
        user = self.user_repo.get_or_create_default_user(data.user_id)
        reminder = self.reminder_repo.create(user_id=user.id, data=data)
        self.user_repo.log_agent_event(
            user_id=user.id,
            intent="CREATE_REMINDER",
            status="completed",
        )
        return reminder

    def list_reminders(self, user_id: str | None = None) -> List[Reminder]:
        user = self.user_repo.get_or_create_default_user(user_id)
        return self.reminder_repo.list_by_user(user.id)

    def get_reminder(self, reminder_id: str) -> Reminder:
        reminder = self.reminder_repo.get_by_id(reminder_id)
        if not reminder:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Xatırlatma tapılmadı.",
            )
        return reminder

    def _owned(self, reminder_id: str, owner_id: str | None) -> Reminder:
        reminder = self.get_reminder(reminder_id)
        if owner_id is not None and reminder.user_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Xatırlatma tapılmadı.")
        return reminder

    def update_reminder(self, reminder_id: str, data: ReminderUpdate, owner_id: str | None = None) -> Reminder:
        reminder = self._owned(reminder_id, owner_id)
        return self.reminder_repo.update(reminder, data)

    def delete_reminder(self, reminder_id: str, owner_id: str | None = None) -> None:
        reminder = self._owned(reminder_id, owner_id)
        self.reminder_repo.delete(reminder)

