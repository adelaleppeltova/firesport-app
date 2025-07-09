from datetime import date
import datetime
from typing import Optional
from pydantic import BaseModel


class Event(BaseModel):
    id: int
    name: str
    start_date: datetime
    end_date: datetime
    location: str
    type: str
    description: str = None
    participants: list[str] = [] 
    

