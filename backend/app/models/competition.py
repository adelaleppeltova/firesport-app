from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List
from datetime import datetime

class CompetitionBase(BaseModel):
    name: str
    place: str
    date: datetime
    league: str

class CompetitionCreate(CompetitionBase):
    pass   

class CompetitionInDB(CompetitionBase):
    id: str = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
    )

class CompetitionCategorySummary(BaseModel):
    id: str
    name: str
    competitors_count: int

    model_config = ConfigDict(
        populate_by_name=True,
    )

class CompetitionDetail(CompetitionInDB):
    categories: List[CompetitionCategorySummary]
    athlete_count: int
