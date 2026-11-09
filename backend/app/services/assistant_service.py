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
from app.services.care_service import CareService
from app.core.i18n import pick
from app.services import weather_service
from app.utils.datetime_utils import format_datetime

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
            lat=request.lat,
            lon=request.lon,
        )

    def process_turn(
        self,
        text: Optional[str] = None,
        audio: Optional[bytes] = None,
        mime_type: Optional[str] = None,
        session_id: Optional[str] = None,
        client_history: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[str] = None,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
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

        lang = action_data.get("lang") or "az"

        # Side effects that need no confirmation
        if wf_status == "completed" and intent == "MEDICATION_TAKEN":
            dose = CareService(self.db).mark_taken(user.id)
            if dose:
                action_data["dose_id"] = dose.id
                response_text = pick(lang, "Əla, qeyd etdim! Sağlam olun.", "Отлично, отметила! Будьте здоровы.")
            else:
                response_text = pick(lang, "Hazırda içiləsi dərman görmürəm, amma qeyd etdim. Sağlam olun.",
                                     "Сейчас я не вижу лекарств по расписанию, но отметила. Будьте здоровы.")
        elif wf_status == "completed" and intent == "CHECKIN":
            CareService(self.db).record_checkin(user.id, action_data.get("mood", "ok"), transcript)
        elif wf_status == "completed" and intent == "WEATHER":
            response_text, weather = weather_service.weather_reply(
                lat, lon, action_data.get("weather_day") or "today", lang)
            if weather:
                action_data["weather"] = weather
        elif wf_status == "completed" and intent == "LOG_HEALTH":
            care = CareService(self.db)
            try:
                row, sent = care.add_reading(user.id, action_data.get("health_kind") or "",
                                             float(action_data.get("health_value") or 0),
                                             action_data.get("health_value2"))
                response_text = care.reading_reply(row, lang, notified_count=sent)
                action_data["reading"] = care.readings(user.id, 1)[0]
                action_data["notified_devices"] = sent
            except HTTPException:
                response_text = pick(lang, "Bu göstəricini düzgün eşitmədim. Bir daha deyə bilərsiniz?",
                                     "Я не расслышала показатель. Повторите, пожалуйста.")
                wf_status = "needs_clarification"
        elif wf_status == "completed" and intent == "HEALTH_QUERY":
            response_text = CareService(self.db).health_summary(user.id, lang)

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
            lang=lang,
            next_step=action_data.get("next_step") if wf_status in ("completed", "needs_confirmation") else None,
            action_token=sign_action(_ACTION_STORE[action_id]) if wf_status == "needs_confirmation" else None,
        )

    def _load_action(self, action_id: str, action_token: Optional[str], missing_detail: str,
                     owner_id: Optional[str] = None) -> Dict[str, Any]:
        """Find a pending action in memory, or rebuild it from its signed token.
        An action can only be confirmed/cancelled by the device that created it."""
        record = self._lookup(action_id, action_token, missing_detail)
        if owner_id is not None and record.get("user_id") not in (owner_id, None):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=missing_detail)
        return record

    def _lookup(self, action_id: str, action_token: Optional[str], missing_detail: str) -> Dict[str, Any]:
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

    def confirm_action(self, action_id: str, action_token: Optional[str] = None,
                       owner_id: Optional[str] = None) -> ActionStatusResponse:
        record = self._load_action(action_id, action_token, "Təsdiqlənəcək əməliyyat tapılmadı.", owner_id)

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
        lang = action_data.get("lang") or "az"

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
            when = format_datetime(reminder.scheduled_at, lang)
            when = f"{when[:1].upper()}{when[1:]}"
            record["response"] = pick(lang, f'"{title}" xatırlatması yaradıldı. {when} sizə xatırladacağam.',
                                      f"Напоминание «{title}» создано. {when} я Вам напомню.")
        elif intent == "MAKE_CALL":
            alias = action_data.get("contact_alias", "kontakt")
            action_data["authorized_execution"] = "OPEN_DIALER"
            record["response"] = pick(lang, f'"{alias}" üçün zəng təsdiqləndi. Nömrə yığıcı açılır.',
                                      "Звоню.")
        elif intent == "CREATE_MEDICATION":
            med = CareService(self.db).add_medication(
                user_id, action_data.get("title") or "Dərman", action_data.get("med_times") or []
            )
            action_data["medication_id"] = med.id
            times = med.times.split(",")
            record["response"] = pick(lang, f"Hazırdır! “{med.name}” üçün hər gün saat {' və '.join(times)}-da xatırladacağam.",
                                      f"Готово! Буду напоминать про «{med.name}» каждый день в {' и '.join(times)}.")
        elif intent in ORDER_INTENTS:
            order = action_data.get("order") or {}
            action_data["authorized_execution"] = "SIMULATED_ORDER"
            record["response"] = order.get("done_text") or pick(lang, "Sifarişiniz qəbul olundu.", "Ваш заказ принят.")
        elif intent == "SEND_VOICE_MESSAGE":
            action_data["authorized_execution"] = "OPEN_SMS_COMPOSER"
            record["response"] = pick(lang, "Mesajınız hazırdır. Göndərmək üçün mesajlar tətbiqi açılır.",
                                      "Сообщение готово. Открываю приложение сообщений.")
        else:
            record["response"] = pick(lang, "Əməliyyat təsdiqləndi və icra olundu.", "Готово.")

        record["status"] = "completed"
        record["action_data"] = action_data

        self.user_repo.log_agent_event(
            user_id=user_id,
            intent=intent,
            status="completed",
        )
        return ActionStatusResponse(**record)

    def cancel_action(self, action_id: str, action_token: Optional[str] = None,
                      owner_id: Optional[str] = None) -> ActionStatusResponse:
        record = self._load_action(action_id, action_token, "Ləğv ediləcək əməliyyat tapılmadı.", owner_id)
        if record["status"] == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Artıq icra olunmuş əməliyyat ləğv edilə bilməz.",
            )

        record["status"] = "cancelled"
        record["response"] = pick((record.get("action_data") or {}).get("lang"),
                                  "Əməliyyat istifadəçi tərəfindən ləğv edildi.", "Действие отменено.")

        self.user_repo.log_agent_event(
            user_id=record.get("user_id") or DEFAULT_USER_ID,
            intent=record.get("intent") or "UNKNOWN",
            status="cancelled",
        )
        return ActionStatusResponse(**record)

