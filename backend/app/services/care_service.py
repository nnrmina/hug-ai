"""Care logic: profile, family circle, medications & doses, daily check-in, SOS,
and the scheduler tick that drives reminders/escalations.

Time rules (SQLite drops tzinfo): every NEW table stores UTC; the legacy `reminders`
table stores Baku wall-clock time. `_utc()` / `_from_db()` keep that straight.
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.models.care import CareEvent, CheckIn, DoseEvent, ElderProfile, FamilyMember, Medication
from app.models.reminder import Reminder
from app.repositories.user_repository import UserRepository
from app.services.push_service import push_to_elder, push_to_family
from app.utils.datetime_utils import BAKU_TZ

UTC = timezone.utc
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
MOOD_AZ = {"good": "yaxşı", "ok": "orta", "bad": "pis"}


# ---------------------------------------------------------------- time helpers
def now_utc() -> datetime:
    return datetime.now(UTC)


def _utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _from_db(dt: Optional[datetime]) -> Optional[datetime]:
    """New tables store UTC; SQLite hands it back naive."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def _store(dt: datetime) -> datetime:
    """Persist as naive UTC so SQLite and Postgres agree."""
    return _utc(dt).replace(tzinfo=None)


def baku_day(now: Optional[datetime] = None) -> str:
    return (now or now_utc()).astimezone(BAKU_TZ).strftime("%Y-%m-%d")


def normalize_times(times: List[str]) -> List[str]:
    out = []
    for t in times:
        m = TIME_RE.match(str(t).strip())
        if not m:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Yanlış saat: {t} (SS:DD olmalıdır)")
        out.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    out = sorted(set(out))
    if not out:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Ən azı bir saat lazımdır.")
    return out


def _slot_utc(day: str, hhmm: str) -> datetime:
    y, mo, d = (int(x) for x in day.split("-"))
    h, mi = (int(x) for x in hhmm.split(":"))
    return datetime(y, mo, d, h, mi, tzinfo=BAKU_TZ).astimezone(UTC)


def _hhmm(dt_utc: datetime) -> str:
    return dt_utc.astimezone(BAKU_TZ).strftime("%H:%M")


