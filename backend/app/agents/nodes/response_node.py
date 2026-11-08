from app.agents.state import AgentState
from app.core.security import check_action_permission
from app.agents.tools.order_tools import ORDER_INTENTS
from app.utils.datetime_utils import format_az_datetime

RISK_LEVEL_AZ = {"high": "yüksək", "medium": "orta", "low": "aşağı"}

CAPABILITIES_TEXT = (
    "Yaxınlarınıza zəng edə, xatırlatma yarada, Wolt-dan yemək, dərman və ya taksi sifariş edə, "
    "şübhəli mesajları yoxlaya bilərəm."
)


def validation_node(state: AgentState) -> AgentState:
    """Check action permissions and business rules (Section 9.6 & 12.2)."""
    action_data = dict(state.get("action_data") or {})
    blocked_action = action_data.get("blocked_action")
    target_action = blocked_action or state.get("intent") or "UNKNOWN"

    permission = check_action_permission(target_action)
    action_data["permission"] = permission

    if not permission["allowed"]:
        return {
            **state,
            "action_data": action_data,
            "requires_confirmation": False,
            "confirmation_status": "rejected",
            "status": "rejected",
        }

    return {
        **state,
        "action_data": action_data,
        "requires_confirmation": state.get(
            "requires_confirmation", permission["requires_confirmation"]
        ),
    }


def confirmation_node(state: AgentState) -> AgentState:
    """Human-in-the-loop confirmation gate (Section 9.6)."""
    if state.get("status") in ("rejected", "needs_clarification"):
        return state

    if state.get("requires_confirmation"):
        return {
            **state,
            "confirmation_status": "waiting_for_user",
            "status": "needs_confirmation",
        }

    return {
        **state,
        "confirmation_status": "approved",
        "status": "completed",
    }


def response_node(state: AgentState) -> AgentState:
    """Generate final Azerbaijani response for the user based on workflow state."""
    intent = state.get("intent") or "UNKNOWN"
    action_data = state.get("action_data") or {}
    status = state.get("status")

    if status == "rejected":
        reason = (
            action_data.get("reason")
            or action_data.get("permission", {}).get("reason")
            or "Bu əməliyyat təhlükəsizlik qaydalarına görə icra edilə bilməz."
        )
        return {
            **state,
            "response": reason,
            "status": "rejected",
        }

    if status == "needs_clarification" and action_data.get("clarification_question"):
        return {
            **state,
            "response": action_data["clarification_question"],
            "status": "needs_clarification",
        }

    if intent == "MAKE_CALL":
        alias = action_data.get("contact_alias", "kontakt")
        return {
            **state,
            "response": f'"{alias}" kontaktına zəng etmək istəyirsiniz? Təsdiqlədikdən sonra zəng ekranda açılacaq.',
            "status": "needs_confirmation",
        }

    if intent == "SEND_VOICE_MESSAGE":
        alias = action_data.get("contact_alias", "kontakt")
        return {
            **state,
            "response": f'"{alias}" kontaktına səsli mesaj göndərməyi təsdiqləyirsiniz?',
            "status": "needs_confirmation",
        }

    if intent == "CREATE_REMINDER":
        title = action_data.get("title", "Xatırlatma")
        when = format_az_datetime(action_data.get("scheduled_at", ""))
        return {
            **state,
            "response": f'{when[:1].upper()}{when[1:]} üçün "{title}" xatırlatması yaradılsın?',
            "status": "needs_confirmation",
        }

    if intent in ORDER_INTENTS:
        order = action_data.get("order") or {}
        return {
            **state,
            "response": order.get("confirm_text") or "Sifariş təsdiqlənsin?",
            "status": "needs_confirmation",
        }

    if intent == "ANALYZE_MESSAGE":
        explanation = action_data.get("explanation", "Mesaj analiz edildi.")
        recommendation = action_data.get("recommendation", "")
        risk_level = RISK_LEVEL_AZ.get(action_data.get("risk_level", "low"), "aşağı")
        return {
            **state,
            "response": f"Risk səviyyəsi: {risk_level}. {explanation} Tövsiyə: {recommendation}".strip(),
            "status": "completed",
        }

    if intent == "EMERGENCY":
        return {
            **state,
            "response": "Narahat olmayın, kömək çağırıram. Ailənizə dərhal xəbər verirəm.",
            "status": "completed",
        }

    if intent == "CREATE_MEDICATION":
        title = action_data.get("title", "Dərman")
        times = action_data.get("med_times") or []
        spoken = " və ".join(times)
        return {
            **state,
            "response": f"“{title}” üçün hər gün saat {spoken}-da xatırladım?",
            "status": "needs_confirmation",
        }

    if intent == "MEDICATION_TAKEN":
        return {**state, "response": "Qeyd etdim.", "status": "completed"}

    if intent == "CHECKIN":
        mood = action_data.get("mood", "ok")
        default = {
            "good": "Buna çox sevindim! Gününüz xoş keçsin.",
            "ok": "Anladım. Bir şey lazım olsa, mənə deyin.",
            "bad": "Çox təəssüf. Ailənizə xəbər verirəm ki, sizə zəng etsinlər.",
        }[mood if mood in ("good", "ok", "bad") else "ok"]
        return {**state, "response": action_data.get("answer") or default, "status": "completed"}

    if intent == "GENERAL_QUESTION":
        if action_data.get("answer"):
            return {**state, "response": action_data["answer"], "status": "completed"}
        is_greeting = "salam" in (state.get("user_message") or "").lower()
        prefix = "Salam! Sizə necə kömək edə bilərəm? " if is_greeting else "Mən sizin səsli köməkçinizəm. "
        return {
            **state,
            "response": prefix + CAPABILITIES_TEXT,
            "status": "completed",
        }

    return {
        **state,
        "response": (
            "Bağışlayın, sizi tam başa düşmədim. "
            "Məsələn belə deyə bilərsiniz: “Qızıma zəng et” və ya “Sabah saat 10-da dərmanımı xatırlat”."
        ),
        "status": "needs_clarification",
    }

