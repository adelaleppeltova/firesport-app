from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import Optional, List
from enum import Enum


class PerformanceIndicatorTrend(str, Enum):
    up = "up"
    down = "down"
    stable = "stable"
    insufficient = "insufficient"

class PerformanceIndicator(BaseModel):
    trend: PerformanceIndicatorTrend = PerformanceIndicatorTrend.insufficient
    delta_seconds: Optional[float] = None
    new_value: Optional[float] = None
    old_value: Optional[float] = None


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
    performance_indicator: PerformanceIndicator = Field(
        default_factory=PerformanceIndicator
    )
    recent_results: List[RecentResult] = Field(default_factory=list)
    performance_variability: Optional[float] = None  # Standardní odchylka časů v aktuálním roce
    stability_rating: str = "Nedostatek dat"  # Slovní hodnocení stability

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
