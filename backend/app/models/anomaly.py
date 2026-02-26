from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

from app.ml.anomaly_config import DEFAULT_CONFIG


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
