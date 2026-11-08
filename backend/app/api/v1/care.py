"""Care API: profile, family circle, medicines, daily check-in, SOS, push subscriptions,
and the token-based family view (no login: the private link is the credential)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import device_user_id
from app.core.config import settings
from app.core.database import get_db
from app.schemas.reminder import ReminderCreate
from app.repositories.reminder_repository import ReminderRepository
from app.services.care_service import CareService
from app.services.push_service import push_enabled, save_subscription

router = APIRouter()


# ---------------------------------------------------------------- schemas
class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    checkin_time: Optional[str] = Field(default=None, max_length=5)


class FamilyIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    relation: str = Field(default="", max_length=50)
    phone: str = Field(default="", max_length=30)


class MedicationIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    times: List[str] = Field(..., min_length=1, max_length=8)
    dose: str = Field(default="", max_length=80)


class SnoozeIn(BaseModel):
    minutes: int = Field(default=10, ge=1, le=120)


class CheckInIn(BaseModel):
    mood: str = Field(..., pattern="^(good|ok|bad)$")
    note: str = Field(default="", max_length=300)


class SosIn(BaseModel):
    lat: Optional[float] = Field(default=None, ge=-90, le=90)
    lon: Optional[float] = Field(default=None, ge=-180, le=180)
    accuracy: Optional[float] = None
    reason: str = Field(default="", max_length=300)


class PushSubIn(BaseModel):
    subscription: dict


class FamilyReminderIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    scheduled_at: str


def _member_out(svc: CareService, m) -> dict:
    return {"id": m.id, "name": m.name, "relation": m.relation, "phone": m.phone,
            "invite_url": svc.invite_url(m)}


# ---------------------------------------------------------------- elder (device)
@router.get("/care/state")
def care_state(uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    """Everything the home screen needs in one call."""
    svc = CareService(db)
    prof = svc.profile(uid)
    check = svc.checkin_today(uid)
    return {
        "profile": {"name": prof.name, "checkin_time": prof.checkin_time},
        "family": [_member_out(svc, m) for m in svc.family(uid)],
        "doses": svc.doses_today(uid),
        "medications": [{"id": m.id, "name": m.name, "dose": m.dose, "times": m.times.split(",")}
                        for m in svc.medications(uid)],
        "checkin": {"mood": check.mood} if check else None,
        "checkin_due": svc.checkin_due(uid),
        "push": {"enabled": push_enabled(), "public_key": settings.VAPID_PUBLIC_KEY},
    }


@router.put("/care/profile")
def update_profile(body: ProfileIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    prof = CareService(db).update_profile(uid, body.name, body.checkin_time)
    return {"name": prof.name, "checkin_time": prof.checkin_time}


@router.post("/care/family", status_code=status.HTTP_201_CREATED)
def add_family(body: FamilyIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    svc = CareService(db)
    return _member_out(svc, svc.add_family(uid, body.name, body.relation, body.phone))


@router.delete("/care/family/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family(member_id: str, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    CareService(db).delete_family(uid, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/care/medications", status_code=status.HTTP_201_CREATED)
def add_medication(body: MedicationIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    med = CareService(db).add_medication(uid, body.name, body.times, body.dose)
    return {"id": med.id, "name": med.name, "dose": med.dose, "times": med.times.split(",")}


@router.delete("/care/medications/{med_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_medication(med_id: str, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    CareService(db).remove_medication(uid, med_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/care/doses/today")
def doses_today(uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    return CareService(db).doses_today(uid)


@router.post("/care/doses/{dose_id}/taken")
def dose_taken(dose_id: str, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    dose = CareService(db).mark_taken(uid, dose_id)
    return {"id": dose.id, "status": dose.status}


@router.post("/care/doses/{dose_id}/snooze")
def dose_snooze(dose_id: str, body: SnoozeIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    dose = CareService(db).snooze(uid, dose_id, body.minutes)
    return {"id": dose.id, "status": dose.status}


@router.post("/care/checkin")
def checkin(body: CheckInIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    row = CareService(db).record_checkin(uid, body.mood, body.note)
    return {"day": row.day, "mood": row.mood}


@router.post("/care/sos")
def sos(body: SosIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    svc = CareService(db)
    ev, sent = svc.sos(uid, body.lat, body.lon, body.accuracy, body.reason)
    return {"id": ev.id, "notified_devices": sent,
            "family": [_member_out(svc, m) for m in svc.family(uid)]}


@router.post("/care/push/subscribe", status_code=status.HTTP_201_CREATED)
def elder_subscribe(body: PushSubIn, uid: str = Depends(device_user_id), db: Session = Depends(get_db)):
    if not push_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bildirişlər serverdə qurulmayıb.")
    CareService(db).profile(uid)
    save_subscription(db, body.subscription, "elder", uid)
    return {"ok": True}


# ---------------------------------------------------------------- family (token)
@router.get("/family/{token}")
def family_view(token: str, db: Session = Depends(get_db)):
    data = CareService(db).family_view(token)
    data["push"] = {"enabled": push_enabled(), "public_key": settings.VAPID_PUBLIC_KEY}
    return data


@router.post("/family/{token}/push/subscribe", status_code=status.HTTP_201_CREATED)
def family_subscribe(token: str, body: PushSubIn, db: Session = Depends(get_db)):
    if not push_enabled():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Bildirişlər serverdə qurulmayıb.")
    member = CareService(db).member_by_token(token)
    save_subscription(db, body.subscription, "family", member.id)
    return {"ok": True}


@router.post("/family/{token}/medications", status_code=status.HTTP_201_CREATED)
def family_add_medication(token: str, body: MedicationIn, db: Session = Depends(get_db)):
    svc = CareService(db)
    member = svc.member_by_token(token)
    med = svc.add_medication(member.user_id, body.name, body.times, body.dose,
                             created_by=f"family:{member.name}")
    return {"id": med.id, "name": med.name, "dose": med.dose, "times": med.times.split(",")}


@router.delete("/family/{token}/medications/{med_id}", status_code=status.HTTP_204_NO_CONTENT)
def family_remove_medication(token: str, med_id: str, db: Session = Depends(get_db)):
    svc = CareService(db)
    member = svc.member_by_token(token)
    svc.remove_medication(member.user_id, med_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/family/{token}/reminders", status_code=status.HTTP_201_CREATED)
def family_add_reminder(token: str, body: FamilyReminderIn, db: Session = Depends(get_db)):
    from datetime import datetime

    from app.utils.datetime_utils import BAKU_TZ

    svc = CareService(db)
    member = svc.member_by_token(token)
    try:
        when = datetime.fromisoformat(body.scheduled_at)
    except ValueError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Tarix formatı yanlışdır.")
    if when.tzinfo is None:
        when = when.replace(tzinfo=BAKU_TZ)
    rem = ReminderRepository(db).create(member.user_id, ReminderCreate(
        title=body.title, scheduled_at=when.astimezone(BAKU_TZ), timezone="Asia/Baku",
        description=f"{member.name} əlavə etdi"))
    return {"id": rem.id, "title": rem.title}
