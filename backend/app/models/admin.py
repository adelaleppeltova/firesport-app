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


class ImportStats(BaseModel):
    total_imported: int = 0
    review_required: int = 0
    athletes_created_new: int = 0
    athletes_existing_matched: int = 0
    categories_created: int = 0
    competitions_created: int = 0
    results_created: int = 0
    results_matched: int = 0
    results_needs_review: int = 0
    results_unmatched: int = 0
    errors: list[str] = Field(default_factory=list)


class DataImportResponse(BaseModel):
    success: bool = True
    message: str
    data: ImportStats


class AdminImportStats(ImportStats):
    files_processed: int = 0


class AdminImportResponse(BaseModel):
    success: bool = True
    message: str
    data: AdminImportStats


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


class AdminResultAssignmentResponse(BaseModel):
    ok: bool = True
    result_id: str
    athlete_id: str
    auto_reassigned: int = 0


class AdminResultUnassignmentResponse(BaseModel):
    ok: bool = True
    result_id: str
    match_status: MatchStatus


class AdminDeleteReviewResponse(BaseModel):
    ok: bool = True
    deleted_count: int
