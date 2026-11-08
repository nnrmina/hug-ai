from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import logger

OPENAI_TRANSCRIPTION_URL = "https://api.openai.com/v1/audio/transcriptions"


class SpeechToTextError(Exception):
    """Raised when audio cannot be transcribed. Never silently replaced with a fake transcript."""

    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class SpeechToTextProvider:
    """Speech-to-Text adapter (Section 10.1).

    Providers:
      - "none":   server-side STT disabled; clients must send a text transcript.
      - "openai": OpenAI Whisper API (key read from server environment only).
      - "mock":   tests only — audio bytes that are valid UTF-8 text are used as the transcript.
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or settings.STT_PROVIDER or "none").lower()

    def transcribe(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language: str = "az-AZ",
        fallback_transcript: Optional[str] = None,
    ) -> str:
        """Convert Azerbaijani speech audio bytes into text."""
        if fallback_transcript and fallback_transcript.strip():
            return fallback_transcript.strip()

        if not audio_bytes:
            raise SpeechToTextError("Audio fayl boşdur.", 400)

        if self.provider == "mock":
            try:
                decoded = audio_bytes.decode("utf-8").strip()
            except UnicodeDecodeError:
                decoded = ""
            if decoded and all(ord(c) >= 32 or c in "\n\r\t" for c in decoded):
                return decoded
            raise SpeechToTextError("Səs tanınmadı (test rejimi).")

        if self.provider == "openai":
            return self._transcribe_openai(audio_bytes, filename, language)

        raise SpeechToTextError(
            "Serverdə səs tanıma aktiv deyil. Cihazın öz səs tanımasından istifadə edin "
            "və ya serverdə STT_PROVIDER=openai və OPENAI_API_KEY təyin edin.",
            503,
        )

    def _transcribe_openai(self, audio_bytes: bytes, filename: str, language: str) -> str:
        api_key = settings.stt_api_key
        if not api_key:
            raise SpeechToTextError("Serverdə OPENAI_API_KEY təyin edilməyib.", 503)

        try:
            response = httpx.post(
                OPENAI_TRANSCRIPTION_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                data={"model": "whisper-1", "language": language.split("-")[0]},
                files={"file": (filename, audio_bytes)},
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            logger.warning("Whisper request failed: %s", type(exc).__name__)
            raise SpeechToTextError("Səs tanıma xidməti ilə əlaqə qurulmadı.", 502)

        if response.status_code != 200:
            # Do not forward provider error bodies to clients (may contain account details).
            logger.warning("Whisper returned HTTP %s", response.status_code)
            raise SpeechToTextError("Səs tanıma xidməti xəta qaytardı.", 502)

        text = (response.json().get("text") or "").strip()
        if not text:
            raise SpeechToTextError("Heç bir nitq tanınmadı. Zəhmət olmasa təkrar danışın.")
        return text