# ---------------------------------------------------------------- service
class CareService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)

    # ---- profile -------------------------------------------------------
    def profile(self, user_id: str) -> ElderProfile:
        self.users.get_or_create_default_user(user_id)
        prof = self.db.get(ElderProfile, user_id)
        if prof is None:
            prof = ElderProfile(user_id=user_id)
            self.db.add(prof)
            self.db.commit()
        return prof

    def update_profile(self, user_id: str, name: Optional[str], checkin_time: Optional[str]) -> ElderProfile:
        prof = self.profile(user_id)
        if name is not None:
            prof.name = name.strip()[:100]
        if checkin_time is not None:
            prof.checkin_time = normalize_times([checkin_time])[0]
        self.db.commit()
        return prof

    def elder_name(self, user_id: str) -> str:
        prof = self.db.get(ElderProfile, user_id)
        return (prof.name if prof and prof.name else "Yaxınınız")

    # ---- family circle -------------------------------------------------
    def family(self, user_id: str) -> List[FamilyMember]:
        return (self.db.query(FamilyMember).filter(FamilyMember.user_id == user_id)
                .order_by(FamilyMember.created_at.asc()).all())

    def add_family(self, user_id: str, name: str, relation: str, phone: str) -> FamilyMember:
        self.profile(user_id)
        member = FamilyMember(user_id=user_id, name=name.strip()[:100], relation=relation.strip()[:50],
                              phone=re.sub(r"[^\d+]", "", phone)[:30])
        self.db.add(member)
        self.db.commit()
        return member

    def delete_family(self, user_id: str, member_id: str) -> None:
        member = self.db.get(FamilyMember, member_id)
        if not member or member.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Ailə üzvü tapılmadı.")
        self.db.delete(member)
        self.db.commit()

    @staticmethod
    def invite_url(member: FamilyMember) -> str:
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/f/{member.invite_token}"

    def member_by_token(self, token: str) -> FamilyMember:
        member = self.db.query(FamilyMember).filter(FamilyMember.invite_token == token).first()
        if not member:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Keçid etibarsızdır.")
        return member

    # ---- medications ---------------------------------------------------
    def medications(self, user_id: str) -> List[Medication]:
        return (self.db.query(Medication).filter(Medication.user_id == user_id, Medication.active.is_(True))
                .order_by(Medication.created_at.asc()).all())

    def add_medication(self, user_id: str, name: str, times: List[str], dose: str = "",
                       created_by: str = "elder") -> Medication:
        self.profile(user_id)
        med = Medication(user_id=user_id, name=name.strip()[:120] or "Dərman", dose=(dose or "").strip()[:80],
                         times=",".join(normalize_times(times)), created_by=created_by[:60])
        self.db.add(med)
        self.db.commit()
        self.ensure_doses(user_id)
        return med

    def remove_medication(self, user_id: str, med_id: str) -> None:
        med = self.db.get(Medication, med_id)
        if not med or med.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Dərman tapılmadı.")
        med.active = False
        (self.db.query(DoseEvent)
         .filter(DoseEvent.medication_id == med_id, DoseEvent.status == "pending")
         .delete(synchronize_session=False))
        self.db.commit()

    def ensure_doses(self, user_id: str, now: Optional[datetime] = None) -> None:
        """Create today's dose events (idempotent per medication + slot)."""
        day = baku_day(now)
        for med in self.medications(user_id):
            existing = {d.slot for d in self.db.query(DoseEvent).filter(DoseEvent.medication_id == med.id)
                        .filter(DoseEvent.slot.like(f"{day}%")).all()}
            for hhmm in med.times.split(","):
                slot = f"{day} {hhmm}"
                if slot in existing:
                    continue
                self.db.add(DoseEvent(medication_id=med.id, user_id=user_id, slot=slot,
                                      scheduled_at=_store(_slot_utc(day, hhmm))))
        self.db.commit()

    def doses_today(self, user_id: str, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        self.ensure_doses(user_id, now)
        day = baku_day(now)
        meds = {m.id: m for m in self.db.query(Medication).filter(Medication.user_id == user_id).all()}
        rows = (self.db.query(DoseEvent).filter(DoseEvent.user_id == user_id, DoseEvent.slot.like(f"{day}%"))
                .order_by(DoseEvent.slot.asc()).all())
        out = []
        for d in rows:
            med = meds.get(d.medication_id)
            if not med or (not med.active and d.status == "pending"):
                continue
            out.append({
                "id": d.id, "medication_id": d.medication_id, "name": med.name, "dose": med.dose,
                "time": d.slot[-5:], "status": d.status,
                "due_at": _from_db(d.scheduled_at).isoformat(),
                "taken_at": _from_db(d.taken_at).isoformat() if d.taken_at else None,
            })
        return out

    def _dose_for(self, user_id: str, dose_id: str) -> DoseEvent:
        dose = self.db.get(DoseEvent, dose_id)
        if not dose or dose.user_id != user_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Dərman qeydi tapılmadı.")
        return dose

    def mark_taken(self, user_id: str, dose_id: Optional[str] = None) -> Optional[DoseEvent]:
        """Mark a dose taken. Without an id: the most relevant pending/missed dose right now."""
        if dose_id:
            dose = self._dose_for(user_id, dose_id)
        else:
            self.ensure_doses(user_id)
            day = baku_day()
            candidates = (self.db.query(DoseEvent)
                          .filter(DoseEvent.user_id == user_id, DoseEvent.slot.like(f"{day}%"),
                                  DoseEvent.status.in_(("pending", "missed")))
                          .order_by(DoseEvent.scheduled_at.asc()).all())
            now = now_utc()
            due = [d for d in candidates if _from_db(d.scheduled_at) <= now + timedelta(minutes=60)]
            dose = due[-1] if due else None
            if dose is None:
                return None
        was_missed = dose.status == "missed"
        dose.status = "taken"
        dose.taken_at = _store(now_utc())
        med = self.db.get(Medication, dose.medication_id)
        self.db.add(CareEvent(user_id=user_id, kind="dose_taken",
                              message=f"{med.name if med else 'Dərman'} içildi ({dose.slot[-5:]})", ref=dose.id))
        self.db.commit()
        if was_missed and dose.family_notified:
            push_to_family(self.db, user_id, {
                "title": "✓ Dərman içildi",
                "body": f"{self.elder_name(user_id)} {med.name if med else 'dərmanı'} gecikmə ilə içdi.",
                "tag": f"dose-{dose.id}", "url": "/f/",
            })
        return dose

    def snooze(self, user_id: str, dose_id: str, minutes: int = 10) -> DoseEvent:
        dose = self._dose_for(user_id, dose_id)
        if dose.status == "taken":
            return dose
        dose.status = "pending"
        dose.scheduled_at = _store(now_utc() + timedelta(minutes=max(1, min(minutes, 120))))
        dose.notified_at = None
        self.db.commit()
        return dose

    # ---- daily check-in -------------------------------------------------
    def checkin_today(self, user_id: str, now: Optional[datetime] = None) -> Optional[CheckIn]:
        return (self.db.query(CheckIn).filter(CheckIn.user_id == user_id, CheckIn.day == baku_day(now))
                .order_by(CheckIn.created_at.desc()).first())

    def checkin_due(self, user_id: str, now: Optional[datetime] = None) -> bool:
        now = now or now_utc()
        prof = self.profile(user_id)
        return (self.checkin_today(user_id, now) is None
                and now >= _slot_utc(baku_day(now), prof.checkin_time))

    def record_checkin(self, user_id: str, mood: str, note: str = "") -> CheckIn:
        if mood not in MOOD_AZ:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "mood: good | ok | bad")
        self.profile(user_id)
        row = CheckIn(user_id=user_id, day=baku_day(), mood=mood, note=(note or "")[:300])
        self.db.add(row)
        name = self.elder_name(user_id)
        self.db.add(CareEvent(user_id=user_id, kind="checkin", message=f"Özünü {MOOD_AZ[mood]} hiss edir",
                              ref=row.day))
        self.db.commit()
        if mood == "bad":
            push_to_family(self.db, user_id, {
                "title": f"⚠️ {name} özünü pis hiss edir",
                "body": "Bu gün halını soruşduq — “pis” cavabını verdi. Zəng etməyiniz yaxşı olardı.",
                "tag": f"checkin-{row.day}", "url": "/f/", "requireInteraction": True,
            })
        return row

    # ---- SOS -----------------------------------------------------------
    def sos(self, user_id: str, lat: Optional[float], lon: Optional[float],
            accuracy: Optional[float] = None, reason: str = "") -> Tuple[CareEvent, int]:
        self.profile(user_id)
        name = self.elder_name(user_id)
        where = f"https://maps.google.com/?q={lat:.6f},{lon:.6f}" if lat is not None and lon is not None else None
        ev = CareEvent(user_id=user_id, kind="sos", lat=lat, lon=lon,
                       message=(reason or "Təcili kömək istəyir")[:300])
        self.db.add(ev)
        self.db.commit()
        body = f"{name} təcili kömək istəyir!" + (f" Yer: {where}" if where else " Yer məlum deyil.")
        sent = push_to_family(self.db, user_id, {
            "title": "🚨 SOS — təcili kömək",
            "body": body, "tag": f"sos-{ev.id}", "url": where or "/f/",
            "requireInteraction": True, "kind": "sos",
        })
        logger.warning("SOS for user %s delivered to %d family devices", user_id[:8], sent)
        return ev, sent

    # ---- timeline / family view ------------------------------------------
    def events(self, user_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        rows = (self.db.query(CareEvent)
                .filter(CareEvent.user_id == user_id,
                        CareEvent.kind.in_(("sos", "dose_missed", "dose_taken", "checkin", "checkin_missed")))
                .order_by(CareEvent.created_at.desc()).limit(limit).all())
        return [{"id": e.id, "kind": e.kind, "message": e.message, "lat": e.lat, "lon": e.lon,
                 "at": _from_db(e.created_at).isoformat()} for e in rows]

    def family_view(self, token: str) -> Dict[str, Any]:
        member = self.member_by_token(token)
        uid = member.user_id
        prof = self.profile(uid)
        check = self.checkin_today(uid)
        reminders = (self.db.query(Reminder).filter(Reminder.user_id == uid, Reminder.status == "pending")
                     .order_by(Reminder.scheduled_at.asc()).limit(20).all())
        return {
            "member": {"id": member.id, "name": member.name, "relation": member.relation},
            "elder": {"name": prof.name or "Yaxınınız", "checkin_time": prof.checkin_time},
            "checkin": {"mood": check.mood, "at": _from_db(check.created_at).isoformat()} if check else None,
            "checkin_due": self.checkin_due(uid),
            "doses": self.doses_today(uid),
            "medications": [{"id": m.id, "name": m.name, "dose": m.dose, "times": m.times.split(",")}
                            for m in self.medications(uid)],
            "reminders": [{"id": r.id, "title": r.title,
                           "scheduled_at": r.scheduled_at.replace(tzinfo=BAKU_TZ).isoformat()
                           if r.scheduled_at.tzinfo is None else r.scheduled_at.isoformat()} for r in reminders],
            "events": self.events(uid),
        }

    # ---- scheduler tick --------------------------------------------------
    def tick(self, now: Optional[datetime] = None) -> Dict[str, int]:
        """One scheduler pass. Idempotent; safe to run every ~30 s."""
        now = now or now_utc()
        stats = {"dose_push": 0, "dose_missed": 0, "reminder_push": 0, "checkin_prompt": 0, "checkin_missed": 0}

        user_ids = {m.user_id for m in self.db.query(Medication).filter(Medication.active.is_(True)).all()}
        for uid in user_ids:
            self.ensure_doses(uid, now)

        # 1) doses due → remind the elder
        for d in self.db.query(DoseEvent).filter(DoseEvent.status == "pending", DoseEvent.notified_at.is_(None)).all():
            if _from_db(d.scheduled_at) > now:
                continue
            med = self.db.get(Medication, d.medication_id)
            d.notified_at = _store(now)
            self.db.commit()
            push_to_elder(self.db, d.user_id, {
                "title": "💊 Dərman vaxtıdır",
                "body": f"{med.name if med else 'Dərman'}{(' · ' + med.dose) if med and med.dose else ''} — saat {d.slot[-5:]}",
                "tag": f"dose-{d.id}", "url": f"/?dose={d.id}", "requireInteraction": True,
                "kind": "dose", "doseId": d.id,
                "actions": [{"action": "taken", "title": "İçdim ✓"}, {"action": "snooze", "title": "10 dəq sonra"}],
            })
            stats["dose_push"] += 1

        # 2) not taken in time → missed, tell the family
        cutoff = now - timedelta(minutes=settings.DOSE_MISSED_AFTER_MIN)
        for d in self.db.query(DoseEvent).filter(DoseEvent.status == "pending").all():
            if _from_db(d.scheduled_at) > cutoff or d.notified_at is None:
                continue
            med = self.db.get(Medication, d.medication_id)
            d.status = "missed"
            d.family_notified = True
            name = self.elder_name(d.user_id)
            msg = f"{med.name if med else 'Dərman'} ({d.slot[-5:]}) içilmədi"
            self.db.add(CareEvent(user_id=d.user_id, kind="dose_missed", message=msg, ref=d.id))
            self.db.commit()
            push_to_family(self.db, d.user_id, {
                "title": f"💊 {name} dərmanını içməyib",
                "body": f"{msg}. Zəng edib xatırlada bilərsiniz.", "tag": f"dose-{d.id}", "url": "/f/",
            })
            stats["dose_missed"] += 1

        # 3) one-off reminders (legacy table stores Baku wall-clock time)
        pushed = {e.ref for e in self.db.query(CareEvent).filter(CareEvent.kind == "reminder_push").all()}
        for r in self.db.query(Reminder).filter(Reminder.status == "pending").all():
            at = r.scheduled_at.replace(tzinfo=BAKU_TZ) if r.scheduled_at.tzinfo is None else r.scheduled_at
            if r.id in pushed or at > now or at < now - timedelta(hours=6):
                continue
            self.db.add(CareEvent(user_id=r.user_id, kind="reminder_push", ref=r.id, message=r.title))
            self.db.commit()
            push_to_elder(self.db, r.user_id, {
                "title": "⏰ Xatırlatma", "body": r.title, "tag": f"rem-{r.id}", "url": "/?open=reminders",
                "requireInteraction": True, "kind": "reminder",
            })
            stats["reminder_push"] += 1

        # 4) daily check-in: prompt the elder, escalate to family if silent
        day = baku_day(now)
        for prof in self.db.query(ElderProfile).all():
            if not self.family(prof.user_id) and not self.medications(prof.user_id):
                continue  # not set up for care yet
            start = _slot_utc(day, prof.checkin_time)
            if now < start or self.checkin_today(prof.user_id, now):
                continue
            ref = f"{day}:{prof.user_id}"
            done = {e.kind for e in self.db.query(CareEvent).filter(CareEvent.ref == ref).all()}
            if "checkin_prompt" not in done:
                self.db.add(CareEvent(user_id=prof.user_id, kind="checkin_prompt", ref=ref))
                self.db.commit()
                push_to_elder(self.db, prof.user_id, {
                    "title": "☀️ Sabahınız xeyir!", "body": "Özünüzü necə hiss edirsiniz? Toxunun və cavab verin.",
                    "tag": f"checkin-{day}", "url": "/?checkin=1", "kind": "checkin",
                })
                stats["checkin_prompt"] += 1
            elif ("checkin_missed" not in done
                  and now >= start + timedelta(minutes=settings.CHECKIN_ESCALATE_AFTER_MIN)):
                name = prof.name or "Yaxınınız"
                self.db.add(CareEvent(user_id=prof.user_id, kind="checkin_missed", ref=ref,
                                      message="Bu gün hələ cavab verməyib"))
                self.db.commit()
                push_to_family(self.db, prof.user_id, {
                    "title": f"☎️ {name} bu gün hələ əlaqə saxlamayıb",
                    "body": "Gündəlik yoxlamaya cavab yoxdur. Zəng edib halını soruşun.",
                    "tag": f"checkin-{day}", "url": "/f/", "requireInteraction": True,
                })
                stats["checkin_missed"] += 1
        return stats
