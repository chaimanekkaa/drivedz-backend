from datetime import date as Date
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.time import today_dz


class PaymentCreate(BaseModel):
    student_id: int
    amount: int = Field(gt=0, le=10_000_000)
    paid_at: Optional[Date] = None

    @field_validator("paid_at")
    @classmethod
    def _not_future(cls, v):
        if v is not None and v > today_dz():
            raise ValueError("La date de paiement ne peut pas être dans le futur")
        return v


class PaymentOut(BaseModel):
    id: int
    student_id: int
    amount: int
    paid_at: Date
    receipt_number: Optional[str] = None
