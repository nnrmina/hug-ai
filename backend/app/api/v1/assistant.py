import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import device_user_id
from app.core.database import get_db
from app.schemas.assistant import (
    ActionStatusResponse,
    AssistantRequest,
    AssistantResponse,
    ConfirmRequest,
    HistoryTurn,
)
from app.services.assistant_service import AssistantService

router = APIRouter()

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # stays under Vercel's 4.5 MB request body limit
ALLOWED_AUDIO_TYPES = {
    "audio/wav", "audio/x-wav", "audio/wave", "audio/mpeg", "audio/mp3", "audio/aac",
    "audio/ogg", "audio/flac", "audio/aiff", "audio/x-aiff", "audio/webm", "audio/mp4",
}

# Routes are plain `def`: the LLM call is blocking, so FastAPI runs them in its threadpool
# instead of stalling the event loop.


@router.get("/assistant/capabilities")
def capabilities():
    """What the client can rely on: whether server-side audio understanding (Gemini) is on."""
    from app.core.config import settings
    from app.integrations.llm.gemini import GeminiLLMAdapter
    from app.integrations.llm.provider import get_llm_adapter

    gemini = isinstance(get_llm_adapter(), GeminiLLMAdapter)
    return {
        "engine": "gemini" if gemini else "rule_based",
        "model": settings.LLM_MODEL_NAME if gemini else None,
        "audio_understanding": gemini,
        "neural_tts": True,
        "max_audio_bytes": MAX_AUDIO_BYTES,
    }


@router.post("/assistant/message", response_model=AssistantResponse)
def process_message(request: AssistantRequest, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    request.user_id = uid
    return AssistantService(db).process_message(request)


@router.post("/assistant/voice", response_model=AssistantResponse)
def process_voice(
    audio: Optional[UploadFile] = File(default=None),
    mime_type: Optional[str] = Form(default=None),
    transcript: Optional[str] = Form(default=None, max_length=2000),
    session_id: Optional[str] = Form(default=None, max_length=64),
    history: Optional[str] = Form(default=None, description="JSON list of recent turns"),
    uid: str = Depends(device_user_id),
    db: Session = Depends(get_db),
):
    """Spoken command: Gemini transcribes and understands the audio in one call.
    `transcript` (from browser speech recognition) is used as a hint / fallback."""
    audio_bytes = audio.file.read(MAX_AUDIO_BYTES + 1) if audio is not None else b""
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Səs yazısı çox uzundur (maks. ~60 saniyə).")
    if not audio_bytes and not (transcript and transcript.strip()):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio fayl və ya səs transkripti təqdim edilməlidir.")

    mime = (mime_type or (audio.content_type if audio else None) or "audio/wav").split(";")[0].strip().lower()
    if audio_bytes and mime not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Dəstəklənməyən audio formatı: {mime}")

    try:
        turns = [HistoryTurn.model_validate(t).model_dump() for t in json.loads(history)][-6:] if history else []
    except (ValueError, TypeError, ValidationError):
        turns = []

    return AssistantService(db).process_turn(
        text=transcript,
        audio=audio_bytes or None,
        mime_type=mime,
        session_id=session_id,
        client_history=turns,
        user_id=uid,
    )


@router.get("/assistant/status/{action_id}", response_model=ActionStatusResponse)
def get_assistant_status(action_id: str, db: Session = Depends(get_db)):
    return AssistantService(db).get_action_status(action_id)


@router.post("/assistant/confirm/{action_id}", response_model=ActionStatusResponse)
def confirm_assistant_action(
    action_id: str,
    body: Optional[ConfirmRequest] = Body(default=None),
    uid: str = Depends(device_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).confirm_action(action_id, body.action_token if body else None, owner_id=uid)


@router.post("/assistant/cancel/{action_id}", response_model=ActionStatusResponse)
def cancel_assistant_action(
    action_id: str,
    body: Optional[ConfirmRequest] = Body(default=None),
    uid: str = Depends(device_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).cancel_action(action_id, body.action_token if body else None, owner_id=uid)
