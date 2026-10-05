import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base


class RegistrationStatusEnum(str, enum.Enum):
    pending = "pending"    # demande envoyée par le candidat
    accepted = "accepted"  # autorisé à passer l'examen
    refused = "refused"    # demande refusée / autorisation retirée
    passed = "passed"      # examen réussi (résultat)
    failed = "failed"      # examen échoué (résultat)


class ExamRegistration(Base):
    __tablename__ = "exam_registrations"
    __table_args__ = (UniqueConstraint("student_id", "exam_session_id", name="uq_registration_student_session"),)

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    exam_session_id = Column(Integer, ForeignKey("exam_sessions.id"), nullable=False, index=True)
    status = Column(Enum(RegistrationStatusEnum, native_enum=False, length=20), nullable=False, default=RegistrationStatusEnum.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)

    student = relationship("User")
    exam_session = relationship("ExamSession", back_populates="registrations")
