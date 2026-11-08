import uuid
from sqlalchemy import Column, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserPreference(Base):
    """User Preferences table (Section 7.3)."""

    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    voice_speed = Column(Float, nullable=False, default=1.0)
    voice_response = Column(Boolean, nullable=False, default=True)
    theme = Column(String(20), nullable=False, default="light")
    language = Column(String(10), nullable=False, default="az-AZ")

    user = relationship("User", back_populates="preferences")

