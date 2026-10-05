"""Validation et sérialisation des séances de conduite."""
from datetime import date as Date, time as Time

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.constants import MAX_GROUP_SIZE, PHASE_LABELS
from app.models.driving_session import DrivingSession, SessionAttendance, SessionStatusEnum
from app.models.student_profile import PhaseEnum, StudentProfile
from app.models.user import RoleEnum, User
from app.models.vehicle import Vehicle, VehicleStatusEnum
from app.services.pipeline_service import duration_hours
from app.services.scope import get_scoped_student


def session_query(db: Session):
    return db.query(DrivingSession).options(
        selectinload(DrivingSession.attendances).joinedload(SessionAttendance.student),
        joinedload(DrivingSession.instructor),
        joinedload(DrivingSession.vehicle),
    )


def load_session_students(db: Session, staff: User, student_ids: list[int], phase: PhaseEnum) -> list[User]:
    """Vérifie que chaque candidat existe, appartient au périmètre du moniteur (même genre),
    est bien dans la phase de la séance et n'a pas déjà terminé sa formation."""
    if phase == PhaseEnum.code:
        if len(student_ids) > MAX_GROUP_SIZE:
            raise HTTPException(status_code=400, detail=f"Une séance de Code est limitée à {MAX_GROUP_SIZE} candidats.")
    elif len(student_ids) != 1:
        raise HTTPException(status_code=400, detail="Une séance de Créneau / Circulation concerne un seul candidat.")

    students: list[User] = []
    for sid in student_ids:
        try:
            user, profile = get_scoped_student(db, staff, sid)
        except HTTPException:
            raise HTTPException(status_code=400, detail=f"Candidat #{sid} introuvable dans votre groupe.")
        if profile.course_completed:
            raise HTTPException(status_code=400, detail=f"{user.full_name} a déjà terminé sa formation.")
        if profile.current_phase != phase:
            raise HTTPException(
                status_code=400,
                detail=f"{user.full_name} est en phase « {PHASE_LABELS[profile.current_phase.value]} », "
                       f"pas « {PHASE_LABELS[phase.value]} ».",
            )
        students.append(user)
    return students


def validate_vehicle(db: Session, phase: PhaseEnum, vehicle_id: int | None) -> Vehicle | None:
    if phase == PhaseEnum.code:
        if vehicle_id is not None:
            raise HTTPException(status_code=400, detail="Une séance de Code ne nécessite pas de véhicule.")
        return None
    if vehicle_id is None:
        raise HTTPException(status_code=400, detail="Un véhicule est obligatoire pour cette séance.")
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=400, detail="Véhicule introuvable.")
    if vehicle.status != VehicleStatusEnum.disponible:
        raise HTTPException(status_code=400, detail=f"Le véhicule {vehicle.plate} est en maintenance.")
    return vehicle


def check_conflicts(
    db: Session,
    *,
    date: Date,
    start: Time,
    end: Time,
    instructor_id: int,
    vehicle_id: int | None,
    students: list[User],
    exclude_id: int | None = None,
) -> None:
    """Refuse tout chevauchement horaire : même moniteur, même véhicule ou même candidat."""
    q = (
        session_query(db)
        .filter(
            DrivingSession.date == date,
            DrivingSession.status != SessionStatusEnum.canceled,
            DrivingSession.start_time < end,
            DrivingSession.end_time > start,
        )
    )
    if exclude_id is not None:
        q = q.filter(DrivingSession.id != exclude_id)

    student_ids = {s.id for s in students}
    for other in q.all():
        span = f"{other.start_time.strftime('%H:%M')}-{other.end_time.strftime('%H:%M')}"
        if other.instructor_id == instructor_id:
            raise HTTPException(status_code=409, detail=f"Vous avez déjà une séance sur ce créneau ({span}).")
        if vehicle_id is not None and other.vehicle_id == vehicle_id:
            raise HTTPException(status_code=409, detail=f"Ce véhicule est déjà réservé sur ce créneau ({span}).")
        for att in other.attendances:
            if att.student_id in student_ids:
                name = att.student.full_name if att.student else f"#{att.student_id}"
                raise HTTPException(status_code=409, detail=f"{name} a déjà une séance sur ce créneau ({span}).")


def serialize_session(s: DrivingSession, viewer: User) -> dict:
    atts = s.attendances
    if viewer.role == RoleEnum.student:
        # Un candidat ne voit jamais les autres participants d'une séance de groupe
        atts = [a for a in atts if a.student_id == viewer.id]
    return {
        "id": s.id,
        "phase": s.phase,
        "status": s.status,
        "date": s.date,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "duration_hours": duration_hours(s),
        "group_label": s.group_label,
        "instructor_id": s.instructor_id,
        "instructor_name": s.instructor.full_name if s.instructor else "",
        "vehicle_id": s.vehicle_id,
        "vehicle_label": f"{s.vehicle.model} — {s.vehicle.plate}" if s.vehicle else None,
        "attendances": [
            {
                "student_id": a.student_id,
                "student_name": a.student.full_name if a.student else f"#{a.student_id}",
                "attended": a.attended,
                "credited_hours": a.credited_hours,
                "notes": a.notes,
            }
            for a in sorted(atts, key=lambda x: (x.student.full_name if x.student else ""))
        ],
    }
