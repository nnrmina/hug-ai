from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
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
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return UserRepository(db).get_or_create_default_user(user_id=user_id)


@router.patch(
    "/users/preferences",
    response_model=UserPreferenceSchema,
)
async def update_user_preferences(
    request: UserPreferenceUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return PreferenceRepository(db).update_preferences(user_id, request)
