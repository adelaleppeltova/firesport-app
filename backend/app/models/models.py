from typing import List, Optional
from pydantic import BaseModel


from app.models.athlete import AthleteDetail
from app.models.result import ResultBase


class AthleteDetailPage(BaseModel):
    athlete: AthleteDetail
    results: List[ResultBase]
    best_time: Optional[float] = None
