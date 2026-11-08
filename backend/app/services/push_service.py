"""Web Push delivery (VAPID). Free, works with the app closed (Android Chrome; iOS 16.4+
when installed to the home screen). Dead subscriptions are pruned automatically."""
import json
from functools import lru_cache
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.care import FamilyMember, PushSubscription


def push_enabled() -> bool:
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


@lru_cache
def _vapid():
    from py_vapid import Vapid02

    return Vapid02.from_raw(settings.VAPID_PRIVATE_KEY.encode())


def save_subscription(db: Session, sub: Dict[str, Any], owner_type: str, owner_id: str) -> PushSubscription:
    endpoint = sub["endpoint"]
    keys = sub.get("keys") or {}
    row = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if row is None:
        row = PushSubscription(endpoint=endpoint, p256dh=keys["p256dh"], auth=keys["auth"],
                               owner_type=owner_type, owner_id=owner_id)
        db.add(row)
    else:  # same browser re-subscribed or changed owner
        row.p256dh, row.auth, row.owner_type, row.owner_id = keys["p256dh"], keys["auth"], owner_type, owner_id
    db.commit()
    return row


def _send(db: Session, subs: List[PushSubscription], payload: Dict[str, Any]) -> int:
    if not push_enabled() or not subs:
        return 0
    from pywebpush import WebPushException, webpush

    sent = 0
    data = json.dumps(payload, ensure_ascii=False)
    for s in subs:
        try:
            webpush(
                subscription_info={"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                data=data,
                vapid_private_key=_vapid(),
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                ttl=3600,
                timeout=10,
                headers={"Urgency": "high"},
            )
            sent += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):  # subscription expired / unsubscribed
                db.delete(s)
                db.commit()
            else:
                logger.warning("push failed (%s): %s", status, str(exc)[:200])
        except Exception as exc:  # network etc. — never break the caller
            logger.warning("push error: %s", str(exc)[:200])
    return sent


def push_to_elder(db: Session, user_id: str, payload: Dict[str, Any]) -> int:
    subs = db.query(PushSubscription).filter(
        PushSubscription.owner_type == "elder", PushSubscription.owner_id == user_id
    ).all()
    return _send(db, subs, payload)


def push_to_family(db: Session, user_id: str, payload: Dict[str, Any],
                   exclude_member: Optional[str] = None) -> int:
    sent = 0
    for member in db.query(FamilyMember).filter(FamilyMember.user_id == user_id).all():
        if member.id == exclude_member:
            continue
        subs = db.query(PushSubscription).filter(
            PushSubscription.owner_type == "family", PushSubscription.owner_id == member.id
        ).all()
        personal = dict(payload)
        if personal.get("url") == "/f/":  # each relative opens their own private family page
            personal["url"] = f"/f/{member.invite_token}"
        sent += _send(db, subs, personal)
    return sent
