from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, ForeignKey
from app.core.database import Base


class PendingAction(Base):
    """Agent actions awaiting human confirmation.

    Stored in the database (not process memory) so confirmations survive restarts and
    work when requests hit different server instances (e.g. serverless deployments).
    """

    __tablename__ = "pending_actions"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    intent = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False)
    response = Column(Text, nullable=False, default="")
    action_data = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
