from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class PricingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permit_fee: int
    extra_hour_fee: int
    exam_fee: int


class PricingUpdate(BaseModel):
    permit_fee: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    extra_hour_fee: Optional[int] = Field(default=None, ge=0, le=10_000_000)
    exam_fee: Optional[int] = Field(default=None, ge=0, le=10_000_000)


class InfoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business_name: str
    agreement_number: str
    director_name: str
    wilaya: str
    commune: str
    address: str
    phone: str


class InfoUpdate(BaseModel):
    business_name: Optional[str] = Field(default=None, max_length=150)
    agreement_number: Optional[str] = Field(default=None, max_length=80)
    director_name: Optional[str] = Field(default=None, max_length=120)
    wilaya: Optional[str] = Field(default=None, max_length=80)
    commune: Optional[str] = Field(default=None, max_length=80)
    address: Optional[str] = Field(default=None, max_length=250)
    phone: Optional[str] = Field(default=None, max_length=20)
