from pydantic import BaseModel
from typing import List
from datetime import date
from bson import ObjectId

class Competition(BaseModel):
    _id: ObjectId
    competition_name: str
    competition_place: str
    competition_date: date
    categories: List[ObjectId] 
    competition_type: str