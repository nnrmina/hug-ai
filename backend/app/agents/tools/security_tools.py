from typing import Dict, Any
from app.integrations.llm.provider import get_rule_adapter


def analyze_message(message: str) -> Dict[str, Any]:
    """Analyze a user-provided message for potential scam/phishing indicators (Section 9.5 & 12.3)."""
    adapter = get_rule_adapter()
    result = adapter.analyze_security_text(message)
    return {
        "action_type": "ANALYZE_MESSAGE",
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
        "indicators": result["indicators"],
        "explanation": result["explanation"],
        "recommendation": result["recommendation"],
    }

