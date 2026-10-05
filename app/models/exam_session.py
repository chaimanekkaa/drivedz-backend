from sqlalchemy import Column, Date, Enum, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.student_profile import PhaseEnum


class ExamSession(Base):
    __tablename__ = "exam_sessions"
    __table_args__ = (UniqueConstraint("phase", "date", name="uq_exam_session_phase_date"),)

    id = Column(Integer, primary_key=True, index=True)
    phase = Column(Enum(PhaseEnum, native_enum=False, length=20), nullable=False)
    date = Column(Date, nullable=False, index=True)

    registrations = relationship("ExamRegistration", back_populates="exam_session")
