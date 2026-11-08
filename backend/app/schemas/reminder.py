from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class ReminderCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    scheduled_at: datetime
    timezone: str = Field(default="Asia/Baku", max_length=50)
    user_id: Optional[str] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    scheduled_at: Optional[datetime] = None
    timezone: Optional[str] = Field(default=None, max_length=50)
    status: Optional[Literal["pending", "completed", "cancelled"]] = None


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

