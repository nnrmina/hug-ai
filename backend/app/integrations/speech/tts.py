from typing import Dict, Any, Optional
from app.core.config import settings


class TextToSpeechProvider:
    """Text-to-Speech metadata/audio synthesis adapter for Azerbaijani (az-AZ) (Section 10.3)."""

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or settings.TTS_PROVIDER

    def synthesize_metadata(
        self,
        text: str,
        language: str = "az-AZ",
        voice_speed: float = 1.0,
    ) -> Dict[str, Any]:
        """Prepare TTS instruction payload for client or cloud synthesis."""
        return {
            "provider": self.provider,
            "language": language,
            "voice_speed": voice_speed,
            "text": text,
            "fallback_to_text": True,
        }

