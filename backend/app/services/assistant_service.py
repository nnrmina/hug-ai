import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.agents.graph import run_agent_workflow
from app.models.user import DEFAULT_USER_ID
from app.repositories.user_repository import UserRepository
from app.repositories.reminder_repository import ReminderRepository
from app.schemas.assistant import (
    AssistantRequest,
    AssistantResponse,
    ActionStatusResponse,
)
from app.schemas.reminder import ReminderCreate
from app.integrations.notifications.local import LocalNotificationFormatter
from app.agents.tools.order_tools import ORDER_INTENTS
from app.utils.datetime_utils import format_az_datetime

# In-memory store of workflow action states for confirmation/cancellation lifecycle
_ACTION_STORE: Dict[str, Dict[str, Any]] = {}


class AssistantService:
    """Orchestrates AI agent interactions, human-in-the-loop confirmations, and event logging."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.reminder_repo = ReminderRepository(db)

    def process_message(self, request: AssistantRequest) -> AssistantResponse:
        user_id = request.user_id or DEFAULT_USER_ID
        user = self.user_repo.get_or_create_default_user(user_id)

        final_state = run_agent_workflow(user_id=user.id, user_message=request.message)
        intent = final_state.get("intent") or "UNKNOWN"
        wf_status = final_state.get("status") or "needs_clarification"
        response_text = final_state.get("response") or ""
        action_data = dict(final_state.get("action_data") or {})

        action_id = str(uuid.uuid4())
        _ACTION_STORE[action_id] = {
            "action_id": action_id,
            "user_id": user.id,
            "intent": intent,
            "status": wf_status,
            "response": response_text,
            "action_data": action_data,
        }

        self.user_repo.log_agent_event(
            user_id=user.id,
            intent=intent,
            status=wf_status,
        )

        return AssistantResponse(
            intent=intent,
            response=response_text,
            status=wf_status,  # type: ignore[arg-type]
            action_id=action_id,
            action_data=action_data,
        )

    def get_action_status(self, action_id: str) -> ActionStatusResponse:
        record = _ACTION_STORE.get(action_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Əməliyyat tapılmadı.",
            )
        return ActionStatusResponse(**record)

    def confirm_action(self, action_id: str) -> ActionStatusResponse:
        record = _ACTION_STORE.get(action_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Təsdiqlənəcək əməliyyat tapılmadı.",
            )

        if record["status"] == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ləğv edilmiş əməliyyat təsdiqlənə bilməz.",
            )

        intent = record["intent"]
        action_data = dict(record.get("action_data") or {})
        user_id = record.get("user_id") or DEFAULT_USER_ID

        if intent == "CREATE_REMINDER":
            scheduled_str = action_data.get("scheduled_at")
            scheduled_dt = (
                datetime.fromisoformat(scheduled_str)
                if isinstance(scheduled_str, str)
                else datetime.now()
            )
            title = action_data.get("title") or "Xatırlatma"
            timezone_str = action_data.get("timezone") or "Asia/Baku"

            reminder = self.reminder_repo.create(
                user_id=user_id,
                data=ReminderCreate(
                    title=title,
                    scheduled_at=scheduled_dt,
                    timezone=timezone_str,
                ),
            )
            action_data["reminder_id"] = reminder.id
            action_data["notification"] = (
                LocalNotificationFormatter.build_reminder_notification(
                    reminder_id=reminder.id,
                    title=reminder.title,
                    scheduled_at=reminder.scheduled_at,
                    timezone=reminder.timezone,
                )
            )
            when = format_az_datetime(reminder.scheduled_at)
            record["response"] = f'"{title}" xatırlatması yaradıldı. {when[:1].upper()}{when[1:]} sizə xatırladacağam.'
        elif intent == "MAKE_CALL":
            alias = action_data.get("contact_alias", "kontakt")
            action_data["authorized_execution"] = "OPEN_DIALER"
            record["response"] = f'"{alias}" üçün zəng təsdiqləndi. Nömrə yığıcı açılır.'
        elif intent in ORDER_INTENTS:
            order = action_data.get("order") or {}
            action_data["authorized_execution"] = "SIMULATED_ORDER"
            record["response"] = order.get("done_text") or "Sifarişiniz qəbul olundu."
        elif intent == "SEND_VOICE_MESSAGE":
            alias = action_data.get("contact_alias", "kontakt")
            action_data["authorized_execution"] = "SEND_VOICE_MESSAGE"
            record["response"] = f'"{alias}" üçün səsli mesaj təsdiqləndi.'
        else:
            record["response"] = "Əməliyyat təsdiqləndi və icra olundu."

        record["status"] = "completed"
        record["action_data"] = action_data

        self.user_repo.log_agent_event(
            user_id=user_id,
            intent=intent,
            status="completed",
        )
        return ActionStatusResponse(**record)

    def cancel_action(self, action_id: str) -> ActionStatusResponse:
        record = _ACTION_STORE.get(action_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ləğv ediləcək əməliyyat tapılmadı.",
            )

        record["status"] = "cancelled"
        record["response"] = "Əməliyyat istifadəçi tərəfindən ləğv edildi."

        self.user_repo.log_agent_event(
            user_id=record.get("user_id") or DEFAULT_USER_ID,
            intent=record.get("intent") or "UNKNOWN",
            status="cancelled",
        )
        return ActionStatusResponse(**record)

