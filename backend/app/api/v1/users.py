from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.user_repository import UserRepository
from app.repositories.preference_repository import PreferenceRepository
from app.schemas.user import (
    UserResponse,
    UserPreferenceSchema,
    UserPreferenceUpdate,
)

router = APIRouter()


@router.get(
    "/users/me",
    response_model=UserResponse,
)
async def get_current_user(
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    return user_repo.get_or_create_default_user(user_id=user_id)


@router.patch(
    "/users/preferences",
    response_model=UserPreferenceSchema,
)
async def update_user_preferences(
    request: UserPreferenceUpdate,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    user_repo = UserRepository(db)
    pref_repo = PreferenceRepository(db)
    user = user_repo.get_or_create_default_user(user_id=user_id)
    return pref_repo.update_preferences(user.id, request)

