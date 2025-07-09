from datetime import date
import datetime
from typing import Optional
from pydantic import BaseModel


class Performance(BaseModel):
    id: int
    event_id: int
    user_id: int
    score: float
    time: datetime.datetime
    rank: int
    notes: str = None