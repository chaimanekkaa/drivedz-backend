import enum

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Time, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.student_profile import PhaseEnum


class SessionStatusEnum(str, enum.Enum):
    scheduled = "scheduled"
    completed = "completed"
    canceled = "canceled"


class DrivingSession(Base):
    __tablename__ = "driving_sessions"
    __table_args__ = (Index("ix_driving_sessions_date_instructor", "date", "instructor_id"),)

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    phase = Column(Enum(PhaseEnum, native_enum=False, length=20), nullable=False)
    status = Column(Enum(SessionStatusEnum, native_enum=False, length=20), nullable=False, default=SessionStatusEnum.scheduled)
    group_label = Column(String(80), nullable=True)  # utilisé pour les séances de Code en groupe

    instructor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True, index=True)  # vide pour le Code
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    instructor = relationship("User", foreign_keys=[instructor_id])
    vehicle = relationship("Vehicle")
    attendances = relationship("SessionAttendance", back_populates="session", cascade="all, delete-orphan")


class SessionAttendance(Base):
    __tablename__ = "session_attendances"
    __table_args__ = (UniqueConstraint("session_id", "student_id", name="uq_attendance_session_student"),)

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("driving_sessions.id"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    attended = Column(Boolean, nullable=False, default=True)  # présent / absent
    credited_hours = Column(Float, nullable=False, default=0.0)  # heures réellement créditées au candidat
    notes = Column(String(300), nullable=True)

    session = relationship("DrivingSession", back_populates="attendances")
    student = relationship("User")
