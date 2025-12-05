from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List
from datetime import date

class CompetitionBase(BaseModel):
    name: str
    place: str
    date: date
    categories: List[str] 
    type: str

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

class CompetitionDetail(BaseModel):
    id: str
    name: str
    place: str
    date: date
    type: str
    categories: List[CompetitionCategorySummary]
    athlete_count: int
