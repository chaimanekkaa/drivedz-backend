from datetime import date as Date, datetime

from pydantic import BaseModel, field_validator

from app.core.time import today_dz
from app.models.exam_registration import RegistrationStatusEnum
from app.models.student_profile import PhaseEnum


class ExamSessionCreate(BaseModel):
    phase: PhaseEnum
    date: Date

    @field_validator("date")
    @classmethod
    def _not_past(cls, v):
        if v < today_dz():
            raise ValueError("La date d'examen ne peut pas être dans le passé")
        return v


class ExamSessionOut(BaseModel):
    id: int
    phase: PhaseEnum
    date: Date
    registrations_count: int = 0


class ExamRegistrationCreate(BaseModel):
    exam_session_id: int


class ExamRegistrationOut(BaseModel):
    id: int
    student_id: int
    student_name: str
    exam_session_id: int
    phase: PhaseEnum
    exam_date: Date
    status: RegistrationStatusEnum
    created_at: datetime | None = None


class ExamRegistrationReview(BaseModel):
    status: RegistrationStatusEnum
