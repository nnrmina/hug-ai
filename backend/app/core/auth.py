"""Authentication: anonymous per-device accounts with signed JWT access tokens.

The server never trusts a user_id sent by the client. A device registers once
(POST /api/v1/auth/device), receives a signed token, and every request's user is
derived from that token's "sub" claim.
"""
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "yaxin-ai"
_DEV_SECRET_FILE = Path(__file__).resolve().parents[2] / ".dev_jwt_secret"
_bearer = HTTPBearer(auto_error=False)
_cached_secret: Optional[str] = None


def _jwt_secret() -> str:
    global _cached_secret
    if settings.JWT_SECRET:
        return settings.JWT_SECRET
    if settings.is_production:
        raise RuntimeError("JWT_SECRET production-da mütləq təyin edilməlidir.")
    if _cached_secret:
        return _cached_secret
    # Development only: a random secret persisted locally (gitignored) so tokens survive restarts.
    try:
        if _DEV_SECRET_FILE.exists():
            _cached_secret = _DEV_SECRET_FILE.read_text(encoding="utf-8").strip()
        if not _cached_secret:
            _cached_secret = secrets.token_urlsafe(48)
            _DEV_SECRET_FILE.write_text(_cached_secret, encoding="utf-8")
    except OSError:
        _cached_secret = _cached_secret or secrets.token_urlsafe(48)
        logger.warning("Could not persist development JWT secret; tokens reset on restart.")
    return _cached_secret


def create_access_token(user_id: str) -> Tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.JWT_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "iss": JWT_ISSUER,
        "typ": "device",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM), expires_at


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> str:
    """FastAPI dependency: the authenticated user's id, taken only from a valid token."""
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise _unauthorized("Giriş tələb olunur (Authorization: Bearer token).")
    try:
        payload = jwt.decode(
            credentials.credentials,
            _jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Sessiyanın vaxtı bitib. Yenidən qeydiyyatdan keçin.")
    except jwt.InvalidTokenError:
        raise _unauthorized("Token etibarsızdır.")

    if payload.get("typ") != "device":
        raise _unauthorized("Token etibarsızdır.")
    user_id = str(payload["sub"])

    from app.models.user import User  # local import avoids a circular import at startup

    if db.get(User, user_id) is None:
        raise _unauthorized("İstifadəçi tapılmadı. Yenidən qeydiyyatdan keçin.")
    return user_id


async def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """Enforce the shared API key when API_KEY is configured (no-op otherwise)."""
    expected = settings.API_KEY
    if not expected:
        return
    if not x_api_key or not hmac.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Giriş icazəsi yoxdur (X-API-Key yanlışdır).",
        )


def parse_uuid(value: Optional[str]) -> Optional[str]:
    """Return a normalized UUID string, or None if the value is missing/invalid."""
    if not value:
        return None
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, AttributeError, TypeError):
        return None
