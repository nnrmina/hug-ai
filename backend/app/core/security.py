from typing import Dict, Any

# Action risk level definitions based on Section 12.2 of the Technical Specification
ACTION_RISK_POLICY: Dict[str, Dict[str, Any]] = {
    "GENERAL_QUESTION": {
        "risk_level": "low",
        "requires_confirmation": False,
        "allowed_in_mvp": True,
    },
    "ANALYZE_MESSAGE": {
        "risk_level": "low",
        "requires_confirmation": False,
        "allowed_in_mvp": True,
    },
    "CREATE_REMINDER": {
        "risk_level": "low_medium",
        "requires_confirmation": True,
        "allowed_in_mvp": True,
    },
    "CONTACT_LOOKUP": {
        "risk_level": "medium",
        "requires_confirmation": True,
        "allowed_in_mvp": True,
    },
    "MAKE_CALL": {
        "risk_level": "medium",
        "requires_confirmation": True,
        "allowed_in_mvp": True,
    },
    "SEND_VOICE_MESSAGE": {
        "risk_level": "medium_high",
        "requires_confirmation": True,
        "allowed_in_mvp": True,
    },
    "EMERGENCY_CALL": {
        "risk_level": "high",
        "requires_confirmation": True,
        "allowed_in_mvp": True,
    },
    "UNKNOWN": {
        "risk_level": "low",
        "requires_confirmation": False,
        "allowed_in_mvp": True,
    },
    "BANK_TRANSFER": {
        "risk_level": "high",
        "requires_confirmation": True,
        "allowed_in_mvp": False,
        "reason": "Real bank əməliyyatları və pul köçürmələri təhlükəsizlik səbəbindən MVP-də dəstəklənmir.",
    },
    "WOLT_ORDER": {
        "risk_level": "high",
        "requires_confirmation": True,
        "allowed_in_mvp": False,
        "simulated": True,
        "reason": "Real Wolt sifarişi MVP-də deaktivdir (yalnız simulyasiya rejimindədir).",
    },
    "MEDICAL_DECISION": {
        "risk_level": "high",
        "requires_confirmation": True,
        "allowed_in_mvp": False,
        "reason": "YAXIN AI tibbi məsləhət və ya müalicə qərarı vermir, yalnız dərman vaxtı xatırlatması yarada bilər.",
    },
}

# Disallowed device data scopes per Privacy Architecture (Section 12)
FORBIDDEN_DATA_SCOPES = {
    "sms_auto_read",
    "whatsapp_messages",
    "photo_gallery",
    "call_history",
    "gps_live_tracking",
    "contact_cloud_sync",
}


def check_action_permission(action_type: str) -> Dict[str, Any]:
    """Verify whether an action is permitted in MVP and whether confirmation is required."""
    policy = ACTION_RISK_POLICY.get(
        action_type,
        {
            "risk_level": "medium",
            "requires_confirmation": True,
            "allowed_in_mvp": True,
        },
    )
    return {
        "action_type": action_type,
        "allowed": policy.get("allowed_in_mvp", False),
        "requires_confirmation": policy.get("requires_confirmation", True),
        "risk_level": policy.get("risk_level", "medium"),
        "simulated": policy.get("simulated", False),
        "reason": policy.get("reason"),
    }

