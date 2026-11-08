from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.database import Base


class DeviceClaim(Base):
    """Marks a user account as bound to a device token.

    Accounts created before JWT auth (identified only by a client-sent UUID) can be claimed
    exactly once by POST /auth/device; after that the UUID alone grants nothing.
    """

    __tablename__ = "device_claims"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    claimed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
