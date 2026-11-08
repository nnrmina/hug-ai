from app.agents.state import AgentState
from app.agents.tools.security_tools import analyze_message

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def security_node(state: AgentState) -> AgentState:
    """Analyze suspicious message and extract risk indicators (MVP 03 - Digital Shield Agent).

    The rule-based baseline always runs; when Gemini also judged the message, the two are
    merged conservatively: the higher risk wins, indicators are combined, and Gemini's
    clearer explanation is preferred.
    """
    action_data = dict(state.get("action_data") or {})
    message_text = action_data.get("message_to_analyze") or state["user_message"]

    result = analyze_message(message_text)
    llm = action_data.pop("llm_security", None)
    if llm:
        rule_level = result["risk_level"]
        llm_level = llm.get("risk_level", "low")
        if _RISK_ORDER.get(llm_level, 0) > _RISK_ORDER.get(rule_level, 0):
            result["risk_level"] = llm_level
        result["risk_score"] = max(int(result["risk_score"]), int(llm.get("risk_score", 0)))
        result["indicators"] = list(dict.fromkeys([*result["indicators"], *llm.get("indicators", [])]))
        # Only adopt Gemini's wording when it does not understate the final risk level
        if llm.get("explanation") and llm_level == result["risk_level"]:
            result["explanation"] = llm["explanation"]
            result["recommendation"] = llm.get("recommendation") or result["recommendation"]
        result["sources"] = ["rules", "gemini"]

    return {
        **state,
        "action_data": {**action_data, **result},
        "requires_confirmation": False,
        "confirmation_status": "not_required",
    }
