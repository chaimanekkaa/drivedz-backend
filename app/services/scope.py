"""Séparation stricte hommes / femmes : chaque membre du personnel ne voit et ne gère
que les candidats de son propre genre (Amine -> hommes, Wassila -> femmes)."""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.student_profile import StudentProfile
from app.models.user import RoleEnum, User


def get_scoped_student(db: Session, staff: User, student_id: int) -> tuple[User, StudentProfile]:
    row = (
        db.query(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(User.id == student_id, User.role == RoleEnum.student, User.gender == staff.gender)
        .first()
    )
    if row is None:
        # 404 volontaire : on ne révèle pas l'existence d'un candidat hors périmètre
        raise HTTPException(status_code=404, detail="Candidat introuvable.")
    return row[0], row[1]


def scoped_student_rows(db: Session, staff: User):
    """Requête (User, StudentProfile) limitée au périmètre du membre du personnel."""
    return (
        db.query(User, StudentProfile)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .filter(User.role == RoleEnum.student, User.gender == staff.gender)
    )
