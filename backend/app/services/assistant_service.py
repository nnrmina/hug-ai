import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.agents.graph import run_agent_workflow
from app.integrations.llm.provider import get_llm_adapter
from app.services.action_tokens import sign_action, verify_action
from app.services.session_store import session_store
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
        return self.process_turn(
            text=request.message,
            session_id=request.session_id,
            client_history=[h.model_dump() for h in request.history],
            user_id=request.user_id,
        )

    def process_turn(
        self,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        session_id: Optional[str] = None,
        client_history: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
    ) -> AssistantResponse:
        """One conversational turn: understand (Gemini or rules) → agent graph → reply."""
        user = self.user_repo.get_or_create_default_user(user_id or DEFAULT_USER_ID)
        history = session_store.get(session_id) or list(client_history or [])

        parsed = get_llm_adapter().understand(
            text=text, audio=audio, mime_type=mime_type, history=history
        )
        engine = parsed.get("engine")
        transcript = (parsed.get("transcript") or text or "").strip()

        if parsed.get("stt_failed") or not transcript:
            reply = parsed.get("clarification_question") or "Sizi eşidə bilmədim. Bir daha deyə bilərsiniz?"
            return AssistantResponse(
                intent="UNKNOWN",
                response=reply,
                status="needs_clarification",
                action_data={"stt_failed": True, "engine": engine},
                transcript=transcript,
                engine=engine,
            )

        final_state = run_agent_workflow(
            user_id=user.id, user_message=transcript, llm_parsed=parsed
        )
        intent = final_state.get("intent") or "UNKNOWN"
        wf_status = final_state.get("status") or "needs_clarification"
        response_text = final_state.get("response") or ""
        action_data = dict(final_state.get("action_data") or {})
        action_data.pop("transcript", None)

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

        pending = None
        if wf_status == "needs_clarification" and intent != "UNKNOWN":
            pending = {
                "intent": intent,
                "title": action_data.get("title"),
                "missing_slots": action_data.get("missing_slots") or [],
            }
        session_store.append(
            session_id,
            {
                "user": transcript,
                "assistant": response_text,
                "intent": intent,
                "status": wf_status,
                "pending": pending,
            },
        )

        return AssistantResponse(
            intent=intent,
            response=response_text,
            status=wf_status,  # type: ignore[arg-type]
            action_id=action_id,
            action_data=action_data,
            transcript=transcript,
            engine=engine,
            action_token=sign_action(_ACTION_STORE[action_id]) if wf_status == "needs_confirmation" else None,
        )

    def _load_action(self, action_id: str, action_token: Optional[str], missing_detail: str) -> Dict[str, Any]:
        """Find a pending action in memory, or rebuild it from its signed token."""
        record = _ACTION_STORE.get(action_id)
        if record:
            return record
        signed = verify_action(action_token, action_id)
        if not signed:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
        record = {
            "action_id": action_id,
            "user_id": signed.get("user_id") or DEFAULT_USER_ID,
            "intent": signed["intent"],
            "status": "needs_confirmation",
            "response": "",
            "action_data": signed.get("action_data") or {},
        }
        _ACTION_STORE[action_id] = record
        return record

    def get_action_status(self, action_id: str) -> ActionStatusResponse:
        record = _ACTION_STORE.get(action_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Əməliyyat tapılmadı.",
            )
        return ActionStatusResponse(**record)

    def confirm_action(self, action_id: str, action_token: Optional[str] = None) -> ActionStatusResponse:
        record = self._load_action(action_id, action_token, "Təsdiqlənəcək əməliyyat tapılmadı.")

        if record["status"] == "completed":
            return ActionStatusResponse(**record)  # idempotent: never create a reminder twice

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
            action_data["authorized_execution"] = "OPEN_SMS_COMPOSER"
            record["response"] = "Mesajınız hazırdır. Göndərmək üçün mesajlar tətbiqi açılır."
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

    def cancel_action(self, action_id: str, action_token: Optional[str] = None) -> ActionStatusResponse:
        record = self._load_action(action_id, action_token, "Ləğv ediləcək əməliyyat tapılmadı.")
        if record["status"] == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artıq icra olunmuş əməliyyat ləğv edilə bilməz.",
            )

        record["status"] = "cancelled"
        record["response"] = "Əməliyyat istifadəçi tərəfindən ləğv edildi."

        self.user_repo.log_agent_event(
            user_id=record.get("user_id") or DEFAULT_USER_ID,
            intent=record.get("intent") or "UNKNOWN",
            status="cancelled",
        )
        return ActionStatusResponse(**record)

