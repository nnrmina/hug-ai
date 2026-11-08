from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    ActionStatusResponse,
)
from app.services.assistant_service import AssistantService
from app.services.speech_service import SpeechService

router = APIRouter()


@router.post(
    "/assistant/message",
    response_model=AssistantResponse,
)
async def process_message(
    request: AssistantRequest,
    db: Session = Depends(get_db),
):
    service = AssistantService(db)
    return service.process_message(request)


@router.post(
    "/assistant/voice",
    response_model=AssistantResponse,
)
async def process_voice(
    audio: Optional[UploadFile] = File(default=None),
    transcript: Optional[str] = Form(default=None),
    user_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    speech_service = SpeechService()
    audio_bytes = await audio.read() if audio is not None else b""

    if not audio_bytes and not (transcript and transcript.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio fayl və ya səs transkripti təqdim edilməlidir.",
        )

    text_command = speech_service.speech_to_text(
        audio_bytes=audio_bytes,
        filename=audio.filename if audio and audio.filename else "voice.wav",
        fallback_transcript=transcript,
    )

    assistant_service = AssistantService(db)
    return assistant_service.process_message(
        AssistantRequest(message=text_command, user_id=user_id)
    )


@router.get(
    "/assistant/status/{action_id}",
    response_model=ActionStatusResponse,
)
async def get_assistant_status(
    action_id: str,
    db: Session = Depends(get_db),
):
    service = AssistantService(db)
    return service.get_action_status(action_id)


@router.post(
    "/assistant/confirm/{action_id}",
    response_model=ActionStatusResponse,
)
async def confirm_assistant_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    service = AssistantService(db)
    return service.confirm_action(action_id)


@router.post(
    "/assistant/cancel/{action_id}",
    response_model=ActionStatusResponse,
)
async def cancel_assistant_action(
    action_id: str,
    db: Session = Depends(get_db),
):
    service = AssistantService(db)
    return service.cancel_action(action_id)

