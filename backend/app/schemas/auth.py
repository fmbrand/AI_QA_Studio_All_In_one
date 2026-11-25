import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORMModel


def _strip(value: str) -> str:
    return value.strip()


class RegisterIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=10, max_length=128)

    _name = field_validator("name")(_strip)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    _name = field_validator("name")(_strip)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class UserOut(ORMModel):
    id: uuid.UUID
    email: str
    name: str
    is_superadmin: bool
    created_at: datetime


class MembershipOut(BaseModel):
    project_id: uuid.UUID
    project_name: str
    project_status: str
    role: str


class MeOut(BaseModel):
    user: UserOut
    memberships: list[MembershipOut]


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int
    user: UserOut
