"""Anomaly detection service – orchestrates per-athlete Isolation Forest runs.

All hyper-parameters are read from ``AnomalyConfig`` (single source of truth).
No magic numbers live in this file.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError

from app.models.anomaly import AnomalyRunStatus, AnomalyDirection
from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG
from app.ml.isolation_forest import compute_iforest_anomalies


logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _build_window(
    window_start: datetime,
    window_end: datetime,
    cfg: AnomalyConfig,
) -> Dict[str, Any]:
    """Build window sub-document stored inside an anomaly run."""
    return {
        "start_date": window_start,
        "end_date": window_end,
        "years": 3,
        "min_results": cfg.min_results,
    }


def _build_model(cfg: AnomalyConfig) -> Dict[str, Any]:
    """Build model sub-document with the *actually used* parameters."""
    return {
        "name": "IsolationForest",
        "params": {
            "n_estimators": cfg.n_estimators,
            "contamination": cfg.contamination,
            "random_state": cfg.random_state,
            "eps_std": cfg.eps_std,
        },
        "feature": "final_time",
        "score_definition": "-decision_function",
    }


def _build_run_doc(
    run_id: str,
    created_at: datetime,
    window: Dict[str, Any],
    model: Dict[str, Any],
    status: str,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    """Build run document for ``anomaly_runs`` collection."""
    return {
        "run_id": run_id,
        "created_at": created_at,
        "window": window,
        "model": model,
        "status": status,
        "summary": summary,
    }


def _empty_skip_reason_counts() -> Dict[str, int]:
    """Return zeroed skip-reason counter dict."""
    return {
        "not_enough_data": 0,
        "not_enough_data_after_cleaning": 0,
        "low_variance": 0,
        "no_valid_results": 0,
    }


# ------------------------------------------------------------------
# Per-athlete computation
# ------------------------------------------------------------------

async def compute_for_athlete(
    db: AsyncIOMotorDatabase,
    athlete_id: str,
    window_start: datetime,
    window_end: datetime,
    *,
    config: AnomalyConfig | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Compute anomalies for a single athlete within a time window.

    Parameters
    ----------
    db:
        Motor database instance.
    athlete_id:
        String representation of athlete ``ObjectId``.
    window_start / window_end:
        Inclusive date boundaries.
    config:
        Hyper-parameters.  Defaults to ``DEFAULT_CONFIG``.

    Returns
    -------
    tuple[run_doc, score_docs]
        ``run_doc``  → insert into ``anomaly_runs``
        ``score_docs`` → insert into ``anomaly_scores`` (empty on skip/fail)

    Never raises; all errors are caught and returned as *failed* runs.
    """
    cfg = config or DEFAULT_CONFIG
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    window = _build_window(window_start, window_end, cfg)
    model = _build_model(cfg)

    try:
        athlete_oid = ObjectId(athlete_id)

        # --- load valid results in window --------------------------------
        results = await db["results"].find(
            {
                "athlete": athlete_oid,
                "final_time_status": "valid",
                "date": {"$gte": window_start, "$lte": window_end},
            },
            projection={"_id": 1, "final_time": 1, "date": 1},
        ).sort("date", 1).to_list(None)

        n_valid_results = len(results)

        # --- early skip: no valid results at all -------------------------
        if n_valid_results == 0:
            summary = {
                "athlete_id": athlete_oid,
                "n_valid_results_in_window": 0,
                "n_anomalies": 0,
                "threshold_score": None,
                "median_time": None,
                "reason": "no_valid_results",
            }
            return (
                _build_run_doc(run_id, created_at, window, model,
                               AnomalyRunStatus.skipped.value, summary),
                [],
            )

        # --- early skip: fewer results than min_results ------------------
        if n_valid_results < cfg.min_results:
            summary = {
                "athlete_id": athlete_oid,
                "n_valid_results_in_window": n_valid_results,
                "n_anomalies": 0,
                "threshold_score": None,
                "median_time": None,
                "reason": "not_enough_data",
            }
            return (
                _build_run_doc(run_id, created_at, window, model,
                               AnomalyRunStatus.skipped.value, summary),
                [],
            )

        # --- run ML ------------------------------------------------------
        times = [r["final_time"] for r in results]
        ml_result = compute_iforest_anomalies(times, config=cfg)
        ml_status = ml_result.get("status")

        if ml_status == "skipped":
            reason = ml_result.get("reason", "unknown")
            summary = {
                "athlete_id": athlete_oid,
                "n_valid_results_in_window": n_valid_results,
                "n_anomalies": 0,
                "threshold_score": None,
                "median_time": None,
                "reason": reason,
            }
            return (
                _build_run_doc(run_id, created_at, window, model,
                               AnomalyRunStatus.skipped.value, summary),
                [],
            )

        # --- ML succeeded ------------------------------------------------
        scores = ml_result.get("scores", [])
        threshold_score = ml_result.get("threshold_score", 0.0)
        median_time = ml_result.get("median_time", 0.0)
        n_anomalies = ml_result.get("n_anomalies", 0)
        is_anomaly_list = ml_result.get("is_anomaly", [])
        direction_list = ml_result.get("direction", [])

        summary = {
            "athlete_id": athlete_oid,
            "n_valid_results_in_window": n_valid_results,
            "n_anomalies": n_anomalies,
            "threshold_score": threshold_score,
            "median_time": median_time,
            "reason": None,
        }
        run_doc = _build_run_doc(
            run_id, created_at, window, model,
            AnomalyRunStatus.success.value, summary,
        )

        score_docs: List[Dict[str, Any]] = []
        for i, result in enumerate(results):
            score_docs.append({
                "run_id": run_id,
                "created_at": created_at,
                "athlete_id": athlete_oid,
                "result_id": result["_id"],
                "competition_date": result["date"],
                "final_time": result["final_time"],
                "score": scores[i] if i < len(scores) else 0.0,
                "threshold_score": threshold_score,
                "median_time": median_time,
                "is_anomaly": is_anomaly_list[i] if i < len(is_anomaly_list) else False,
                "direction": (
                    direction_list[i]
                    if i < len(direction_list)
                    else AnomalyDirection.none.value
                ),
            })

        return run_doc, score_docs

    except Exception as e:
        logger.exception("Error computing anomalies for athlete %s: %s", athlete_id, e)
        try:
            athlete_oid = ObjectId(athlete_id)
        except Exception:
            athlete_oid = None

        summary = {
            "athlete_id": athlete_oid,
            "athlete_id_str": athlete_id if not athlete_oid else None,
            "n_valid_results_in_window": 0,
            "n_anomalies": 0,
            "threshold_score": None,
            "median_time": None,
            "reason": str(e),
        }
        return (
            _build_run_doc(run_id, created_at, window, model,
                           AnomalyRunStatus.failed.value, summary),
            [],
        )


# ------------------------------------------------------------------
# Bulk recomputation
# ------------------------------------------------------------------

async def recompute_for_all_athletes(
    db: AsyncIOMotorDatabase,
    window_start: datetime,
    window_end: datetime,
    *,
    config: AnomalyConfig | None = None,
) -> Dict[str, Any]:
    """Recompute anomalies for every athlete in the database.

    Returns a dict with counters **and** structured skip-reason counts
    for full observability.
    """
    cfg = config or DEFAULT_CONFIG

    counters: Dict[str, Any] = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "scores_inserted": 0,
        "skip_reason_counts": _empty_skip_reason_counts(),
        # echo back the used params so the API can forward them
        "min_results_used": cfg.min_results,
        "contamination_used": cfg.contamination,
        "eps_std_used": cfg.eps_std,
        "n_estimators_used": cfg.n_estimators,
        "random_state_used": cfg.random_state,
    }

    try:
        athletes = await db["athletes"].find(
            {}, projection={"_id": 1},
        ).to_list(None)

        logger.info("Starting anomaly computation for %d athletes", len(athletes))

        for athlete_doc in athletes:
            athlete_id = str(athlete_doc["_id"])

            run_doc, score_docs = await compute_for_athlete(
                db, athlete_id, window_start, window_end, config=cfg,
            )

            # persist run doc
            await db["anomaly_runs"].insert_one(run_doc)

            status = run_doc["status"]
            if status == AnomalyRunStatus.success.value:
                counters["processed"] += 1
                if score_docs:
                    try:
                        result = await db["anomaly_scores"].insert_many(
                            score_docs, ordered=False,
                        )
                        counters["scores_inserted"] += len(result.inserted_ids)
                    except BulkWriteError as e:
                        logger.warning(
                            "BulkWriteError inserting scores for athlete %s: %s",
                            athlete_id, e.details,
                        )
                        n_ins = (e.details or {}).get("nInserted", len(score_docs))
                        counters["scores_inserted"] += n_ins

            elif status == AnomalyRunStatus.skipped.value:
                counters["skipped"] += 1
                reason = (run_doc.get("summary") or {}).get("reason", "unknown")
                sr = counters["skip_reason_counts"]
                if reason in sr:
                    sr[reason] += 1
                else:
                    # catch-all for any unexpected reason string
                    sr.setdefault(reason, 0)
                    sr[reason] += 1

            elif status == AnomalyRunStatus.failed.value:
                counters["failed"] += 1

        logger.info(
            "Anomaly computation completed. processed=%d skipped=%d failed=%d scores=%d",
            counters["processed"], counters["skipped"],
            counters["failed"], counters["scores_inserted"],
        )

        return counters

    except Exception as e:
        logger.exception("Critical error in recompute_for_all_athletes: %s", e)
        return counters
