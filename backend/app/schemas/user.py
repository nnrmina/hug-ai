from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class UserPreferenceSchema(BaseModel):
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    voice_response: bool = True
    theme: Literal["light", "dark", "high_contrast"] = "light"
    language: str = "az-AZ"

    model_config = ConfigDict(from_attributes=True)


class UserPreferenceUpdate(BaseModel):
    voice_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    voice_response: Optional[bool] = None
    theme: Optional[Literal["light", "dark", "high_contrast"]] = None
    language: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    display_name: str
    phone_number: Optional[str] = None
    language: str
    created_at: datetime
    preferences: Optional[UserPreferenceSchema] = None

    model_config = ConfigDict(from_attributes=True)

