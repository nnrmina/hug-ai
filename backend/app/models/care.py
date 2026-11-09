"""Care features: elder profile, family circle, medications, check-ins, SOS, push.

All NEW tables (Base.metadata.create_all only creates missing tables; it never alters
existing ones), so this deploys safely onto the live SQLite database.
"""
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _token() -> str:
    return secrets.token_urlsafe(18)


class ElderProfile(Base):
    """The person HUG cares for (one per device / user)."""

    __tablename__ = "elder_profiles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name = Column(String(100), nullable=False, default="")
    checkin_time = Column(String(5), nullable=False, default="10:00")  # HH:MM, Asia/Baku
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class FamilyMember(Base):
    """A relative in the family circle. Their private link (invite_token) opens the family view."""

    __tablename__ = "family_members"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    relation = Column(String(50), nullable=False, default="")  # qızım, oğlum, bacım, həkim…
    phone = Column(String(30), nullable=False, default="")
    invite_token = Column(String(64), nullable=False, unique=True, default=_token)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class PushSubscription(Base):
    """A browser push endpoint, owned by the elder (owner_type='elder') or a family member."""

    __tablename__ = "push_subscriptions"

    id = Column(String(36), primary_key=True, default=_uuid)
    endpoint = Column(Text, nullable=False, unique=True)
    p256dh = Column(String(200), nullable=False)
    auth = Column(String(100), nullable=False)
    owner_type = Column(String(10), nullable=False)  # elder | family
    owner_id = Column(String(36), nullable=False, index=True)  # user_id or family_member_id
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class Medication(Base):
    """A recurring medicine schedule, e.g. 'Kardiomaqnil' at 09:00 and 21:00 every day."""

    __tablename__ = "medications"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    dose = Column(String(80), nullable=False, default="")
    times = Column(String(200), nullable=False)  # comma-separated HH:MM (Asia/Baku)
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(String(60), nullable=False, default="elder")  # elder | family:<name>
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class DoseEvent(Base):
    """One scheduled intake of a medication. pending → taken | missed (snooze re-times it)."""

    __tablename__ = "dose_events"
    __table_args__ = (UniqueConstraint("medication_id", "slot", name="uq_dose_slot"),)

    id = Column(String(36), primary_key=True, default=_uuid)
    medication_id = Column(String(36), ForeignKey("medications.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    slot = Column(String(16), nullable=False)  # 'YYYY-MM-DD HH:MM' Baku: idempotency key
    scheduled_at = Column(DateTime(timezone=True), nullable=False)  # UTC; moves on snooze
    status = Column(String(10), nullable=False, default="pending")  # pending | taken | missed
    notified_at = Column(DateTime(timezone=True), nullable=True)
    taken_at = Column(DateTime(timezone=True), nullable=True)
    family_notified = Column(Boolean, nullable=False, default=False)


class CheckIn(Base):
    """The daily 'how are you feeling?' answer."""

    __tablename__ = "checkins"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    day = Column(String(10), nullable=False)  # YYYY-MM-DD (Baku)
    mood = Column(String(10), nullable=False)  # good | ok | bad
    note = Column(String(300), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class CareEvent(Base):
    """Timeline the family sees: SOS, missed doses, check-ins, scheduler bookkeeping."""

    __tablename__ = "care_events"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    kind = Column(String(30), nullable=False)
    # sos | sos_cancelled | dose_missed | dose_taken | checkin | checkin_missed | checkin_prompt | reminder_push | health
    message = Column(String(300), nullable=False, default="")
    status = Column(String(30), nullable=True)  # delivered | no_devices | no_family | cancelled | failed
    notified_count = Column(Integer, nullable=True, default=0)
    ref = Column(String(64), nullable=True, index=True)  # e.g. reminder id / day, for idempotency
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)


class HealthReading(Base):
    """Self-reported measurements: blood pressure, sugar, pulse, temperature, weight."""

    __tablename__ = "health_readings"

    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(36), nullable=False, index=True)
    kind = Column(String(10), nullable=False)  # bp | sugar | pulse | temp | weight
    value = Column(Float, nullable=False)
    value2 = Column(Float, nullable=True)  # diastolic for bp
    level = Column(String(10), nullable=False, default="normal")  # normal | high | low | critical
    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
