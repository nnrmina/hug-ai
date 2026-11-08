from typing import TypedDict, Optional, Dict, Any


class AgentState(TypedDict):
    """State structure managed across LangGraph nodes (Section 9.2)."""

    user_id: str
    user_message: str
    intent: Optional[str]
    confidence: Optional[float]
    action_data: Optional[Dict[str, Any]]
    requires_confirmation: bool
    confirmation_status: Optional[str]
    response: Optional[str]
    status: Optional[str]
    # Pre-computed understanding (Gemini or rule-based) for this turn; when present the
    # intent node uses it instead of re-parsing the text. Declared here because LangGraph
    # drops state keys that are not part of the schema.
    llm_parsed: Optional[Dict[str, Any]]

