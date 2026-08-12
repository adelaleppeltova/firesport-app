from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

from app.models.result import QualityFlag


class AnomalyDirection(str, Enum):
    fast = "fast"
    slow = "slow"
    none = "none"


class AnomalyRunStatus(str, Enum):
    success = "success"
    skipped = "skipped"
    failed = "failed"


class SkipReasonCounts(BaseModel):
    """Structured skip-reason counters for observability."""
    not_enough_data: int = 0
    not_enough_data_after_cleaning: int = 0
    low_variance: int = 0
    no_valid_results: int = 0


# API Response Models
class AnomalyItem(BaseModel):
    """Single anomaly score item in athlete's anomaly results."""
    result_id: str
    competition_date: datetime
    final_time: float
    score: float
    is_anomaly: bool
    direction: AnomalyDirection
    competition_name: Optional[str] = None
    competition_place: Optional[str] = None
    quality_flag: QualityFlag = QualityFlag.ok
    category_group: Optional[str] = None


class AnomalyRunInfo(BaseModel):
    """Summary info about the latest anomaly run for an athlete."""
    run_id: str
    created_at: datetime
    window_start: datetime
    window_end: datetime
    n_valid_results_in_window: int
    n_invalid_results_in_window: int = 0
    n_anomalies: int
    median_time: Optional[float] = None
    status: AnomalyRunStatus
    reason: Optional[str] = None
    # Model parameters (populated from run document)
    model_name: Optional[str] = None
    contamination_mode: Optional[str] = None
    n_estimators: Optional[int] = None
    random_state: Optional[int] = None
    max_samples: Optional[str] = None
    eps_std: Optional[float] = None
    discipline: Optional[str] = None


class AthleteAnomaliesResponse(BaseModel):
    """Complete anomaly analysis response for an athlete."""
    athlete_id: str
    run: Optional[AnomalyRunInfo] = None
    items: list[AnomalyItem] = Field(default_factory=list)


class WindowListItem(BaseModel):
    """One distinct detection window returned by GET /ml/windows.

    Represents a unique (window_start, window_end) combination that exists
    in the ``anomaly_runs`` collection for a given *window_type*.

    Recommended index on ``anomaly_runs``::

        db.anomaly_runs.create_index(
            [("window_type", 1), ("window.end_date", -1)]
        )
    """
    run_id: str
    anchor_date: str          # YYYY-MM-DD  (== window_end date, UTC)
    window_start: datetime
    window_end: datetime
    label: str                # e.g. "Q1 2026 (2023-04-01\u20132026-03-31)"

class WindowRecomputeSummary(BaseModel):
    """Returned by ``recompute_for_window`` after a single-window ML run."""
    run_id: str
    window_type: str
    anchor_date: str           # YYYY-MM-DD
    window_start: datetime
    window_end: datetime
    processed: int
    skipped: int
    failed: int
    scores_inserted: int
    skip_reason_counts: SkipReasonCounts = Field(default_factory=SkipReasonCounts)


class YearlyBatchItem(BaseModel):
    """Result for one anchor in a yearly batch recompute."""
    anchor_date: str           # YYYY-MM-DD
    window_start: datetime
    window_end: datetime
    status: str                # "computed" | "skipped_existing" | "failed"
    run_id: Optional[str] = None
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    scores_inserted: int = 0
    error: Optional[str] = None


class YearlyBatchResponse(BaseModel):
    """Response for POST /ml/recompute-yearly."""
    date_min: str              # YYYY-MM-DD actually used
    date_max: str              # YYYY-MM-DD actually used
    total_anchors: int
    computed: int
    skipped_existing: int
    failed: int
    results: list[YearlyBatchItem]
