from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum

from app.models.athlete import AthleteInDB
from app.models.competition import CompetitionInDB
from app.models.category import CategoryInDB


class TimeStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"


class QualityFlag(str, Enum):
    ok = "ok"
    suspicious = "suspicious"

class TimeAttempt(BaseModel):
    attempt: int
    time: Optional[float]
    status: TimeStatus

class ResultBase(BaseModel):
    athlete: AthleteInDB
    competition: CompetitionInDB
    category: CategoryInDB
    
    date: datetime
    team: Optional[str]

    start_number: Optional[int] = None

    times: list[TimeAttempt] = Field(default_factory=list)

    final_time: Optional[float] = None
    final_time_status: TimeStatus

    rank: Optional[int] = None
    quality_flag: QualityFlag = QualityFlag.ok


class ResultCreate(ResultBase):
    pass


class ResultInDB(ResultBase):
    id: str = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class ResultAthleteDetail(BaseModel):
    competition: CompetitionInDB
    category: CategoryInDB
    
    date: datetime
    team: str

    start_number: Optional[int] = None

    times: list[TimeAttempt] = Field(default_factory=list)

    final_time: Optional[float] = None
    final_time_status: TimeStatus

    rank: Optional[int] = None
    quality_flag: QualityFlag = QualityFlag.ok
