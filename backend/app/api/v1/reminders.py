from typing import List
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.schemas.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
)
from app.services.reminder_service import ReminderService

router = APIRouter()

# Every route takes the user from the verified token; any user_id sent by the client is ignored.


@router.post(
    "/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reminder(
    request: ReminderCreate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return ReminderService(db).create_reminder(request, user_id=user_id)


@router.get(
    "/reminders",
    response_model=List[ReminderResponse],
)
async def list_reminders(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return ReminderService(db).list_reminders(user_id=user_id)


@router.get(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
)
async def get_reminder(
    reminder_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return ReminderService(db).get_reminder(reminder_id, user_id=user_id)


@router.patch(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
)
async def update_reminder(
    reminder_id: str,
    request: ReminderUpdate,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return ReminderService(db).update_reminder(reminder_id, request, user_id=user_id)


@router.delete(
    "/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reminder(
    reminder_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    ReminderService(db).delete_reminder(reminder_id, user_id=user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
