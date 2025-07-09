from datetime import date
import datetime
from typing import Optional
from pydantic import BaseModel

class Team(BaseModel):
    id: str
    name: str
    athletes: list[str]
    created_at: datetime.datetime = datetime.datetime.now()
    updated_at: datetime.datetime = datetime.datetime.now()

    def add_athlete(self, athlete_id: str):
        if athlete_id not in self.athletes:
            self.athletes.append(athlete_id)
            self.updated_at = datetime.datetime.now()

    def remove_athlete(self, athlete_id: str):
        if athlete_id in self.athletes:
            self.athletes.remove(athlete_id)
            self.updated_at = datetime.datetime.now()