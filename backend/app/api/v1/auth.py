import hashlib
import hmac
import secrets
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import create_access_token, parse_uuid
from app.core.database import get_db
from app.core.logging import logger
from app.models.device_claim import DeviceClaim
from app.models.device_credential import DeviceCredential
from app.models.user import DEFAULT_USER_ID, User
from app.repositories.user_repository import UserRepository

router = APIRouter()


class DeviceRegisterRequest(BaseModel):
    # Re-login of an already registered device (token lost/expired): same account, same data.
    user_id: Optional[str] = Field(default=None, max_length=64)
    device_secret: Optional[str] = Field(default=None, max_length=128)
    # First registration of a device that used the pre-JWT version: keeps its data (claimable once).
    legacy_user_id: Optional[str] = Field(default=None, max_length=64)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    expires_at: datetime
    # Returned ONLY when a new device binding is created. The client must store it securely.
    device_secret: Optional[str] = None


def _hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _bind_device(db: Session, user_id: str) -> Optional[str]:
    """Bind an account to a device (at most once per account). Returns the new device secret."""
    device_secret = secrets.token_urlsafe(32)
    db.add(DeviceClaim(user_id=user_id))
    db.add(DeviceCredential(user_id=user_id, secret_hash=_hash_secret(device_secret)))
    try:
        db.commit()
        return device_secret
    except IntegrityError:
        db.rollback()
        return None


@router.post("/auth/device", response_model=TokenResponse)
async def register_device(request: DeviceRegisterRequest, db: Session = Depends(get_db)):
    """Anonymous per-device accounts with signed access tokens."""
    # 1) Known device re-authenticating with its secret.
    if request.user_id or request.device_secret:
        user_id = parse_uuid(request.user_id)
        cred = db.get(DeviceCredential, user_id) if user_id else None
        if (
            cred is None
            or not request.device_secret
            or not hmac.compare_digest(cred.secret_hash, _hash_secret(request.device_secret))
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Cihaz məlumatları yanlışdır. Tətbiqi yenidən qurun.",
            )
        token, expires_at = create_access_token(user_id)
        return TokenResponse(access_token=token, user_id=user_id, expires_at=expires_at)

    # 2) Pre-JWT device keeping its data: the legacy account can be bound exactly once.
    legacy = parse_uuid(request.legacy_user_id)
    if legacy and legacy != DEFAULT_USER_ID and db.get(User, legacy) is not None:
        device_secret = _bind_device(db, legacy)
        if device_secret:
            logger.info("Legacy account bound to a device.")
            token, expires_at = create_access_token(legacy)
            return TokenResponse(
                access_token=token, user_id=legacy, expires_at=expires_at, device_secret=device_secret
            )

    # 3) Brand-new device.
    user_id = str(uuid.uuid4())
    UserRepository(db).get_or_create_default_user(user_id)
    device_secret = _bind_device(db, user_id)
    token, expires_at = create_access_token(user_id)
    return TokenResponse(access_token=token, user_id=user_id, expires_at=expires_at, device_secret=device_secret)
