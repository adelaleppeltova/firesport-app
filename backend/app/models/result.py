from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId
from enum import Enum

class TimeStatus(str, Enum):
    valid = "valid"
    invalid = "invalid"
class ResultBase(BaseModel):
    athlete_id: str
    competition_id: str
    category_id: str
    start_number: Optional[int]
    time_1: Optional[float]
    time_1_status: TimeStatus
    time_2: Optional[float]
    time_2_status: TimeStatus
    final_time: Optional[float]
    final_time_status: TimeStatus
    rank: Optional[int]

class ResultCreate(ResultBase):
    pass   

class ResultInDB(ResultBase):
    id: ObjectId = Field(alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True


