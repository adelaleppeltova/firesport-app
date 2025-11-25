from pydantic import BaseModel, EmailStr
from datetime import datetime
from bson import ObjectId

class User(BaseModel):
    _id: ObjectId
    email: EmailStr
    hashed_password: str
    role: str
    is_active: bool = True
    created_at: datetime
    
