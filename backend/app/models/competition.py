from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.category_catalog import Discipline

class CompetitionBase(BaseModel):
    name: str
    place: Optional[str] = None
    date: datetime
    league: Optional[List[str]] = None

class CompetitionInDB(CompetitionBase):
    id: str = Field(..., alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class CompetitionCategorySummary(BaseModel):
    id: str
    name: str
    competitors_count: int
    discipline: Optional[Discipline] = None
    type: Optional[str] = None

    model_config = ConfigDict(
        populate_by_name=True,
    )

class CompetitionDetail(CompetitionInDB):
    categories: List[CompetitionCategorySummary]
    athlete_count: int

class CompetitionsPage(BaseModel):
    """Stránkovaný seznam soutěží s vyhledáváním."""
    items: List[CompetitionInDB]
    total: int
    page: int
    page_size: int
