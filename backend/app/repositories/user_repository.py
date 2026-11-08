from typing import Optional
from sqlalchemy.orm import Session
from app.models.user import User, DEFAULT_USER_ID
from app.models.preference import UserPreference
from app.models.agent_event import AgentEvent


class UserRepository:
    """Repository for User and AgentEvent persistence."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create_default_user(self, user_id: Optional[str] = None) -> User:
        target_id = user_id or DEFAULT_USER_ID
        user = self.db.query(User).filter(User.id == target_id).first()
        if not user:
            user = User(
                id=target_id,
                display_name="Yaxın İstifadəçi",
                language="az-AZ",
            )
            self.db.add(user)
            self.db.flush()
            pref = UserPreference(
                user_id=user.id,
                voice_speed=1.0,
                voice_response=True,
                theme="light",
                language="az-AZ",
            )
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(user)
        elif not user.preferences:
            pref = UserPreference(
                user_id=user.id,
                voice_speed=1.0,
                voice_response=True,
                theme="light",
                language="az-AZ",
            )
            self.db.add(pref)
            self.db.commit()
            self.db.refresh(user)
        return user

    def log_agent_event(self, user_id: Optional[str], intent: str, status: str) -> AgentEvent:
        """Record sanitized agent execution metadata (no PII or raw message content)."""
        user = self.get_or_create_default_user(user_id)
        event = AgentEvent(
            user_id=user.id,
            intent=intent,
            status=status,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

