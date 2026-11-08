from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class AssistantRequest(BaseModel):
    """The user is taken from the access token; a client-sent user_id is ignored."""

    message: str = Field(..., min_length=1, max_length=2000, description="İstifadəçinin səsli və ya yazılı əmri")

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mesaj boş ola bilməz.")
        return v


WorkflowStatus = Literal[
    "completed",
    "needs_confirmation",
    "needs_clarification",
    "rejected",
]


class AssistantResponse(BaseModel):
    intent: str
    response: str
    status: WorkflowStatus
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
        "executing",
    ]
    response: str
    action_data: Optional[Dict[str, Any]] = None


class TranscriptionResponse(BaseModel):
    text: str
