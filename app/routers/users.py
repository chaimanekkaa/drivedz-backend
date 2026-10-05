from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.constants import PHASE_LABELS
from app.core.security import hash_password
from app.database import get_db
from app.deps import get_current_user, require_admin, require_staff
from app.models.student_profile import StudentProfile
from app.models.user import RoleEnum, User
from app.schemas.auth import UserOut
from app.schemas.user import (
    PhaseSetIn,
    ResetPasswordIn,
    StudentProgressOut,
    StudentSummaryOut,
    UserCreate,
)
from app.services import pipeline_service as ps
from app.services.notification_service import notify
from app.services.scope import get_scoped_student, scoped_student_rows
from app.services.settings_service import get_pricing

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), current_user: User = Depends(require_staff)):
    # --- Qui peut créer quoi ? ---
    if user_in.role == RoleEnum.admin:
        raise HTTPException(status_code=403, detail="La création d'un compte administrateur n'est pas autorisée.")
    if user_in.role == RoleEnum.instructor and current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Seul l'administrateur peut créer un compte moniteur.")
    if user_in.role == RoleEnum.student and user_in.gender != current_user.gender:
        raise HTTPException(status_code=400, detail="Vous ne pouvez inscrire que des candidats de votre propre genre.")

    if db.query(User).filter(User.phone == user_in.phone).first():
        raise HTTPException(status_code=409, detail="Ce numéro de téléphone est déjà enregistré.")

    new_user = User(
        full_name=user_in.full_name,
        phone=user_in.phone,
        password_hash=hash_password(user_in.password),
        role=user_in.role,
        gender=user_in.gender,
    )
    db.add(new_user)
    try:
        db.flush()
        if new_user.role == RoleEnum.student:
            db.add(
                StudentProfile(
                    user_id=new_user.id,
                    instructor_id=current_user.id,  # rattaché à celui qui l'inscrit
                    agreed_fee=get_pricing(db).permit_fee,  # forfait figé à l'inscription
                )
            )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Ce numéro de téléphone est déjà enregistré.")
    db.refresh(new_user)
    return new_user


@router.get("/students", response_model=List[StudentSummaryOut])
def list_students(
    q: Optional[str] = Query(default=None, max_length=60),
    limit: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    staff: User = Depends(require_staff),
):
    query = scoped_student_rows(db, staff)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(User.full_name.ilike(term), User.phone.ilike(term)))
    rows = query.order_by(User.full_name).limit(limit).all()

    pricing = get_pricing(db)
    paid = ps.total_paid_map(db, [u.id for u, _ in rows]) if rows else {}
    instr_ids = {p.instructor_id for _, p in rows if p.instructor_id}
    instructors = {u.id: u for u in db.query(User).filter(User.id.in_(instr_ids)).all()} if instr_ids else {}
    return [ps.build_summary(u, p, instructors.get(p.instructor_id), paid.get(u.id, 0), pricing) for u, p in rows]


@router.get("/instructors", response_model=List[UserOut])
def list_instructors(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    return db.query(User).filter(User.role == RoleEnum.instructor).order_by(User.full_name).all()


@router.get("/{user_id}/progress", response_model=StudentProgressOut)
def get_student_progress(user_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == RoleEnum.student:
        if current_user.id != user_id:
            raise HTTPException(status_code=403, detail="Accès refusé.")
        user = current_user
        profile = db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first()
        if profile is None:
            raise HTTPException(status_code=404, detail="Dossier candidat introuvable.")
    else:
        user, profile = get_scoped_student(db, current_user, user_id)

    instructor = db.get(User, profile.instructor_id) if profile.instructor_id else None
    paid = ps.total_paid_map(db, [user.id]).get(user.id, 0)
    data = ps.build_summary(user, profile, instructor, paid, get_pricing(db))
    data["instructor_phone"] = instructor.phone if instructor else None
    data["phases"] = ps.phases_status(profile)
    return data


@router.post("/{user_id}/validate-phase")
def validate_student_phase(user_id: int, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    user, profile = get_scoped_student(db, staff, user_id)
    new_state = ps.validate_phase(profile)
    if new_state == "completed":
        notify(db, user.id, "phase_changed", "Formation terminée 🎉", "Félicitations, vous avez terminé toutes les étapes du permis B.")
    else:
        notify(db, user.id, "phase_changed", "Étape validée",
               f"Vous passez à l'étape « {PHASE_LABELS[new_state]} ».")
    db.commit()
    return {"message": "Phase validée.", "current_phase": profile.current_phase.value, "course_completed": profile.course_completed}


@router.put("/{user_id}/phase")
def set_student_phase(user_id: int, payload: PhaseSetIn, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    """Changement manuel (ex : candidat qui a déjà son Code ailleurs et démarre en Créneau)."""
    user, profile = get_scoped_student(db, staff, user_id)
    ps.set_phase_manual(profile, payload.phase)
    notify(db, user.id, "phase_changed", "Étape mise à jour",
           f"Votre moniteur vous a placé à l'étape « {PHASE_LABELS[payload.phase.value]} ».")
    db.commit()
    return {"message": "Phase mise à jour.", "current_phase": profile.current_phase.value}


@router.post("/{user_id}/reset-password")
def reset_student_password(user_id: int, data: ResetPasswordIn, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    user, _ = get_scoped_student(db, staff, user_id)
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Mot de passe réinitialisé."}
