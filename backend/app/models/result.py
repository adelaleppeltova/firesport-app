from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, model_validator
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


class MatchStatus(str, Enum):
    matched = "matched"
    needs_review = "needs_review"
    unmatched = "unmatched"


class ImportedAthleteData(BaseModel):
    first_name: str = ""
    last_name: str = ""
    birth_year: Optional[int] = None
    fscode: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fscode(cls, data):
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        fscode = normalized.get("fscode")
        if fscode is not None:
            value = str(fscode).strip()
            normalized["fscode"] = value or None
        return normalized


class TimeAttempt(BaseModel):
    attempt: Optional[int] = None
    time: Optional[float]
    status: TimeStatus

class ResultBase(BaseModel):
    athlete: Optional[AthleteInDB] = None
    competition: CompetitionInDB
    category: CategoryInDB

    date: datetime
    team: Optional[str]
    imported_athlete: ImportedAthleteData = Field(default_factory=ImportedAthleteData)
    match_status: MatchStatus = MatchStatus.matched
    match_reason: Optional[str] = None

    start_number: Optional[int] = None

    times: list[TimeAttempt] = Field(default_factory=list)

    final_time: Optional[float] = None
    final_time_status: TimeStatus

    rank: Optional[int] = None
    quality_flag: QualityFlag = QualityFlag.ok


class ResultInDB(ResultBase):
    id: str = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class ResultAthleteDetail(BaseModel):
    competition: CompetitionInDB
    category: CategoryInDB

    date: datetime
    team: Optional[str] = None

    start_number: Optional[int] = None

    times: list[TimeAttempt] = Field(default_factory=list)

    final_time: Optional[float] = None
    final_time_status: TimeStatus

    rank: Optional[int] = None
    quality_flag: QualityFlag = QualityFlag.ok
