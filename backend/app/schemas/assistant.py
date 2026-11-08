from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="İstifadəçinin səsli və ya yazılı əmri")
    user_id: Optional[str] = Field(default=None, description="İstifadəçi identifikatoru (opsional)")


class AssistantResponse(BaseModel):
    intent: str
    response: str
    status: Literal[
        "completed",
        "needs_confirmation",
        "needs_clarification",
        "rejected",
    ]
    action_id: Optional[str] = None
    action_data: Optional[Dict[str, Any]] = None


class ActionStatusResponse(BaseModel):
    action_id: str
    intent: str
    status: Literal[
        "completed",
        "needs_confirmation",
        "needs_clarification",
        "rejected",
        "cancelled",
    ]
    response: str
    action_data: Optional[Dict[str, Any]] = None

