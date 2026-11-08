"""HMAC-signed confirmation tokens.

A pending action (call / reminder / order) normally lives in the in-memory action store.
On serverless platforms the confirm request can land on a different instance, so the
response also carries a signed token describing the action; confirm/cancel accept it when
the store has no record. Tokens expire and cannot be forged without ACTION_SIGNING_KEY.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

from app.core.config import settings

_PROCESS_KEY = secrets.token_bytes(32)


def _key() -> bytes:
    configured = (settings.ACTION_SIGNING_KEY or "").strip()
    return configured.encode("utf-8") if configured else _PROCESS_KEY


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign_action(record: Dict[str, Any], ttl_s: Optional[int] = None) -> str:
    payload = {
        "action_id": record["action_id"],
        "user_id": record.get("user_id"),
        "intent": record["intent"],
        "action_data": record.get("action_data") or {},
        "exp": int(time.time()) + (ttl_s or settings.ACTION_TOKEN_TTL_S),
    }
    body = _b64(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))
    sig = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_action(token: Optional[str], action_id: str) -> Optional[Dict[str, Any]]:
    """Return the signed action record if the token is valid, unexpired and for action_id."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    expected = _b64(hmac.new(_key(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        payload = json.loads(_unb64(body))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("action_id") != action_id or payload.get("exp", 0) < time.time():
        return None
    return payload
