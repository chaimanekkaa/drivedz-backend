from datetime import date as Date, time as Time
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.core.constants import MAX_SESSION_MINUTES
from app.models.driving_session import SessionStatusEnum
from app.models.student_profile import PhaseEnum


def minutes_between(start: Time, end: Time) -> int:
    return (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute)


def check_times(start: Time, end: Time) -> None:
    diff = minutes_between(start, end)
    if diff <= 0:
        raise ValueError("L'heure de fin doit être après l'heure de début")
    if diff > MAX_SESSION_MINUTES:
        raise ValueError(f"Une séance ne peut pas dépasser {MAX_SESSION_MINUTES // 60} heures")


class SessionCreate(BaseModel):
    phase: PhaseEnum
    date: Date
    start_time: Time
    end_time: Time
    vehicle_id: Optional[int] = None
    group_label: Optional[str] = Field(default=None, max_length=80)
    student_ids: list[int] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self):
        check_times(self.start_time, self.end_time)
        if len(set(self.student_ids)) != len(self.student_ids):
            raise ValueError("Candidat en double dans la séance")
        return self


class SessionUpdate(BaseModel):
    date: Optional[Date] = None
    start_time: Optional[Time] = None
    end_time: Optional[Time] = None
    vehicle_id: Optional[int] = None
    group_label: Optional[str] = Field(default=None, max_length=80)
    student_ids: Optional[list[int]] = Field(default=None, min_length=1)


class AttendanceIn(BaseModel):
    student_id: int
    attended: bool = True
    notes: Optional[str] = Field(default=None, max_length=300)


class SessionComplete(BaseModel):
    attendances: list[AttendanceIn] = []


class AttendanceOut(BaseModel):
    student_id: int
    student_name: str
    attended: bool
    credited_hours: float
    notes: Optional[str] = None


class SessionOut(BaseModel):
    id: int
    phase: PhaseEnum
    status: SessionStatusEnum
    date: Date
    start_time: Time
    end_time: Time
    duration_hours: float
    group_label: Optional[str] = None
    instructor_id: int
    instructor_name: str
    vehicle_id: Optional[int] = None
    vehicle_label: Optional[str] = None
    attendances: list[AttendanceOut]
