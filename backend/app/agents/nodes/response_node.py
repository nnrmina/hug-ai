from app.agents.state import AgentState
from app.core.security import check_action_permission
from app.agents.tools.order_tools import ORDER_INTENTS
from app.core.i18n import pick
from app.utils.datetime_utils import format_datetime

RISK_LEVEL_AZ = {"high": "yüksək", "medium": "orta", "low": "aşağı"}
RISK_LEVEL_RU = {"high": "высокий", "medium": "средний", "low": "низкий"}

CAPABILITIES_TEXT = (
    "Yaxınlarınıza zəng edə, xatırlatma yarada, Wolt-dan yemək, dərman və ya taksi sifariş edə, "
    "şübhəli mesajları yoxlaya, hava proqnozunu deyə, ən yaxın apteki tapa və təzyiqinizi qeyd edə bilərəm."
)
CAPABILITIES_TEXT_RU = (
    "Я могу позвонить близким, поставить напоминание, заказать еду, лекарства или такси, "
    "проверить подозрительное сообщение, рассказать о погоде, найти ближайшую аптеку и записать давление."
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
    """Generate the final spoken reply (Azerbaijani, or Russian when the user spoke Russian)."""
    intent = state.get("intent") or "UNKNOWN"
    action_data = state.get("action_data") or {}
    status = state.get("status")
    lang = action_data.get("lang") or "az"

    def reply(text: str, st: str) -> AgentState:
        return {**state, "response": text, "status": st}

    if status == "rejected":
        reason = (
            action_data.get("reason")
            or action_data.get("permission", {}).get("reason")
            or "Bu əməliyyat təhlükəsizlik qaydalarına görə icra edilə bilməz."
        )
        if lang == "ru":
            reason = "К сожалению, это действие я выполнить не могу из соображений безопасности."
        return reply(reason, "rejected")

    if status == "needs_clarification" and action_data.get("clarification_question"):
        return reply(action_data["clarification_question"], "needs_clarification")

    if intent == "MAKE_CALL":
        alias = action_data.get("contact_alias", "kontakt")
        return reply(pick(lang,
                          f'"{alias}" kontaktına zəng etmək istəyirsiniz? Təsdiqlədikdən sonra zəng ekranda açılacaq.',
                          f"Позвонить контакту «{alias}»?"), "needs_confirmation")

    if intent == "SEND_VOICE_MESSAGE":
        alias = action_data.get("contact_alias", "kontakt")
        return reply(pick(lang, f'"{alias}" kontaktına səsli mesaj göndərməyi təsdiqləyirsiniz?',
                          f"Отправить сообщение контакту «{alias}»?"), "needs_confirmation")

    if intent == "CREATE_REMINDER":
        title = action_data.get("title", "Xatırlatma")
        when = format_datetime(action_data.get("scheduled_at", ""), lang)
        return reply(pick(lang, f'{when[:1].upper()}{when[1:]} üçün "{title}" xatırlatması yaradılsın?',
                          f"Создать напоминание «{title}» на {when}?"), "needs_confirmation")

    if intent in ORDER_INTENTS:
        order = action_data.get("order") or {}
        return reply(order.get("confirm_text") or pick(lang, "Sifariş təsdiqlənsin?", "Подтвердить заказ?"),
                     "needs_confirmation")

    if intent == "ANALYZE_MESSAGE":
        explanation = action_data.get("explanation", "Mesaj analiz edildi.")
        recommendation = action_data.get("recommendation", "")
        level = action_data.get("risk_level", "low")
        if lang == "ru":
            text = f"Уровень риска: {RISK_LEVEL_RU.get(level, 'низкий')}. {explanation} Совет: {recommendation}"
        else:
            text = f"Risk səviyyəsi: {RISK_LEVEL_AZ.get(level, 'aşağı')}. {explanation} Tövsiyə: {recommendation}"
        return reply(text.strip(), "completed")

    if intent == "EMERGENCY":
        return reply(pick(lang, "Narahat olmayın, kömək çağırıram. Ailənizə dərhal xəbər verirəm.",
                          "Не волнуйтесь, я зову помощь. Сразу сообщаю Вашей семье."), "completed")

    if intent == "CREATE_MEDICATION":
        title = action_data.get("title", "Dərman")
        spoken = pick(lang, " və ", " и ").join(action_data.get("med_times") or [])
        return reply(pick(lang, f"“{title}” üçün hər gün saat {spoken}-da xatırladım?",
                          f"Напоминать про «{title}» каждый день в {spoken}?"), "needs_confirmation")

    if intent == "MEDICATION_TAKEN":
        return reply(pick(lang, "Qeyd etdim.", "Отметила."), "completed")

    if intent == "CHECKIN":
        mood = action_data.get("mood", "ok")
        mood = mood if mood in ("good", "ok", "bad") else "ok"
        default = {
            "good": pick(lang, "Buna çox sevindim! Gününüz xoş keçsin.", "Очень рада! Хорошего Вам дня."),
            "ok": pick(lang, "Anladım. Bir şey lazım olsa, mənə deyin.", "Поняла. Если что-то понадобится — скажите мне."),
            "bad": pick(lang, "Çox təəssüf. Ailənizə xəbər verirəm ki, sizə zəng etsinlər.",
                        "Мне очень жаль. Сообщу семье, чтобы Вам позвонили."),
        }[mood]
        return reply(action_data.get("answer") or default, "completed")

    if intent == "WEATHER":
        # The real forecast is filled in by AssistantService (needs network + location)
        return reply(pick(lang, "Hava proqnozuna baxıram...", "Смотрю прогноз погоды..."), "completed")

    if intent == "FIND_PLACE":
        hospital = action_data.get("place_type") == "hospital"
        return reply(pick(lang,
                          "Ən yaxın xəstəxanaları axtarıram..." if hospital else "Ən yaxın aptekləri axtarıram...",
                          "Ищу ближайшие больницы..." if hospital else "Ищу ближайшие аптеки..."), "completed")

    if intent == "OPEN_SCREEN":
        return reply(pick(lang, "Açıram.", "Открываю."), "completed")

    if intent in ("LOG_HEALTH", "HEALTH_QUERY"):
        # Saved and phrased by AssistantService (needs the database)
        return reply(pick(lang, "Qeyd etdim.", "Записала."), "completed")

    if intent == "GENERAL_QUESTION":
        if action_data.get("answer"):
            return reply(action_data["answer"], "completed")
        if lang == "ru":
            return reply("Здравствуйте! Чем я могу помочь? " + CAPABILITIES_TEXT_RU, "completed")
        is_greeting = "salam" in (state.get("user_message") or "").lower()
        prefix = "Salam! Sizə necə kömək edə bilərəm? " if is_greeting else "Mən sizin səsli köməkçinizəm. "
        return reply(prefix + CAPABILITIES_TEXT, "completed")

    return reply(pick(lang,
                      "Bağışlayın, sizi tam başa düşmədim. "
                      "Məsələn belə deyə bilərsiniz: “Qızıma zəng et” və ya “Sabah saat 10-da dərmanımı xatırlat”.",
                      "Извините, я Вас не совсем поняла. Например, скажите: «Позвони дочке» "
                      "или «Напомни завтра в 10 выпить лекарство»."), "needs_clarification")
