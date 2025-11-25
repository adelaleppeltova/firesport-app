from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from bson import ObjectId
from enum import Enum
from typing import Optional
class UserRole(str, Enum):
    admin = "admin"
    user = "user"

class UserBase(BaseModel):
    email: EmailStr
    role: UserRole
    is_active: bool = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

class UserInDB(UserBase):
    id: str = Field(..., alias="_id")
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True
    
class UserPublic(UserBase):
    id: str
    created_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool
