"""
ML endpoints for anomaly detection and performance analysis.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from dateutil.relativedelta import relativedelta

from app.db.database import get_db
from app.models.anomaly import RecomputeResponse, SkipReasonCounts
from app.services.anomaly_service import recompute_for_all_athletes


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/recompute", response_model=RecomputeResponse)
async def recompute_anomalies(db=Depends(get_db)):
    """
    Recompute anomalies for all athletes using Isolation Forest.
    
    TODO: Add admin authentication
    
    Returns:
        RecomputeResponse with statistics about the computation.
    """
    started_at = datetime.now(timezone.utc)
    
    # Calculate time window: last 3 years
    window_end = datetime.now(timezone.utc)
    window_start = window_end - relativedelta(years=3)
    
    # Perform recomputation
    counters = await recompute_for_all_athletes(db, window_start, window_end)
    
    finished_at = datetime.now(timezone.utc)
    
    return {
        "window_start": window_start,
        "window_end": window_end,
        "started_at": started_at,
        "finished_at": finished_at,
        "processed": counters["processed"],
        "skipped": counters["skipped"],
        "failed": counters["failed"],
        "scores_inserted": counters["scores_inserted"],
        # new config echo fields
        "min_results_used": counters["min_results_used"],
        "contamination_used": counters["contamination_used"],
        "eps_std_used": counters["eps_std_used"],
        "n_estimators_used": counters["n_estimators_used"],
        "random_state_used": counters["random_state_used"],
        "skip_reason_counts": SkipReasonCounts(
            **counters.get("skip_reason_counts", {}),
        ),
    }
