from typing import Optional

from pydantic import BaseModel, Field

from app.models.result import ImportedAthleteData, MatchStatus


class AssignAthleteRequest(BaseModel):
    athlete_id: str


class AdminReviewItem(BaseModel):
    result_id: str
    imported_athlete: ImportedAthleteData
    match_status: MatchStatus
    match_reason: Optional[str] = None
    team: Optional[str] = None
    date: Optional[str] = None


class AdminReviewSummary(BaseModel):
    total: int
    needs_review: int = 0
    unmatched: int = 0


class AdminReviewResponse(BaseModel):
    summary: AdminReviewSummary
    items: list[AdminReviewItem]


class AthleteMergeCandidate(BaseModel):
    athlete_id: str
    first_name: str
    last_name: str
    birth_year: Optional[int] = None
    fs_codes: list[str] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    result_count: int = 0


class AthleteMergeCandidatesResponse(BaseModel):
    items: list[AthleteMergeCandidate]


class AthleteMergeResponse(BaseModel):
    ok: bool = True
    source_athlete_id: str
    target_athlete_id: str
    moved_results: int = 0
