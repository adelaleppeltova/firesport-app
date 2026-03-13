from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from enum import Enum


class PerformanceIndicatorTrend(str, Enum):
    up = "up"
    down = "down"
    stable = "stable"
    insufficient = "insufficient"

class RecentResult(BaseModel):
    final_time: Optional[float]
    rank: Optional[int]

class PerformanceIndicator(BaseModel):
    trend: PerformanceIndicatorTrend = PerformanceIndicatorTrend.insufficient
    delta_seconds: Optional[float] = None
    new_value: Optional[float] = None
    old_value: Optional[float] = None
    average_time: Optional[float] = None
    recent_results: Optional[List[RecentResult]] = Field(default_factory=list)

class BestPerformance(BaseModel):
    """Nejlepší výkon - čas, soutěž a místo"""
    time: Optional[float] = None
    competition_place: Optional[str] = None
    competition_date: Optional[str] = None


class AthleteBase(BaseModel):
    first_name: str
    last_name: str
    teams: List[str] = Field(default_factory=list)
    fscode: Optional[int] = None
    birth_year: Optional[int] = None
    district: Optional[str] = None

class AthleteCreate(AthleteBase):
    pass

class AthleteInDB(AthleteBase):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class AthleteOverview(AthleteInDB):
    """
    Přehled athleta pro kartu na HomePage.
    """
    last_active: Optional[str] = None
    total_competitions: int = 0
    best_time: Optional[float] = None
    average_time: Optional[float] = None
    performance_indicator: Optional[PerformanceIndicator] = Field(
        default_factory=PerformanceIndicator
    )
    performance_variability: Optional[float] = None  # Rozsah (max - min) poslednich platnych casu
    stability_rating: str = "Nedostatek dat"  # Slovní hodnocení stability
    best_performance: BestPerformance = Field(default_factory=BestPerformance)  # Nejlepší výkon s detaily soutěže

class AthleteDetail(AthleteInDB):
    """
    Detail athleta pro stránku atleta.
    """
    category: Optional[str] = None
    best_time: Optional[float] = None

class AthletesSearch(BaseModel):
    items: List[AthleteInDB]

class AthletesPage(BaseModel):
    """Stránkovaný seznam atletů s vyhledáváním."""
    items: List[AthleteInDB]
    total: int
    page: int
    page_size: int


class PerformanceDataPoint(BaseModel):
    """Datový bod pro graf vývoje výkonu v čase"""
    date: str  # ISO formát nebo "YYYY-MM-DD"
    time: float  # Čas v sekundách
    rank: Optional[int] = None
    place: Optional[str] = None

class PerformanceByYear(BaseModel):
    """Data pro graf vývoje výkonu po sezónách"""
    years: List[int]  # [2022, 2023, 2024]
    data: dict  # {2022: [{"date": "2022-05-15", "time": 16.5, "rank": 1}, ...], ...}

class TimeAttemptOut(BaseModel):
    attempt: Optional[int] = None
    time: Optional[float] = None
    status: str = "invalid"

class RaceInYear(BaseModel):
    competition_id: Optional[str] = None
    competition_name: Optional[str] = None
    competition_place: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None  # YYYY-MM-DD
    final_time: Optional[float] = None
    final_time_status: Optional[str] = None
    rank: Optional[int] = None
    times: List[TimeAttemptOut] = Field(default_factory=list)


class PerformanceInYear(BaseModel):
    year: int
    average_time: Optional[float]
    best_time: Optional[float]
    competitions: int
    races: List[RaceInYear]


class CategoryRaceStats(BaseModel):
    """Statistiky závodů v jedné skupině kategorií (bez ohledu na okno detekce)."""
    total_races: int
    best_time: Optional[float] = None


class AthleteCategoryStatsResponse(BaseModel):
    """Mapa category_group → statistiky ze všech závodů v DB."""
    stats: dict[str, CategoryRaceStats] = Field(default_factory=dict)
