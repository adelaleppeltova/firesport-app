from pydantic import BaseModel, Field
from typing import List
from datetime import date
from bson import ObjectId

class CompetitionBase(BaseModel):
    competition_name: str
    competition_place: str
    competition_date: date
    categories: List[str] 
    competition_type: str

class CompetitionCreate(CompetitionBase):
    pass   

class CompetitionInDB(CompetitionBase):
    id: str = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True