import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AgentEvent(Base):
    """Agent Events metadata table (Section 7.5).
    Stores only operation intent and status—never raw audio, contacts, or sensitive SMS text.
    """

    __tablename__ = "agent_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    intent = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="agent_events")

