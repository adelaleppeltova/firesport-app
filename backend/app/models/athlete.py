from pydantic import BaseModel
from bson import ObjectId

class Athlete(BaseModel):
    _id: ObjectId
    first_name: str
    last_name: str
    birth_year: int
    fscode: int
    team: str