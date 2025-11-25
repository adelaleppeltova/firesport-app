from pydantic import BaseModel
from typing import Optional
from bson import ObjectId

class Result(BaseModel):
    _id: ObjectId
    athlete_id: ObjectId
    competition_id: ObjectId
    category_id: ObjectId
    start_number: int
    time_1: Optional[float]
    time_1_status: str
    time_2: Optional[float]
    time_2_status: str
    final_time: Optional[float]
    final_time_status: str
    rank: int