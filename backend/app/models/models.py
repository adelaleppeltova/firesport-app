from typing import List, Optional
from pydantic import BaseModel, Field
from app.category_catalog import Discipline


from app.models.athlete import AthleteDetail
from app.models.result import ResultAthleteDetail


class AthleteDetailPage(BaseModel):
    athlete: AthleteDetail
    results: List[ResultAthleteDetail]
    best_time: Optional[float] = None
    personal_records: dict[Discipline, Optional[float]] = Field(default_factory=dict)
