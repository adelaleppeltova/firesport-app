from pydantic import BaseModel, Field, ConfigDict, field_serializer
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
    id: ObjectId = Field(alias="_id")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
    @field_serializer("id")
    def serialize_id(self, id: ObjectId) -> str:
        return str(id)