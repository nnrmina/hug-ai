from app.agents.state import AgentState
from app.core.security import check_action_permission


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
    if state.get("status") == "rejected":
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
        scheduled_at = action_data.get("scheduled_at", "")
        return {
            **state,
            "response": f'"{title}" üçün ({scheduled_at}) vaxtına xatırlatma yaradılsın?',
            "status": "needs_confirmation",
        }

    if intent == "ANALYZE_MESSAGE":
        explanation = action_data.get("explanation", "Mesaj analiz edildi.")
        recommendation = action_data.get("recommendation", "")
        risk_level = action_data.get("risk_level", "low").upper()
        return {
            **state,
            "response": f"[Risk: {risk_level}] {explanation} Tövsiyə: {recommendation}".strip(),
            "status": "completed",
        }

    if intent == "GENERAL_QUESTION":
        return {
            **state,
            "response": (
                "Mən YAXIN AI-yəm — Azərbaycan dilində səsli köməkçiniz. "
                "Sizə yaxınlarınıza zəng etməkdə, xatırlatma yaratmaqda və şübhəli mesajları yoxlamaqda kömək edə bilərəm."
            ),
            "status": "completed",
        }

    return {
        **state,
        "response": (
            f'Mesajınızı aldım: "{state.get("user_message", "")}". '
            "Zəhmət olmasa nə etmək istədiyinizi dəqiqləşdirin (məsələn: \"Qızıma zəng et\", \"Sabah saat 9-da məni oyat\" və ya \"Bu mesajı yoxla\")."
        ),
        "status": "needs_clarification",
    }

