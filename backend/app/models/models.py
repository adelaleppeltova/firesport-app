from typing import List, Optional
from pydantic import BaseModel


from app.models.athlete import AthleteDetail
from app.models.result import ResultAthleteDetail


class AthleteDetailPage(BaseModel):
    athlete: AthleteDetail
    results: List[ResultAthleteDetail]
    best_time: Optional[float] = None
