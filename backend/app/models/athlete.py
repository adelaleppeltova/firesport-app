from pydantic import BaseModel, Field, ConfigDict, field_serializer
from bson import ObjectId
from typing import Optional, List
from datetime import datetime

class AthleteBase(BaseModel):
    first_name: str
    last_name: str
    birth_year: int
    fscode: Optional[int] = None
    team: str


class AthleteCreate(AthleteBase):
    pass

class AthleteInDB(AthleteBase):
    id: ObjectId = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    @field_serializer("id")
    def serialize_id(self, id: ObjectId) -> str:
        return str(id)

class AthleteOverview(BaseModel):
    """
    Přehled athleta pro kartu na HomePage.
    """

    id: str
    first_name: str
    last_name: str
    birth_year: int
    team: str
    last_active: Optional[str] = None
    total_competitions: int = 0
    best_time: Optional[float] = None
    average_time: Optional[float] = None
    best_time_in_year: Optional[float] = None
    average_time_in_year: Optional[float] = None

class AthleteDetailAthlete(BaseModel):
    """
    Detail athleta pro stránku atleta.
    """

    id: str
    first_name: str
    last_name: str
    birth_year: int
    fscode: Optional[int] = None
    team: str
    category: Optional[str] = None


class AthleteResultRow(BaseModel):
    competition_id: str
    competition_name: str
    competition_date: str
    competition_place: str
    final_time: Optional[float] = None
    rank: Optional[int] = None

    model_config = ConfigDict(
        populate_by_name=True,
    )

class AthleteDetail(BaseModel):
    athlete: AthleteDetailAthlete
    best_time: Optional[float] = None
    results: List[AthleteResultRow]


class AthletesSearch(BaseModel):
    items: List[AthleteInDB]