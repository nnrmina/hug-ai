import re
from typing import Optional

from fastapi import Header

from app.models.user import DEFAULT_USER_ID

_DEVICE_RE = re.compile(r"^[A-Za-z0-9-]{16,64}$")


def device_user_id(x_hug_device: Optional[str] = Header(default=None)) -> str:
    """Anonymous per-phone identity: the app generates a random id once and sends it as
    `X-HUG-Device`. No login; each phone sees only its own reminders, medicines and family.
    Requests without it (old clients, tests) fall back to the shared default user."""
    if x_hug_device and _DEVICE_RE.match(x_hug_device):
        return x_hug_device.lower()
    return DEFAULT_USER_ID
