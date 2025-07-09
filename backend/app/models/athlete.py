from datetime import date
import datetime
from typing import Optional
from pydantic import BaseModel
from app.models.team import Team
from typing import List, Union

class Athlete(BaseModel):
    id: str
    first_name: str
    last_name: str
    adress: str
    email: Optional[str] = None
    phone: Optional[str] = None
    birth_date: date
    registration_number: int
    category: str
    team: List[Team]
