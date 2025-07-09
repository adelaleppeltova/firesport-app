from datetime import date
import datetime
from typing import Optional
from pydantic import BaseModel

class User(BaseModel):
    id: int
    username: str
    email: str
    password: str
    rights: str