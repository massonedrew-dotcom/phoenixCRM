import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.enums import Role
from app.core.security import MIN_PASSWORD_LENGTH

Password = Annotated[str, Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)]
Username = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=64),
    Field(pattern=r"^[a-zA-Z0-9._-]+$"),
]


def _not_blank(value: str) -> str:
    if not value:
        raise ValueError("Поле не может быть пустым")
    return value


FullName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=160),
    AfterValidator(_not_blank),
]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    username: Username
    full_name: FullName
    password: Password
    role: Role


class UserPatch(BaseModel):
    full_name: FullName | None = None
    role: Role | None = None
    is_active: bool | None = None


class PasswordReset(BaseModel):
    new_password: Password


class RealtorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    is_active: bool
