"""Azerbaijani neural text-to-speech via edge-tts (Microsoft az-AZ-BanuNeural voice).

Free, no API key. Generated MP3s are cached on disk by text hash, so repeated phrases
are served instantly and only new sentences hit the network.
"""
import hashlib
import os
from pathlib import Path
from typing import Optional

VOICE = "az-AZ-BanuNeural"
VOICES = {"az": VOICE, "ru": "ru-RU-SvetlanaNeural"}
MAX_TEXT_LENGTH = 600


def _cache_dir() -> Path:
    # TTS_CACHE_DIR (Docker volume) > /tmp on Vercel (read-only FS) > backend/.tts_cache locally
    if os.environ.get("TTS_CACHE_DIR"):
        base = Path(os.environ["TTS_CACHE_DIR"])
    elif os.environ.get("VERCEL"):
        base = Path("/tmp/hug_tts_cache")
    else:
        base = Path(__file__).resolve().parents[3] / ".tts_cache"
    base.mkdir(parents=True, exist_ok=True)
    return base


async def synthesize_mp3(text: str, voice: str = VOICE) -> Optional[Path]:
    """Return a path to an MP3 of `text`, or None if synthesis is unavailable."""
    try:
        import edge_tts
    except ImportError:
        return None

    key = hashlib.sha256(f"{voice}|{text}".encode("utf-8")).hexdigest()
    path = _cache_dir() / f"{key}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path

    tmp_path = path.with_suffix(".part")
    for _attempt in range(2):  # the edge service occasionally drops a request: retry once
        try:
            await edge_tts.Communicate(text, voice).save(str(tmp_path))
            if tmp_path.stat().st_size > 0:
                tmp_path.replace(path)
                return path
        except Exception:
            pass
        tmp_path.unlink(missing_ok=True)
    return None
