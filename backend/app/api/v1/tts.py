from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.integrations.speech.neural_tts import MAX_TEXT_LENGTH, VOICES, synthesize_mp3

router = APIRouter()


@router.get("/tts", response_class=FileResponse)
async def text_to_speech(
    text: str = Query(..., min_length=1, max_length=MAX_TEXT_LENGTH),
    lang: str = Query(default="az", pattern="^(az|ru)$"),
):
    """Speak Azerbaijani text with the neural az-AZ voice. Returns audio/mpeg.

    503 means synthesis is unavailable (no network / edge-tts missing); the client
    should fall back to the browser's own speechSynthesis.
    """
    path = await synthesize_mp3(text.strip(), VOICES[lang])
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Səs sintezi hazırda əlçatan deyil.",
        )
    return FileResponse(
        path,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
