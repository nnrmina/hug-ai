from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.config import settings
from app.core.database import get_db
from app.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    ActionStatusResponse,
    TranscriptionResponse,
)
from app.services.assistant_service import AssistantService
from app.services.speech_service import SpeechService, SpeechServiceError

router = APIRouter()

ALLOWED_AUDIO_MIME_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/aac",
    "video/webm",  # some browsers label MediaRecorder audio-only output as video/webm
}


def _looks_like_audio(data: bytes) -> bool:
    """Check the file signature so a renamed non-audio file is rejected even with an audio MIME type."""
    head = data[:16]
    return (
        head.startswith(b"\x1a\x45\xdf\xa3")                      # WebM / Matroska
        or head.startswith(b"OggS")                               # Ogg / Opus
        or (head.startswith(b"RIFF") and head[8:12] == b"WAVE")   # WAV
        or head.startswith(b"ID3")                                # MP3 with ID3 tag
        or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0)  # MP3 / AAC frame sync
        or head[4:8] == b"ftyp"                                   # MP4 / M4A
    )


async def _read_audio(audio: Optional[UploadFile]) -> bytes:
    if audio is None:
        return b""
    content_type = (audio.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_AUDIO_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Dəstəklənməyən fayl növü. Yalnız səs faylları qəbul olunur (webm, ogg, wav, mp3, m4a, aac).",
        )
    data = await audio.read(settings.STT_MAX_AUDIO_BYTES + 1)
    if len(data) > settings.STT_MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Səs faylı çox böyükdür (maksimum {settings.STT_MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
        )
    # The "mock" provider (tests only, refused in production) feeds UTF-8 text as fake audio.
    if data and settings.STT_PROVIDER.lower() != "mock" and not _looks_like_audio(data):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Fayl səs faylına oxşamır.",
        )
    return data


def _transcribe(audio_bytes: bytes, filename: str, transcript: Optional[str]) -> str:
    try:
        return SpeechService().speech_to_text(
            audio_bytes=audio_bytes,
            filename=filename,
            fallback_transcript=transcript,
        )
    except SpeechServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post(
    "/assistant/message",
    response_model=AssistantResponse,
)
async def process_message(
    request: AssistantRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).process_message(request, user_id=user_id)


@router.post(
    "/speech/transcribe",
    response_model=TranscriptionResponse,
)
async def transcribe_audio(
    audio: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """Server-side speech recognition: the provider API key never leaves the server."""
    audio_bytes = await _read_audio(audio)
    if not audio_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Audio fayl boşdur.")
    text = _transcribe(audio_bytes, audio.filename or "voice.webm", None)
    return TranscriptionResponse(text=text)


@router.post(
    "/assistant/voice",
    response_model=AssistantResponse,
)
async def process_voice(
    audio: Optional[UploadFile] = File(default=None),
    transcript: Optional[str] = Form(default=None, max_length=2000),
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    audio_bytes = await _read_audio(audio)

    if not audio_bytes and not (transcript and transcript.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio fayl və ya səs transkripti təqdim edilməlidir.",
        )

    text_command = _transcribe(
        audio_bytes,
        audio.filename if audio and audio.filename else "voice.wav",
        transcript,
    )

    try:
        request = AssistantRequest(message=text_command)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors()[0].get("msg", "Yanlış sorğu."),
        )
    return AssistantService(db).process_message(request, user_id=user_id)


@router.get(
    "/assistant/status/{action_id}",
    response_model=ActionStatusResponse,
)
async def get_assistant_status(
    action_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).get_action_status(action_id, user_id=user_id)


@router.post(
    "/assistant/confirm/{action_id}",
    response_model=ActionStatusResponse,
)
async def confirm_assistant_action(
    action_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).confirm_action(action_id, user_id=user_id)


@router.post(
    "/assistant/cancel/{action_id}",
    response_model=ActionStatusResponse,
)
async def cancel_assistant_action(
    action_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return AssistantService(db).cancel_action(action_id, user_id=user_id)
