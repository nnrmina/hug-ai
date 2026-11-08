import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.agents.graph import run_agent_workflow
from app.core.config import settings
from app.integrations.notifications.local import LocalNotificationFormatter
from app.models.pending_action import PendingAction
from app.repositories.reminder_repository import ReminderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.assistant import (
    ActionStatusResponse,
    AssistantRequest,
    AssistantResponse,
)
from app.schemas.reminder import ReminderCreate

# Only these intents can ever be executed through the confirmation endpoint.
CONFIRMABLE_INTENTS = {"CREATE_REMINDER", "MAKE_CALL", "SEND_VOICE_MESSAGE", "EMERGENCY_CALL"}


def _as_utc(dt: datetime) -> datetime:
    # SQLite returns naive datetimes even for timezone-aware columns.
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class AssistantService:
    """Orchestrates AI agent interactions, human-in-the-loop confirmations, and event logging."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.reminder_repo = ReminderRepository(db)

    # ------------------------------------------------------------------ helpers
    def _to_response(self, action: PendingAction) -> ActionStatusResponse:
        return ActionStatusResponse(
            action_id=action.id,
            intent=action.intent,
            status=action.status,  # type: ignore[arg-type]
            response=action.response or "",
            action_data=action.action_data or {},
        )

    def _get_action(self, action_id: str, user_id: str, not_found_detail: str) -> PendingAction:
        # Ownership check: another user's action is indistinguishable from a missing one.
        action = (
            self.db.query(PendingAction)
            .filter(PendingAction.id == action_id, PendingAction.user_id == user_id)
            .first()
        )
        if not action:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_detail)
        return action

    def _is_expired(self, action: PendingAction) -> bool:
        return _as_utc(action.expires_at) < datetime.now(timezone.utc)

    # ------------------------------------------------------------------ API
    def process_message(self, request: AssistantRequest, user_id: str) -> AssistantResponse:
        user = self.user_repo.get_or_create_default_user(user_id)

        final_state = run_agent_workflow(user_id=user.id, user_message=request.message)
        intent = final_state.get("intent") or "UNKNOWN"
        wf_status = final_state.get("status") or "needs_clarification"
        response_text = final_state.get("response") or ""
        action_data: Dict[str, Any] = dict(final_state.get("action_data") or {})

        # Every action is persisted (with owner, status and creation time) — confirmations survive
        # restarts, and expired/finished records stay as an audit trail.
        action_id = str(uuid.uuid4())
        self.db.add(
            PendingAction(
                id=action_id,
                user_id=user.id,
                intent=intent,
                status=wf_status,
                response=response_text,
                action_data=action_data,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.ACTION_TTL_MINUTES),
            )
        )
        self.db.commit()

        self.user_repo.log_agent_event(user_id=user.id, intent=intent, status=wf_status)

        return AssistantResponse(
            intent=intent,
            response=response_text,
            status=wf_status,  # type: ignore[arg-type]
            action_id=action_id,
            action_data=action_data,
        )

    def get_action_status(self, action_id: str, user_id: str) -> ActionStatusResponse:
        action = self._get_action(action_id, user_id, "Əməliyyat tapılmadı.")
        return self._to_response(action)

    def confirm_action(self, action_id: str, user_id: str) -> ActionStatusResponse:
        action = self._get_action(action_id, user_id, "Təsdiqlənəcək əməliyyat tapılmadı.")

        if action.status != "needs_confirmation" or action.intent not in CONFIRMABLE_INTENTS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu əməliyyat təsdiq gözləmir (artıq icra edilib, ləğv edilib və ya rədd edilib).",
            )
        if self._is_expired(action):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Təsdiq müddəti bitib. Zəhmət olmasa əmri yenidən deyin.",
            )

        # Atomically claim the action so a double tap / duplicate request cannot execute it twice.
        claimed = self.db.execute(
            update(PendingAction)
            .where(
                PendingAction.id == action_id,
                PendingAction.user_id == user_id,
                PendingAction.status == "needs_confirmation",
            )
            .values(status="executing")
        ).rowcount
        self.db.commit()
        if claimed != 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu əməliyyat artıq icra olunur və ya icra edilib.",
            )
        self.db.refresh(action)

        intent = action.intent
        action_data = dict(action.action_data or {})

        try:
            if intent == "CREATE_REMINDER":
                scheduled_str = action_data.get("scheduled_at")
                if not isinstance(scheduled_str, str):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Xatırlatma vaxtı müəyyən edilmədi.",
                    )
                title = action_data.get("title") or "Xatırlatma"
                timezone_str = action_data.get("timezone") or settings.DEFAULT_TIMEZONE
                reminder = self.reminder_repo.create(
                    user_id=user_id,
                    data=ReminderCreate(
                        title=title,
                        scheduled_at=datetime.fromisoformat(scheduled_str),
                        timezone=timezone_str,
                    ),
                )
                action_data["reminder_id"] = reminder.id
                action_data["notification"] = LocalNotificationFormatter.build_reminder_notification(
                    reminder_id=reminder.id,
                    title=reminder.title,
                    scheduled_at=reminder.scheduled_at,
                    timezone=reminder.timezone,
                )
                response = f'"{title}" xatırlatması uğurla yaradıldı.'
            elif intent == "MAKE_CALL":
                alias = action_data.get("contact_alias", "kontakt")
                action_data["authorized_execution"] = "OPEN_DIALER"
                response = f'"{alias}" üçün zəng təsdiqləndi. Nömrə yığıcı açılır.'
            elif intent == "EMERGENCY_CALL":
                action_data["authorized_execution"] = "OPEN_DIALER"
                response = f'Təcili yardım ({action_data.get("phone_number", "103")}) nömrəsi yığılır.'
            else:  # SEND_VOICE_MESSAGE
                alias = action_data.get("contact_alias", "kontakt")
                action_data["authorized_execution"] = "SEND_VOICE_MESSAGE"
                response = f'"{alias}" üçün səsli mesaj təsdiqləndi.'
        except Exception:
            # Release the claim so the user can retry.
            action.status = "needs_confirmation"
            self.db.commit()
            raise

        action.status = "completed"
        action.response = response
        action.action_data = action_data
        self.db.commit()
        self.db.refresh(action)

        self.user_repo.log_agent_event(user_id=user_id, intent=intent, status="completed")
        return self._to_response(action)

    def cancel_action(self, action_id: str, user_id: str) -> ActionStatusResponse:
        action = self._get_action(action_id, user_id, "Ləğv ediləcək əməliyyat tapılmadı.")
        if action.status != "needs_confirmation":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Yalnız təsdiq gözləyən əməliyyat ləğv edilə bilər.",
            )

        action.status = "cancelled"
        action.response = "Əməliyyat istifadəçi tərəfindən ləğv edildi."
        self.db.commit()
        self.db.refresh(action)

        self.user_repo.log_agent_event(user_id=action.user_id, intent=action.intent, status="cancelled")
        return self._to_response(action)
