from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.vehicle import VehicleStatusEnum


def _clean(v: str) -> str:
    return " ".join(v.split())


class VehicleCreate(BaseModel):
    plate: str = Field(min_length=3, max_length=30)
    model: str = Field(min_length=2, max_length=80)

    @field_validator("plate", "model")
    @classmethod
    def _c(cls, v):
        return _clean(v)


class VehicleUpdate(BaseModel):
    plate: Optional[str] = Field(default=None, min_length=3, max_length=30)
    model: Optional[str] = Field(default=None, min_length=2, max_length=80)
    status: Optional[VehicleStatusEnum] = None

    @field_validator("plate", "model")
    @classmethod
    def _c(cls, v):
        return _clean(v) if v else v


class VehicleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate: str
    model: str
    status: VehicleStatusEnum
