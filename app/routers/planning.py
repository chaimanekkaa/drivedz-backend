from datetime import date as Date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.constants import PHASE_LABELS
from app.database import get_db
from app.deps import get_current_user, require_staff
from app.models.driving_session import DrivingSession, SessionAttendance, SessionStatusEnum
from app.models.user import RoleEnum, User
from app.schemas.driving_session import SessionComplete, SessionCreate, SessionOut, SessionUpdate, check_times
from app.services import pipeline_service as ps
from app.services.notification_service import notify
from app.services.session_service import (
    check_conflicts,
    load_session_students,
    serialize_session,
    session_query,
    validate_vehicle,
)

router = APIRouter(prefix="/planning", tags=["planning"])


def _own_session(db: Session, staff: User, session_id: int) -> DrivingSession:
    """Chaque moniteur (admin compris) ne gère que ses propres séances."""
    s = session_query(db).filter(DrivingSession.id == session_id, DrivingSession.instructor_id == staff.id).first()
    if s is None:
        raise HTTPException(status_code=404, detail="Séance introuvable.")
    return s


def _label(s: DrivingSession) -> str:
    return f"{PHASE_LABELS[s.phase.value]} le {s.date.strftime('%d/%m/%Y')} à {s.start_time.strftime('%H:%M')}"


@router.post("/", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(data: SessionCreate, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    students = load_session_students(db, staff, data.student_ids, data.phase)
    validate_vehicle(db, data.phase, data.vehicle_id)
    check_conflicts(
        db, date=data.date, start=data.start_time, end=data.end_time,
        instructor_id=staff.id, vehicle_id=data.vehicle_id, students=students,
    )

    session = DrivingSession(
        instructor_id=staff.id,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        phase=data.phase,
        vehicle_id=data.vehicle_id,
        group_label=(data.group_label or "Groupe Code") if data.phase.value == "code" else None,
    )
    db.add(session)
    db.flush()
    for st in students:
        db.add(SessionAttendance(session_id=session.id, student_id=st.id))
        notify(db, st.id, "session_created", "Nouvelle séance", f"{_label(session)} avec {staff.full_name}.")
    db.commit()
    return serialize_session(_own_session(db, staff, session.id), staff)


@router.get("/", response_model=List[SessionOut])
def list_sessions(
    date_from: Optional[Date] = None,
    date_to: Optional[Date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = session_query(db)
    if current_user.role == RoleEnum.student:
        q = q.join(SessionAttendance, SessionAttendance.session_id == DrivingSession.id).filter(
            SessionAttendance.student_id == current_user.id,
            DrivingSession.status != SessionStatusEnum.canceled,
        )
    else:
        q = q.filter(DrivingSession.instructor_id == current_user.id)
    if date_from:
        q = q.filter(DrivingSession.date >= date_from)
    if date_to:
        q = q.filter(DrivingSession.date <= date_to)
    sessions = q.order_by(DrivingSession.date, DrivingSession.start_time).all()
    return [serialize_session(s, current_user) for s in sessions]


@router.put("/{session_id}", response_model=SessionOut)
def update_session(session_id: int, data: SessionUpdate, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = _own_session(db, staff, session_id)
    if s.status != SessionStatusEnum.scheduled:
        raise HTTPException(status_code=400, detail="Seule une séance planifiée peut être modifiée.")

    new_date = data.date or s.date
    new_start = data.start_time or s.start_time
    new_end = data.end_time or s.end_time
    try:
        check_times(new_start, new_end)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    old_ids = {a.student_id for a in s.attendances}
    student_ids = data.student_ids if data.student_ids is not None else list(old_ids)
    if len(set(student_ids)) != len(student_ids):
        raise HTTPException(status_code=422, detail="Candidat en double dans la séance.")
    students = load_session_students(db, staff, student_ids, s.phase)

    vehicle_id = data.vehicle_id if "vehicle_id" in data.model_fields_set else s.vehicle_id
    validate_vehicle(db, s.phase, vehicle_id)
    check_conflicts(
        db, date=new_date, start=new_start, end=new_end, instructor_id=staff.id,
        vehicle_id=vehicle_id, students=students, exclude_id=s.id,
    )

    changed_slot = (new_date, new_start, new_end, vehicle_id) != (s.date, s.start_time, s.end_time, s.vehicle_id)
    s.date, s.start_time, s.end_time, s.vehicle_id = new_date, new_start, new_end, vehicle_id
    if s.phase.value == "code" and "group_label" in data.model_fields_set:
        s.group_label = data.group_label or "Groupe Code"

    new_ids = {st.id for st in students}
    for att in list(s.attendances):
        if att.student_id not in new_ids:
            s.attendances.remove(att)
            notify(db, att.student_id, "session_canceled", "Séance annulée", f"{_label(s)} a été annulée.")
    for st in students:
        if st.id not in old_ids:
            db.add(SessionAttendance(session_id=s.id, student_id=st.id))
            notify(db, st.id, "session_created", "Nouvelle séance", f"{_label(s)} avec {staff.full_name}.")
        elif changed_slot:
            notify(db, st.id, "session_updated", "Séance modifiée", f"Nouvel horaire : {_label(s)}.")
    db.commit()
    return serialize_session(_own_session(db, staff, session_id), staff)


@router.post("/{session_id}/complete", response_model=SessionOut)
def complete_session(session_id: int, data: SessionComplete, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = _own_session(db, staff, session_id)
    ps.complete_session(db, s, data.attendances)
    db.commit()
    return serialize_session(_own_session(db, staff, session_id), staff)


@router.post("/{session_id}/reopen", response_model=SessionOut)
def reopen_session(session_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = _own_session(db, staff, session_id)
    ps.reopen_session(db, s)
    db.commit()
    return serialize_session(_own_session(db, staff, session_id), staff)


@router.post("/{session_id}/cancel", response_model=SessionOut)
def cancel_session(session_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = _own_session(db, staff, session_id)
    if s.status != SessionStatusEnum.scheduled:
        raise HTTPException(status_code=400, detail="Seule une séance planifiée peut être annulée.")
    s.status = SessionStatusEnum.canceled
    for a in s.attendances:
        notify(db, a.student_id, "session_canceled", "Séance annulée", f"{_label(s)} a été annulée.")
    db.commit()
    return serialize_session(_own_session(db, staff, session_id), staff)


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    s = _own_session(db, staff, session_id)
    if s.status == SessionStatusEnum.completed:
        raise HTTPException(status_code=400, detail="Une séance terminée ne peut pas être supprimée : rouvrez-la d'abord.")
    if s.status == SessionStatusEnum.scheduled:
        for a in s.attendances:
            notify(db, a.student_id, "session_canceled", "Séance annulée", f"{_label(s)} a été annulée.")
    db.delete(s)
    db.commit()
