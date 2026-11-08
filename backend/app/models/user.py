import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base

DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"


class User(Base):
    """Users table (Section 7.2). Phone number is optional and contacts are never stored here."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    display_name = Column(String(100), nullable=False, default="Yaxın İstifadəçi")
    phone_number = Column(String(20), nullable=True)
    language = Column(String(10), nullable=False, default="az-AZ")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    preferences = relationship(
        "UserPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    reminders = relationship(
        "Reminder",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    agent_events = relationship(
        "AgentEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )

