from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from app.core.database import Base


class DeviceCredential(Base):
    """Long-lived device secret used only to obtain new access tokens for the SAME account.

    Only a SHA-256 hash of the (256-bit random) secret is stored.
    """

    __tablename__ = "device_credentials"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    secret_hash = Column(String(64), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
