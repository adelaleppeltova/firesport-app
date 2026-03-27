from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from enum import Enum


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


class UserInDB(UserBase):
    id: str = Field(..., alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(
        populate_by_name=True,
    )


class UserPublic(UserBase):
    id: str
    created_at: datetime


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: UserRole
    is_active: bool
