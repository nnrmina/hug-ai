from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.reminder import Reminder
from app.schemas.reminder import ReminderCreate, ReminderUpdate


class ReminderRepository:
    """Repository for Reminder CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, user_id: str, data: ReminderCreate) -> Reminder:
        reminder = Reminder(
            user_id=user_id,
            title=data.title,
            description=data.description,
            scheduled_at=data.scheduled_at,
            timezone=data.timezone or "Asia/Baku",
            status="pending",
        )
        self.db.add(reminder)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def list_by_user(self, user_id: str) -> List[Reminder]:
        return (
            self.db.query(Reminder)
            .filter(Reminder.user_id == user_id)
            .order_by(Reminder.scheduled_at.asc())
            .all()
        )

    def get_by_id(self, reminder_id: str) -> Optional[Reminder]:
        return self.db.query(Reminder).filter(Reminder.id == reminder_id).first()

    def get_for_user(self, reminder_id: str, user_id: str) -> Optional[Reminder]:
        """Fetch a reminder only if it belongs to user_id (both ids checked in the query)."""
        return (
            self.db.query(Reminder)
            .filter(Reminder.id == reminder_id, Reminder.user_id == user_id)
            .first()
        )

    def update(self, reminder: Reminder, data: ReminderUpdate) -> Reminder:
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(reminder, field, value)
        self.db.commit()
        self.db.refresh(reminder)
        return reminder

    def delete(self, reminder: Reminder) -> None:
        self.db.delete(reminder)
        self.db.commit()

