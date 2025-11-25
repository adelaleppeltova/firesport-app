from pydantic import BaseModel, Field
from bson import ObjectId
from typing import Optional

class AthleteBase(BaseModel):
    first_name: str
    last_name: str
    birth_year: int
    fscode: Optional[int] = None
    team: str


class AthleteCreate(AthleteBase):
    pass

class AthleteInDB(AthleteBase):
    id: str = Field(..., alias="_id")

    class Config:
        allow_population_by_field_name = True
        json_encoders = {ObjectId: str}
        arbitrary_types_allowed = True
