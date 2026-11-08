from typing import Dict, Any


def prepare_contact_lookup(
    contact_alias: str,
    operation: str = "MAKE_CALL",
) -> Dict[str, Any]:
    """Prepare on-device contact lookup instruction for Flutter (Section 9.5 & 11.5).
    Contacts are NEVER uploaded to or searched on the backend server.
    """
    return {
        "action_type": "CONTACT_LOOKUP",
        "operation": operation,
        "contact_alias": contact_alias,
        "local_only": True,
        "requires_confirmation": True,
    }

