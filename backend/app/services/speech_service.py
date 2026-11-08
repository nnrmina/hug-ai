from typing import Optional
from app.integrations.speech.stt import SpeechToTextError, SpeechToTextProvider
from app.integrations.speech.tts import TextToSpeechProvider

# Re-exported for the API layer.
SpeechServiceError = SpeechToTextError


class SpeechService:
    """Service coordinating Speech-to-Text (STT) and Text-to-Speech (TTS) operations."""

    def __init__(self):
        self.stt = SpeechToTextProvider()
        self.tts = TextToSpeechProvider()

    def speech_to_text(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "az-AZ",
        fallback_transcript: Optional[str] = None,
    ) -> str:
        return self.stt.transcribe(
            audio_bytes=audio_bytes,
            filename=filename,
            language=language,
            fallback_transcript=fallback_transcript,
        )
