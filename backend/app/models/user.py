from pydantic import BaseModel, EmailStr, Field, ConfigDict
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    admin = "admin"
    user = "user"


class UserBase(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.user
    is_active: bool = True


CLIENT_PASSWORD_HASH_PATTERN = r"^[a-f0-9]{64}$"


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=CLIENT_PASSWORD_HASH_PATTERN,
    )


class UserLoginRequest(BaseModel):
    email: EmailStr
    password_hash: str = Field(
        ...,
        min_length=64,
        max_length=64,
        pattern=CLIENT_PASSWORD_HASH_PATTERN,
    )


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    is_active: bool


class AuthenticatedUserOut(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    is_active: bool
    athlete_id: Optional[str] = None


class CurrentUserResponse(BaseModel):
    user_id: str
    email: EmailStr
    role: UserRole
    athlete_id: Optional[str] = None


class AthletePairingResponse(BaseModel):
    ok: bool = True
    athlete_id: Optional[str] = None
