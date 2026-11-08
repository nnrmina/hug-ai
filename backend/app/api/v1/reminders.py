from typing import List, Optional
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.reminder import (
    ReminderCreate,
    ReminderUpdate,
    ReminderResponse,
)
from app.services.reminder_service import ReminderService

router = APIRouter()


@router.post(
    "/reminders",
    response_model=ReminderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_reminder(
    request: ReminderCreate,
    db: Session = Depends(get_db),
):
    service = ReminderService(db)
    return service.create_reminder(request)


@router.get(
    "/reminders",
    response_model=List[ReminderResponse],
)
async def list_reminders(
    user_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = ReminderService(db)
    return service.list_reminders(user_id=user_id)


@router.get(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
)
async def get_reminder(
    reminder_id: str,
    db: Session = Depends(get_db),
):
    service = ReminderService(db)
    return service.get_reminder(reminder_id)


@router.patch(
    "/reminders/{reminder_id}",
    response_model=ReminderResponse,
)
async def update_reminder(
    reminder_id: str,
    request: ReminderUpdate,
    db: Session = Depends(get_db),
):
    service = ReminderService(db)
    return service.update_reminder(reminder_id, request)


@router.delete(
    "/reminders/{reminder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_reminder(
    reminder_id: str,
    db: Session = Depends(get_db),
):
    service = ReminderService(db)
    service.delete_reminder(reminder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

