from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum

from app.ml.anomaly_config import DEFAULT_CONFIG
from app.models.result import QualityFlag


class AnomalyDirection(str, Enum):
    fast = "fast"
    slow = "slow"
    none = "none"


class AnomalyRunStatus(str, Enum):
    success = "success"
    skipped = "skipped"
    failed = "failed"


class AnomalyRunWindow(BaseModel):
    start_date: datetime
    end_date: datetime
    years: int = 3
    min_results: int = DEFAULT_CONFIG.min_results


class AnomalyRunModel(BaseModel):
    name: str = "IsolationForest"
    params: Dict[str, Any] = Field(
        default_factory=lambda: {
            "n_estimators": DEFAULT_CONFIG.n_estimators,
            "contamination": DEFAULT_CONFIG.contamination,
            "random_state": DEFAULT_CONFIG.random_state,
            "eps_std": DEFAULT_CONFIG.eps_std,
        }
    )
    feature: str = "final_time"
    score_definition: str = "-decision_function"


# API/DTO schemas for anomaly runs and scores
# Note: These are used for API responses and internal DTOs.
# Raw Mongo documents use ObjectId directly; conversion to str happens in routers.
class AnomalyRunSummary(BaseModel):
    athlete_id: str
    n_valid_results_in_window: int
    n_anomalies: int = 0
    threshold_score: Optional[float] = None
    median_time: Optional[float] = None
    reason: Optional[str] = None


class AnomalyRunBase(BaseModel):
    run_id: str
    created_at: datetime
    window: AnomalyRunWindow
    model: AnomalyRunModel
    status: AnomalyRunStatus
    summary: AnomalyRunSummary


class SkipReasonCounts(BaseModel):
    """Structured skip-reason counters for observability."""
    not_enough_data: int = 0
    not_enough_data_after_cleaning: int = 0
    low_variance: int = 0
    no_valid_results: int = 0


class RecomputeResponse(BaseModel):
    """Response model for ML recomputation endpoint."""
    window_start: datetime
    window_end: datetime
    started_at: datetime
    finished_at: datetime
    processed: int
    skipped: int
    failed: int
    scores_inserted: int
    # --- new fields (backward-compatible additions) ---
    min_results_used: int = DEFAULT_CONFIG.min_results
    contamination_used: float = DEFAULT_CONFIG.contamination
    eps_std_used: float = DEFAULT_CONFIG.eps_std
    n_estimators_used: int = DEFAULT_CONFIG.n_estimators
    random_state_used: int = DEFAULT_CONFIG.random_state
    skip_reason_counts: SkipReasonCounts = Field(default_factory=SkipReasonCounts)


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


class AnomalyRunInfo(BaseModel):
    """Summary info about the latest anomaly run for an athlete."""
    run_id: str
    created_at: datetime
    window_start: datetime
    window_end: datetime
    n_valid_results_in_window: int
    n_anomalies: int
    threshold_score: Optional[float] = None
    median_time: Optional[float] = None
    status: AnomalyRunStatus
    reason: Optional[str] = None


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

class ContaminationStats(BaseModel):
    """Per-window min/median/max of per-athlete contamination values."""
    min: float
    median: float
    max: float


class WindowRecomputeSummary(BaseModel):
    """Returned by ``recompute_for_window`` after a single-window ML run."""
    run_id: str
    window_type: str
    anchor_date: str           # YYYY-MM-DD
    window_start: datetime
    window_end: datetime
    contamination_base: str    # human-readable strategy description
    contamination_stats: Optional[ContaminationStats] = None
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