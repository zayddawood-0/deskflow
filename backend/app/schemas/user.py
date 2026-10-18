import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.models.enums import UserRole
from app.schemas.auth import UserOut, validate_password_strength

__all__ = ["AgentOut", "UserCreate", "UserOut", "UserUpdate"]


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: EmailStr
    role: UserRole


class UserCreate(BaseModel):
    email: EmailStr
    full_name: Annotated[str, Field(min_length=1, max_length=120)]
    password: str
    role: UserRole = UserRole.REQUESTER

    _password_ok = field_validator("password")(validate_password_strength)


class UserUpdate(BaseModel):
    full_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    role: UserRole | None = None
    is_active: bool | None = None
