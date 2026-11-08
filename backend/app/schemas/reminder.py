from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

_BAKU = dt_timezone(timedelta(hours=4), name="Asia/Baku")
_TZ_PATTERN = r"^[A-Za-z]+(?:/[A-Za-z_\-]+){0,2}$|^UTC$"


def _clean_title(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not v:
        raise ValueError("Başlıq boş ola bilməz.")
    return v


def _aware(v: Optional[datetime]) -> Optional[datetime]:
    # A time without timezone is interpreted as Baku local time instead of silently as UTC.
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=_BAKU)
    return v


class ReminderCreate(BaseModel):
    """Owner is always the authenticated user; a client-sent user_id is ignored."""

    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    scheduled_at: datetime
    timezone: str = Field(default="Asia/Baku", max_length=50, pattern=_TZ_PATTERN)

    _title = field_validator("title")(classmethod(lambda cls, v: _clean_title(v)))
    _when = field_validator("scheduled_at")(classmethod(lambda cls, v: _aware(v)))


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    scheduled_at: Optional[datetime] = None
    timezone: Optional[str] = Field(default=None, max_length=50, pattern=_TZ_PATTERN)
    status: Optional[Literal["pending", "completed", "cancelled"]] = None

    _title = field_validator("title")(classmethod(lambda cls, v: _clean_title(v)))
    _when = field_validator("scheduled_at")(classmethod(lambda cls, v: _aware(v)))


class ReminderResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    scheduled_at: datetime
    timezone: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
