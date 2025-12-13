from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List
from enum import Enum


class PerformanceTrend(str, Enum):
    improving = "improving"
    declining = "declining"
    stable = "stable"


class RecentResult(BaseModel):
    final_time: Optional[float]
    rank: Optional[int]


class AthleteBase(BaseModel):
    first_name: str
    last_name: str
    birth_year: int
    fscode: Optional[int] = None
    team: str

class AthleteCreate(AthleteBase):
    pass

class AthleteInDB(AthleteBase):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

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
    performance_trend: PerformanceTrend = PerformanceTrend.stable
    recent_results: List[RecentResult] = []

class AthleteDetail(BaseModel):
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
    best_time: Optional[float] = None

    model_config = ConfigDict(
        populate_by_name=True,
    )

class AthletesSearch(BaseModel):
    items: List[AthleteInDB]

