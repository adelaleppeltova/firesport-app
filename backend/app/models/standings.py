from typing import Literal

from pydantic import BaseModel

from app.models.result import TimeAttempt, TimeStatus


class PublishedRun(BaseModel):
    id: str
    rank: int | None = None
    start_number: str | None = None
    published_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    team: str | None = None
    times: list[TimeAttempt]
    final_time: float | None
    final_time_status: TimeStatus
    final_time_unverified: bool = False


class PublishedTeam(BaseModel):
    id: str
    category_id: str
    category_name: str
    name: str | None
    source_number: int | None
    rank: int | None
    total_time: float | None
    total_status: TimeStatus
    source_url: str
    members: list[PublishedRun]


class HistoricalStanding(BaseModel):
    name: str
    discipline: Literal["60m"] = "60m"
    min_age: int
    max_age: int
    source_url: str | None = None
    result_list_id: str | None = None
    results: list[PublishedRun]


class SupplementalStandings(BaseModel):
    teams: list[PublishedTeam]
    historical: list[HistoricalStanding]
