from pydantic import BaseModel, ConfigDict, field_validator

from app.core.security import MAX_PASSWORD_BYTES
from app.models.user import GenderEnum, RoleEnum


def check_password(v: str) -> str:
    if len(v) < 6:
        raise ValueError("Le mot de passe doit contenir au moins 6 caractères")
    if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError("Mot de passe trop long (72 octets maximum)")
    return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    phone: str
    role: RoleEnum
    gender: GenderEnum


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v):
        return check_password(v)
