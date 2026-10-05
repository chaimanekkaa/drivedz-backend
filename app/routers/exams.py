from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.constants import PHASE_LABELS
from app.core.time import today_dz
from app.database import get_db
from app.deps import get_current_user, require_staff, require_student
from app.models.exam_registration import ExamRegistration, RegistrationStatusEnum as RS
from app.models.exam_session import ExamSession
from app.models.student_profile import StudentProfile
from app.models.user import RoleEnum, User
from app.schemas.exam import (
    ExamRegistrationCreate,
    ExamRegistrationOut,
    ExamRegistrationReview,
    ExamSessionCreate,
    ExamSessionOut,
)
from app.services import pipeline_service as ps
from app.services.notification_service import notify
from app.services.scope import get_scoped_student

router = APIRouter(prefix="/exams", tags=["exams"])

ACTIVE = (RS.pending, RS.accepted)
# Transitions autorisées : demande -> autorisation -> résultat
TRANSITIONS = {
    RS.pending: {RS.accepted, RS.refused},
    RS.accepted: {RS.refused, RS.passed, RS.failed},
}


def _reg_out(r: ExamRegistration) -> dict:
    return {
        "id": r.id,
        "student_id": r.student_id,
        "student_name": r.student.full_name if r.student else f"#{r.student_id}",
        "exam_session_id": r.exam_session_id,
        "phase": r.exam_session.phase,
        "exam_date": r.exam_session.date,
        "status": r.status,
        "created_at": r.created_at,
    }


def _reg_query(db: Session):
    return db.query(ExamRegistration).options(joinedload(ExamRegistration.student), joinedload(ExamRegistration.exam_session))


def _exam_label(e: ExamSession) -> str:
    return f"{PHASE_LABELS[e.phase.value]} du {e.date.strftime('%d/%m/%Y')}"


# ---------------- Sessions d'examen ----------------

@router.get("/sessions", response_model=List[ExamSessionOut])
def list_exam_sessions(
    upcoming: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ExamSession)
    if upcoming or current_user.role == RoleEnum.student:
        q = q.filter(ExamSession.date >= today_dz())
    sessions = q.order_by(ExamSession.date, ExamSession.phase).all()
    counts = dict(db.query(ExamRegistration.exam_session_id, func.count(ExamRegistration.id)).group_by(ExamRegistration.exam_session_id).all())
    return [{"id": s.id, "phase": s.phase, "date": s.date, "registrations_count": counts.get(s.id, 0)} for s in sessions]


