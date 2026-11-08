from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey
from app.core.database import Base


class SecurityAnalysis(Base):
    """Digital Shield analysis results.

    Only the analysis is stored — never the raw (possibly sensitive) SMS/message text.
    """

    __tablename__ = "security_analyses"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    risk_level = Column(String(10), nullable=False)
    risk_score = Column(Integer, nullable=False)
    indicators = Column(JSON, nullable=False, default=list)
    explanation = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
