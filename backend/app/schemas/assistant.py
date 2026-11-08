from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class HistoryTurn(BaseModel):
    """A previous turn, sent by the client as a fallback when the server lost its session."""

    user: Optional[str] = Field(default=None, max_length=500)
    assistant: Optional[str] = Field(default=None, max_length=1000)
    intent: Optional[str] = Field(default=None, max_length=40)
    status: Optional[str] = Field(default=None, max_length=40)
    pending: Optional[Dict[str, Any]] = None


class AssistantRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="İstifadəçinin səsli və ya yazılı əmri")
    user_id: Optional[str] = Field(default=None, description="İstifadəçi identifikatoru (opsional)")
    session_id: Optional[str] = Field(default=None, max_length=64, description="Söhbət sessiyası (qısa yaddaş)")
    history: List[HistoryTurn] = Field(default_factory=list, max_length=6)


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
    transcript: Optional[str] = None
    engine: Optional[str] = Field(default=None, description="gemini | rule_based")
    action_token: Optional[str] = Field(default=None, description="Signed action for stateless confirm/cancel")


class ConfirmRequest(BaseModel):
    action_token: Optional[str] = Field(default=None, max_length=8000)


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
