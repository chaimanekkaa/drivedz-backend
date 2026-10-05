import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, func
from sqlalchemy.orm import relationship

from app.database import Base


class PhaseEnum(str, enum.Enum):
    code = "code"
    creneau = "creneau"
    circulation = "circulation"


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    current_phase = Column(Enum(PhaseEnum, native_enum=False, length=20), nullable=False, default=PhaseEnum.code)
    hours_code = Column(Float, nullable=False, default=0.0)
    hours_creneau = Column(Float, nullable=False, default=0.0)
    hours_circulation = Column(Float, nullable=False, default=0.0)

    # Forfait convenu à l'inscription (photographie du tarif à ce moment-là), en DA
    agreed_fee = Column(Integer, nullable=False)
    # Vrai quand l'épreuve de Circulation est réussie (formation terminée)
    course_completed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="student_profile", foreign_keys=[user_id])
    instructor = relationship("User", foreign_keys=[instructor_id])
