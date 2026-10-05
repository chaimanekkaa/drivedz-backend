"""Logique du parcours candidat : phases, heures, heures supplémentaires, facturation."""
import math
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.constants import PHASE_HOURS_REQUIRED, PHASE_ORDER
from app.models.driving_session import DrivingSession, SessionAttendance, SessionStatusEnum
from app.models.payment import Payment
from app.models.settings import Pricing
from app.models.student_profile import PhaseEnum, StudentProfile
from app.models.user import User
from app.schemas.driving_session import AttendanceIn

_HOURS_ATTR = {"code": "hours_code", "creneau": "hours_creneau", "circulation": "hours_circulation"}


def _key(phase) -> str:
    return phase.value if isinstance(phase, PhaseEnum) else str(phase)


def required_hours(phase) -> float:
    return PHASE_HOURS_REQUIRED[_key(phase)]


def hours_of(profile: StudentProfile, phase) -> float:
    return float(getattr(profile, _HOURS_ATTR[_key(phase)]) or 0.0)


def set_hours(profile: StudentProfile, phase, value: float) -> None:
    setattr(profile, _HOURS_ATTR[_key(phase)], round(max(0.0, value), 2))


def add_hours(profile: StudentProfile, phase, delta: float) -> None:
    set_hours(profile, phase, hours_of(profile, phase) + delta)


def current_hours(profile: StudentProfile) -> float:
    return hours_of(profile, profile.current_phase)


def is_ready(profile: StudentProfile) -> bool:
    """Prêt à valider / passer l'examen de la phase courante."""
    return (not profile.course_completed) and current_hours(profile) >= required_hours(profile.current_phase)


def extra_hours(profile: StudentProfile) -> float:
    """Heures au-delà du quota de chaque phase (facturées en supplément)."""
    return round(sum(max(0.0, hours_of(profile, p) - required_hours(p)) for p in PHASE_ORDER), 2)


def phases_status(profile: StudentProfile) -> list[dict]:
    idx = PHASE_ORDER.index(_key(profile.current_phase))
    out = []
    for i, key in enumerate(PHASE_ORDER):
        if profile.course_completed or i < idx:
            status = "done"
        elif i == idx:
            status = "current"
        else:
            status = "locked"
        out.append({"key": key, "status": status})
    return out


# ---------- Argent : une seule source de vérité (table payments) ----------

def total_paid_map(db: Session, student_ids: list[int] | None = None) -> dict[int, int]:
    q = db.query(Payment.student_id, func.coalesce(func.sum(Payment.amount), 0)).group_by(Payment.student_id)
    if student_ids is not None:
        q = q.filter(Payment.student_id.in_(student_ids))
    return {sid: int(total) for sid, total in q.all()}


def total_due(profile: StudentProfile, pricing: Pricing) -> int:
    extra = math.ceil(extra_hours(profile) - 1e-9)  # facturé par tranche de 60 min entamée
    return int(profile.agreed_fee) + extra * int(pricing.extra_hour_fee)


def build_summary(user: User, profile: StudentProfile, instructor: User | None, paid: int, pricing: Pricing) -> dict:
    due = total_due(profile, pricing)
    return {
        "id": user.id,
        "full_name": user.full_name,
        "phone": user.phone,
        "gender": user.gender,
        "instructor_id": profile.instructor_id,
        "instructor_name": instructor.full_name if instructor else None,
        "current_phase": profile.current_phase,
        "hours_code": hours_of(profile, "code"),
        "hours_creneau": hours_of(profile, "creneau"),
        "hours_circulation": hours_of(profile, "circulation"),
        "hours_current": current_hours(profile),
        "hours_required": required_hours(profile.current_phase),
        "ready_for_exam": is_ready(profile),
        "course_completed": bool(profile.course_completed),
        "extra_hours": extra_hours(profile),
        "total_due": due,
        "total_paid": paid,
        "remaining": max(0, due - paid),
    }


# ---------- Changements de phase ----------

def advance(profile: StudentProfile) -> str:
    """Passe à la phase suivante (Circulation -> formation terminée). Retourne un libellé."""
    cur = _key(profile.current_phase)
    if profile.course_completed:
        raise HTTPException(status_code=400, detail="La formation de ce candidat est déjà terminée.")
    if cur == "code":
        profile.current_phase = PhaseEnum.creneau
        return "creneau"
    if cur == "creneau":
        profile.current_phase = PhaseEnum.circulation
        return "circulation"
    profile.course_completed = True
    return "completed"


def validate_phase(profile: StudentProfile) -> str:
    """Validation manuelle par le moniteur : exige que les heures de la phase soient complètes."""
    if profile.course_completed:
        raise HTTPException(status_code=400, detail="La formation de ce candidat est déjà terminée.")
    missing = required_hours(profile.current_phase) - current_hours(profile)
    if missing > 1e-9:
        raise HTTPException(status_code=400, detail=f"Il manque encore {missing:g} h pour valider cette phase.")
    return advance(profile)


def set_phase_manual(profile: StudentProfile, target: PhaseEnum) -> None:
    """Changement manuel de phase, en gardant des heures cohérentes :
    - phases précédentes considérées comme terminées (heures = quota au minimum) ;
    - phases suivantes remises à zéro."""
    idx = PHASE_ORDER.index(target.value)
    for i, key in enumerate(PHASE_ORDER):
        if i < idx:
            set_hours(profile, key, max(hours_of(profile, key), required_hours(key)))
        elif i > idx:
            set_hours(profile, key, 0.0)
    profile.current_phase = target
    profile.course_completed = False


# ---------- Séances : clôture / réouverture (idempotentes) ----------

def duration_hours(session: DrivingSession) -> float:
    start = session.start_time.hour * 60 + session.start_time.minute
    end = session.end_time.hour * 60 + session.end_time.minute
    return round((end - start) / 60, 2)


def complete_session(db: Session, session: DrivingSession, inputs: list[AttendanceIn]) -> None:
    from app.core.time import today_dz

    if session.status == SessionStatusEnum.completed:
        raise HTTPException(status_code=409, detail="Cette séance est déjà terminée.")
    if session.status == SessionStatusEnum.canceled:
        raise HTTPException(status_code=400, detail="Une séance annulée ne peut pas être terminée.")
    if session.date > today_dz():
        raise HTTPException(status_code=400, detail="Impossible de terminer une séance qui n'a pas encore eu lieu.")

    by_student = {a.student_id: a for a in inputs}
    known = {att.student_id for att in session.attendances}
    unknown = set(by_student) - known
    if unknown:
        raise HTTPException(status_code=400, detail="Présence saisie pour un candidat qui ne fait pas partie de la séance.")

    hrs = duration_hours(session)
    for att in session.attendances:
        inp = by_student.get(att.student_id)
        att.attended = inp.attended if inp else True
        att.notes = inp.notes if inp else att.notes
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == att.student_id).first()
        if att.attended and profile is not None:
            add_hours(profile, session.phase, hrs)
            att.credited_hours = hrs
        else:
            att.credited_hours = 0.0
    session.status = SessionStatusEnum.completed


def reopen_session(db: Session, session: DrivingSession) -> None:
    if session.status != SessionStatusEnum.completed:
        raise HTTPException(status_code=400, detail="Seule une séance terminée peut être rouverte.")
    for att in session.attendances:
        if att.credited_hours:
            profile = db.query(StudentProfile).filter(StudentProfile.user_id == att.student_id).first()
            if profile is not None:
                add_hours(profile, session.phase, -att.credited_hours)
        att.credited_hours = 0.0
    session.status = SessionStatusEnum.scheduled
