from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.phone import normalize_phone
from app.models.student_profile import PhaseEnum
from app.models.user import GenderEnum, RoleEnum
from app.schemas.auth import check_password


class UserCreate(BaseModel):
    full_name: str = Field(min_length=3, max_length=120)
    phone: str
    password: str
    role: RoleEnum = RoleEnum.student
    gender: GenderEnum

    @field_validator("full_name")
    @classmethod
    def _name(cls, v):
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("Nom trop court")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v):
        return normalize_phone(v)

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return check_password(v)


class PhaseStatusOut(BaseModel):
    key: str
    status: str  # done | current | locked


class StudentSummaryOut(BaseModel):
    id: int
    full_name: str
    phone: str
    gender: GenderEnum
    instructor_id: Optional[int] = None
    instructor_name: Optional[str] = None
    current_phase: PhaseEnum
    hours_code: float
    hours_creneau: float
    hours_circulation: float
    hours_current: float
    hours_required: float
    ready_for_exam: bool
    course_completed: bool
    extra_hours: float
    total_due: int
    total_paid: int
    remaining: int


class StudentProgressOut(StudentSummaryOut):
    instructor_phone: Optional[str] = None
    phases: list[PhaseStatusOut]


class PhaseSetIn(BaseModel):
    phase: PhaseEnum


class ResetPasswordIn(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v):
        return check_password(v)