@router.post("/sessions", response_model=ExamSessionOut, status_code=201)
def create_exam_session(data: ExamSessionCreate, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    if db.query(ExamSession).filter(ExamSession.phase == data.phase, ExamSession.date == data.date).first():
        raise HTTPException(status_code=409, detail="Une session d'examen existe déjà pour cette épreuve à cette date.")
    exam = ExamSession(phase=data.phase, date=data.date)
    db.add(exam)
    db.flush()
    # Prévenir tous les candidats actuellement dans cette phase
    ids = [uid for (uid,) in db.query(StudentProfile.user_id).filter(
        StudentProfile.current_phase == data.phase, StudentProfile.course_completed.is_(False)).all()]
    for uid in ids:
        notify(db, uid, "exam_announced", "Nouvelle date d'examen", f"Examen {_exam_label(exam)} : vous pouvez faire une demande.")
    db.commit()
    return {"id": exam.id, "phase": exam.phase, "date": exam.date, "registrations_count": 0}


@router.delete("/sessions/{exam_id}", status_code=204)
def delete_exam_session(exam_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    exam = db.get(ExamSession, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Session d'examen introuvable.")
    if db.query(ExamRegistration).filter(ExamRegistration.exam_session_id == exam_id).first():
        raise HTTPException(status_code=409, detail="Cette session a déjà des demandes : elle ne peut pas être supprimée.")
    db.delete(exam)
    db.commit()


# ---------------- Demandes des candidats ----------------

@router.post("/registrations", response_model=ExamRegistrationOut, status_code=201)
def request_exam(data: ExamRegistrationCreate, db: Session = Depends(get_db), student: User = Depends(require_student)):
    exam = db.get(ExamSession, data.exam_session_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Session d'examen introuvable.")
    profile = db.query(StudentProfile).filter(StudentProfile.user_id == student.id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Dossier candidat introuvable.")

    if exam.date < today_dz():
        raise HTTPException(status_code=400, detail="Cette session d'examen est déjà passée.")
    if profile.course_completed:
        raise HTTPException(status_code=400, detail="Votre formation est déjà terminée.")
    if exam.phase != profile.current_phase:
        raise HTTPException(status_code=400, detail=f"Cet examen concerne l'étape « {PHASE_LABELS[exam.phase.value]} », pas votre étape actuelle.")
    if not ps.is_ready(profile):
        missing = ps.required_hours(profile.current_phase) - ps.current_hours(profile)
        raise HTTPException(status_code=400, detail=f"Il vous manque encore {missing:g} h avant de pouvoir demander l'examen.")

    same_phase_active = (
        db.query(ExamRegistration)
        .join(ExamSession, ExamSession.id == ExamRegistration.exam_session_id)
        .filter(ExamRegistration.student_id == student.id, ExamSession.phase == exam.phase, ExamRegistration.status.in_(ACTIVE))
        .first()
    )
    if same_phase_active:
        raise HTTPException(status_code=409, detail="Vous avez déjà une demande en cours pour cette épreuve.")

    reg = ExamRegistration(student_id=student.id, exam_session_id=exam.id)
    db.add(reg)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Vous avez déjà fait une demande pour cette session.")
    notify(db, profile.instructor_id, "exam_request", "Demande d'examen",
           f"{student.full_name} demande à passer l'examen {_exam_label(exam)}.")
    db.commit()
    return _reg_out(_reg_query(db).filter(ExamRegistration.id == reg.id).one())


@router.get("/registrations/me", response_model=List[ExamRegistrationOut])
def my_registrations(db: Session = Depends(get_db), student: User = Depends(require_student)):
    rows = _reg_query(db).filter(ExamRegistration.student_id == student.id).order_by(ExamRegistration.id.desc()).all()
    return [_reg_out(r) for r in rows]


@router.get("/registrations", response_model=List[ExamRegistrationOut])
def list_registrations(db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    """Uniquement les demandes des candidats du périmètre du moniteur (même genre)."""
    rows = (
        _reg_query(db)
        .join(User, User.id == ExamRegistration.student_id)
        .filter(User.gender == staff.gender)
        .order_by(ExamRegistration.id.desc())
        .all()
    )
    return [_reg_out(r) for r in rows]


@router.put("/registrations/{reg_id}", response_model=ExamRegistrationOut)
def review_registration(reg_id: int, data: ExamRegistrationReview, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    reg = _reg_query(db).filter(ExamRegistration.id == reg_id).first()
    if reg is None:
        raise HTTPException(status_code=404, detail="Demande introuvable.")
    user, profile = get_scoped_student(db, staff, reg.student_id)  # même genre uniquement

    new = data.status
    if new not in TRANSITIONS.get(reg.status, set()):
        raise HTTPException(status_code=409, detail=f"Changement impossible : « {reg.status.value} » → « {new.value} ».")
    exam = reg.exam_session
    if new in (RS.passed, RS.failed) and exam.date > today_dz():
        raise HTTPException(status_code=400, detail="Le résultat ne peut être saisi qu'à partir du jour de l'examen.")

    reg.status = new
    reg.reviewed_at = datetime.now(timezone.utc)
    label = _exam_label(exam)

    if new == RS.accepted:
        notify(db, user.id, "exam_accepted", "Demande acceptée", f"Vous êtes autorisé(e) à passer l'examen {label}.")
    elif new == RS.refused:
        notify(db, user.id, "exam_refused", "Demande refusée", f"Votre demande pour l'examen {label} n'a pas été retenue.")
    elif new == RS.failed:
        notify(db, user.id, "exam_failed", "Résultat d'examen", f"Vous n'avez pas réussi l'examen {label}. Vous pourrez refaire une demande.")
    elif new == RS.passed:
        if profile.current_phase == exam.phase and not profile.course_completed:
            state = ps.advance(profile)
            if state == "completed":
                notify(db, user.id, "exam_passed", "Félicitations 🎉", "Vous avez réussi l'examen final : votre formation est terminée !")
            else:
                notify(db, user.id, "exam_passed", "Examen réussi 🎉",
                       f"Bravo ! Examen {label} réussi : vous passez à l'étape « {PHASE_LABELS[state]} ».")
        else:
            notify(db, user.id, "exam_passed", "Examen réussi 🎉", f"Examen {label} réussi.")
    db.commit()
    return _reg_out(_reg_query(db).filter(ExamRegistration.id == reg_id).one())
