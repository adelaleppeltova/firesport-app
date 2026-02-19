from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional
from enum import Enum

from app.models.athlete import AthleteInDB
from app.models.competition import CompetitionInDB
from app.models.category import CategoryInDB


class TimeStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"

class TimeAttempt(BaseModel):
    attempt: int
    time: Optional[float]
    status: TimeStatus

class ResultBase(BaseModel):
    athlete: AthleteInDB
    competition: CompetitionInDB
    category: CategoryInDB
    
    date: datetime

    start_number: Optional[int] = None

    times: list[TimeAttempt] = []

    time_1: Optional[float] = None
    time_1_status: TimeStatus

    time_2: Optional[float] = None
    time_2_status: TimeStatus

    final_time: Optional[float] = None
    final_time_status: TimeStatus

    rank: Optional[int] = None

class ResultCreate(ResultBase):
    pass

class ResultInDB(ResultBase):
    id: str = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )
