"""Anomaly detection service – orchestrates per-athlete Isolation Forest runs.

All hyper-parameters are read from ``AnomalyConfig`` (single source of truth).
No magic numbers live in this file.
"""

import logging
import statistics
from datetime import date, datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError

from app.models.anomaly import (
    AnomalyRunStatus,
    AnomalyDirection,
    ContaminationStats,
    YearlyBatchItem,
    YearlyBatchResponse,
    SkipReasonCounts,
    WindowRecomputeSummary,
)
from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG
from app.ml.isolation_forest import compute_iforest_anomalies
from app.services.quality_flag_service import recompute_quality_flags
from app.services.windows import (
    window_for_anchor,
    adaptive_contamination,
    list_year_anchors,
    is_year_end,
    year_label,
)


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
    window_type: str = "yearly_3y",
) -> Dict[str, Any]:
    """Build run document for ``anomaly_runs`` collection.

    ``window_type`` is a top-level field used for efficient filtering.
    Recommended compound index: (window_type, window.end_date DESC).
    """
    return {
        "run_id": run_id,
        "created_at": created_at,
        "window_type": window_type,
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

        # Přepočítej quality_flag pro všechny výsledky
        try:
            qf_stats = await recompute_quality_flags(db)
            counters["quality_flag_stats"] = qf_stats
        except Exception as qf_err:
            logger.exception("quality_flag recompute failed: %s", qf_err)
            counters["quality_flag_stats"] = {"error": str(qf_err)}

        return counters

    except Exception as e:
        logger.exception("Critical error in recompute_for_all_athletes: %s", e)
        return counters


# ------------------------------------------------------------------
# Window listing
# ------------------------------------------------------------------

async def list_detection_windows(
    db: AsyncIOMotorDatabase,
    window_type: str = "yearly_3y",
) -> list[dict]:
    """Return distinct valid detection windows from ``anomaly_runs``.

    Filters applied
    ---------------
    1. ``window_type == window_type`` (parameter).
    2. ``is_superseded != True`` – only active (non-replaced) runs.
    3. Anchor validity: for ``yearly_3y`` uses ``is_year_end``.
       Runs with non-standard anchor dates (e.g. mid-month legacy runs) are excluded.
    4. ``stats.processed > 0 OR stats.scores_inserted > 0`` – exclude empty
       runs (soft filter: runs without the ``stats`` field are kept).

    Results are sorted by ``window.end_date`` descending (newest first).

    Recommended index::

        db.anomaly_runs.create_index(
            [("window_type", 1), ("window.end_date", -1)]
        )
    """
    pipeline = [
        {
            "$match": {
                "window_type": window_type,
                "is_superseded": {"$ne": True},
            }
        },
        {
            "$group": {
                "_id": {
                    "window_start": "$window.start_date",
                    "window_end": "$window.end_date",
                },
                "run_id": {"$first": "$run_id"},
                "processed": {"$first": "$stats.processed"},
                "scores_inserted": {"$first": "$stats.scores_inserted"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "run_id": 1,
                "window_start": "$_id.window_start",
                "window_end": "$_id.window_end",
                "processed": 1,
                "scores_inserted": 1,
            }
        },
        {"$sort": {"window_end": -1}},
    ]
    raw = await db["anomaly_runs"].aggregate(pipeline).to_list(None)

    result = []
    for row in raw:
        end_date = row.get("window_end")
        if end_date is None:
            continue
        # Normalise Motor naive UTC datetimes
        if isinstance(end_date, datetime) and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
            row["window_end"] = end_date

        # Filter 3: only valid anchor dates (year-end = Dec 31)
        valid_anchor = is_year_end(end_date)

        if not valid_anchor:
            logger.warning(
                "Skipping non-expected-anchor window %s for window_type=%s (run=%s)",
                end_date.date().isoformat() if hasattr(end_date, "date") else end_date,
                window_type,
                row.get("run_id"),
            )
            continue

        # Filter 4 (soft): skip runs that produced zero results, but only
        # when the stats field is present (legacy runs without it are kept).
        processed = row.get("processed")
        scores = row.get("scores_inserted")
        if processed is not None and scores is not None:
            if processed == 0 and scores == 0:
                continue

        result.append(row)

    return result


# ------------------------------------------------------------------
# Single-window recomputation
# ------------------------------------------------------------------

def _contamination_stats(values: list[float]) -> Optional[ContaminationStats]:
    """Compute min / median / max of per-athlete contamination values.

    Returns ``None`` when *values* is empty.

    Parameters
    ----------
    values:
        List of contamination floats actually used across athletes.

    Returns
    -------
    ContaminationStats | None
    """
    if not values:
        return None
    return ContaminationStats(
        min=min(values),
        median=statistics.median(values),
        max=max(values),
    )


async def _supersede_existing_window_run(
    db: AsyncIOMotorDatabase,
    window_type: str,
    anchor_dt: datetime,
) -> Optional[str]:
    """Mark any existing run for this window as superseded and purge its scores.

    Idempotence strategy: we do **not** delete the old run document so that
    history is preserved.  We add ``is_superseded=True`` and remove scores
    belonging to it.  A new run document with a fresh ``run_id`` is then
    created by the caller.

    Parameters
    ----------
    db:
        Motor database.
    window_type:
        E.g. ``"yearly_3y"``.
    anchor_dt:
        Timezone-aware UTC datetime matching ``window.end_date``.

    Returns
    -------
    str | None
        Old ``run_id`` if a run was found and superseded, else ``None``.
    """
    existing = await db["anomaly_runs"].find_one(
        {
            "window_type": window_type,
            "window.end_date": anchor_dt,
            "is_superseded": {"$ne": True},
        }
    )
    if existing is None:
        return None

    old_run_id: str = existing["run_id"]
    now = datetime.now(timezone.utc)

    await db["anomaly_runs"].update_one(
        {"run_id": old_run_id},
        {"$set": {"is_superseded": True, "superseded_at": now}},
    )
    del_result = await db["anomaly_scores"].delete_many({"run_id": old_run_id})
    logger.info(
        "Superseded run %s for window_type=%s anchor=%s (deleted %d scores)",
        old_run_id, window_type, anchor_dt.date().isoformat(), del_result.deleted_count,
    )
    return old_run_id


def _build_window_run_doc(
    run_id: str,
    created_at: datetime,
    window_start: datetime,
    window_end: datetime,
    window_years: int,
    window_type: str,
    min_results_used: int,
    contamination_base: str,
    contamination_stats: Optional[ContaminationStats],
    counters: Dict[str, Any],
    cfg: AnomalyConfig,
) -> Dict[str, Any]:
    """Assemble the single ``anomaly_runs`` document for a window-level run."""
    c_stats = contamination_stats.model_dump() if contamination_stats else None
    return {
        "run_id": run_id,
        "created_at": created_at,
        "window_type": window_type,
        "window": {
            "start_date": window_start,
            "end_date": window_end,
            "years": window_years,
            "min_results": min_results_used,
        },
        "model": {
            "name": "IsolationForest",
            "params": {
                "n_estimators": cfg.n_estimators,
                "contamination_base": contamination_base,
                "random_state": cfg.random_state,
                "eps_std": cfg.eps_std,
            },
            "feature": "final_time",
            "score_definition": "-decision_function",
        },
        "status": AnomalyRunStatus.success.value,
        "stats": {
            "processed": counters["processed"],
            "skipped": counters["skipped"],
            "failed": counters["failed"],
            "scores_inserted": counters["scores_inserted"],
            "skip_reason_counts": counters["skip_reason_counts"],
            "contamination": c_stats,
        },
    }


async def recompute_for_window(
    db: AsyncIOMotorDatabase,
    *,
    anchor_date: date,
    window_years: int = 3,
    window_type: str = "yearly_3y",
    min_results_used: int = 10,
    use_adaptive_contamination: bool = True,
) -> WindowRecomputeSummary:
    """Recompute Isolation Forest anomalies for all athletes within one window.

    The window boundaries are derived from *anchor_date* using
    :func:`~app.services.windows.window_for_anchor`.

    Idempotence
    -----------
    If a non-superseded run already exists for ``(window_type, anchor_date)``
    it is marked ``is_superseded=True`` and its scores are deleted before a
    new run is created.  This is safe without transactions because:

    1. The old run is preserved (only flagged) for audit purposes.
    2. Scores referencing the old ``run_id`` are removed atomically per
       ``delete_many``.
    3. The new run is inserted afterwards.

    Contamination strategy
    ----------------------
    When *use_adaptive_contamination* is ``True`` (default), each athlete
    gets ``contamination = clamp(1/n, 0.02, 0.10)``.  Otherwise 0.05 is
    used for all athletes.  The strategy string is stored in
    ``model.params.contamination_base`` on the run document.

    Parameters
    ----------
    db:
        Async Motor database.
    anchor_date:
        Anchor date (e.g. ``date(2025, 12, 31)`` for a year-end window).
    window_years:
        Rolling window length in years.  Defaults to 3.
    window_type:
        Label stored on the run document.  Defaults to ``"yearly_3y"``.
    min_results_used:
        Minimum valid results required per athlete to run the model.
    use_adaptive_contamination:
        If ``True``, contamination = ``adaptive_contamination(n)``.
        If ``False``, contamination = 0.05 (fixed default).

    Returns
    -------
    WindowRecomputeSummary
        Aggregated statistics for the entire window run.
    """
    # 1) Compute window boundaries
    anchor_dt = datetime(
        anchor_date.year, anchor_date.month, anchor_date.day, tzinfo=timezone.utc
    )
    window_start, window_end = window_for_anchor(anchor_dt, years=window_years)

    contamination_base = (
        "adaptive(1/n clamped 0.02-0.10)" if use_adaptive_contamination else "fixed(0.05)"
    )

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)

    counters: Dict[str, Any] = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "scores_inserted": 0,
        "skip_reason_counts": _empty_skip_reason_counts(),
    }
    contaminations_used: list[float] = []

    cfg_base = AnomalyConfig(
        min_results=min_results_used,
        n_estimators=DEFAULT_CONFIG.n_estimators,
        eps_std=DEFAULT_CONFIG.eps_std,
        random_state=DEFAULT_CONFIG.random_state,
        contamination=DEFAULT_CONFIG.contamination,  # overridden per athlete below
    )

    try:
        # 2) Idempotence: supersede previous run for this window if any
        await _supersede_existing_window_run(db, window_type, anchor_dt)

        # 3) Load all valid results in window (one DB round-trip)
        raw_results = await db["results"].find(
            {
                "final_time_status": "valid",
                "final_time": {"$ne": None},
                "date": {"$gte": window_start, "$lte": window_end},
            },
            projection={"_id": 1, "athlete": 1, "final_time": 1, "date": 1},
        ).sort("date", 1).to_list(None)

        # 4) Group by athlete_id
        athlete_results: Dict[str, List[Dict[str, Any]]] = {}
        for r in raw_results:
            aid = str(r["athlete"])
            athlete_results.setdefault(aid, []).append(r)

        all_score_docs: List[Dict[str, Any]] = []

        # 5) Per-athlete processing
        for athlete_id, results in athlete_results.items():
            n = len(results)
            sr = counters["skip_reason_counts"]

            if n < min_results_used:
                counters["skipped"] += 1
                sr["not_enough_data"] = sr.get("not_enough_data", 0) + 1
                continue

            # Determine contamination
            if use_adaptive_contamination:
                c = adaptive_contamination(n)
            else:
                c = 0.05
            contaminations_used.append(c)

            # Build per-athlete config with overridden contamination
            cfg = AnomalyConfig(
                min_results=cfg_base.min_results,
                n_estimators=cfg_base.n_estimators,
                eps_std=cfg_base.eps_std,
                random_state=cfg_base.random_state,
                contamination=c,
            )

            times = [r["final_time"] for r in results]
            try:
                ml_result = compute_iforest_anomalies(times, config=cfg)
            except Exception as ml_exc:
                logger.exception(
                    "ML error for athlete %s in window %s: %s",
                    athlete_id, anchor_date.isoformat(), ml_exc,
                )
                counters["failed"] += 1
                continue

            ml_status = ml_result.get("status")
            if ml_status == "skipped":
                reason = ml_result.get("reason", "unknown")
                counters["skipped"] += 1
                sr[reason] = sr.get(reason, 0) + 1
                contaminations_used.pop()  # don't count skipped athlete
                continue

            # ML succeeded – build score docs
            scores = ml_result.get("scores", [])
            is_anomaly_list = ml_result.get("is_anomaly", [])
            direction_list = ml_result.get("direction", [])
            threshold_score = ml_result.get("threshold_score", 0.0)
            median_time = ml_result.get("median_time", 0.0)
            athlete_oid = ObjectId(athlete_id)

            for i, result in enumerate(results):
                all_score_docs.append({
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
                    "contamination_used": c,
                })
            counters["processed"] += 1

        # 6) Insert scores in bulk
        if all_score_docs:
            try:
                ins = await db["anomaly_scores"].insert_many(
                    all_score_docs, ordered=False
                )
                counters["scores_inserted"] = len(ins.inserted_ids)
            except BulkWriteError as bwe:
                n_ins = (bwe.details or {}).get("nInserted", len(all_score_docs))
                counters["scores_inserted"] = n_ins
                logger.warning("BulkWriteError inserting window scores: %s", bwe.details)

        # 7) Compute contamination stats
        c_stats = _contamination_stats(contaminations_used)

        # 8) Persist run document
        run_doc = _build_window_run_doc(
            run_id=run_id,
            created_at=created_at,
            window_start=window_start,
            window_end=window_end,
            window_years=window_years,
            window_type=window_type,
            min_results_used=min_results_used,
            contamination_base=contamination_base,
            contamination_stats=c_stats,
            counters=counters,
            cfg=cfg_base,
        )
        await db["anomaly_runs"].insert_one(run_doc)

        logger.info(
            "recompute_for_window done: anchor=%s processed=%d skipped=%d failed=%d scores=%d",
            anchor_date.isoformat(),
            counters["processed"], counters["skipped"],
            counters["failed"], counters["scores_inserted"],
        )

        return WindowRecomputeSummary(
            run_id=run_id,
            window_type=window_type,
            anchor_date=anchor_date.isoformat(),
            window_start=window_start,
            window_end=window_end,
            contamination_base=contamination_base,
            contamination_stats=c_stats,
            processed=counters["processed"],
            skipped=counters["skipped"],
            failed=counters["failed"],
            scores_inserted=counters["scores_inserted"],
            skip_reason_counts=SkipReasonCounts(**counters["skip_reason_counts"]),
        )

    except Exception as exc:
        logger.exception("Critical error in recompute_for_window: %s", exc)
        raise


# ------------------------------------------------------------------
# Quarterly batch recomputation
# ------------------------------------------------------------------

async def get_results_date_range(db: AsyncIOMotorDatabase) -> tuple[datetime, datetime]:
    """Return the (min_date, max_date) of all results in the database.

    Used to derive batch boundaries when the caller does not supply them.

    Parameters
    ----------
    db:
        Motor database instance.

    Returns
    -------
    tuple[datetime, datetime]
        Both values are timezone-aware UTC datetimes.

    Raises
    ------
    ValueError
        If no results exist yet in the collection.
    """
    pipeline = [
        {
            "$group": {
                "_id": None,
                "min_date": {"$min": "$date"},
                "max_date": {"$max": "$date"},
            }
        }
    ]
    rows = await db["results"].aggregate(pipeline).to_list(1)
    if not rows:
        raise ValueError("No results found in the database – cannot derive date range.")
    min_d: datetime = rows[0]["min_date"]
    max_d: datetime = rows[0]["max_date"]
    # Motor may return naive UTC – normalise
    if min_d.tzinfo is None:
        min_d = min_d.replace(tzinfo=timezone.utc)
    if max_d.tzinfo is None:
        max_d = max_d.replace(tzinfo=timezone.utc)
    return min_d, max_d


# ------------------------------------------------------------------
# Yearly batch recomputation
# ------------------------------------------------------------------

async def recompute_yearly_batch(
    db: AsyncIOMotorDatabase,
    *,
    date_min: Optional[datetime] = None,
    date_max: Optional[datetime] = None,
    force: bool = False,
    window_years: int = 3,
    window_type: str = "yearly_3y",
    min_results_used: int = 10,
    use_adaptive_contamination: bool = True,
) -> YearlyBatchResponse:
    """Recompute Isolation Forest for every yearly anchor (Dec 31) in a date range.

    For each year-end anchor (December 31) whose date lies within
    ``[date_min, date_max]``, calls :func:`recompute_for_window`.

    Behaviour
    ---------
    * If *date_min* / *date_max* are ``None``, they are derived from
      ``min(results.date)`` / ``max(results.date)`` via
      :func:`get_results_date_range`.
    * If ``force=False`` (default) and a non-superseded run already exists
      for an anchor, that anchor is **skipped** (status ``"skipped_existing"``).
    * If ``force=True``, :func:`recompute_for_window` is called for every
      anchor; its built-in idempotence logic handles superseding.

    Parameters
    ----------
    db:
        Motor database instance.
    date_min:
        Lower bound for anchor selection (inclusive, UTC).  Derived from
        DB when ``None``.
    date_max:
        Upper bound for anchor selection (inclusive, UTC).  Derived from
        DB when ``None``.
    force:
        Re-run even when a run already exists for the anchor.
    window_years:
        Rolling window size in years passed to :func:`recompute_for_window`.
    window_type:
        Tag stored on every run document.  Defaults to ``"yearly_3y"``.
    min_results_used:
        Minimum per-athlete results threshold.
    use_adaptive_contamination:
        Whether to use adaptive contamination strategy.

    Returns
    -------
    YearlyBatchResponse
        Summary of all anchors processed, skipped, or failed.
    """
    # 1) Resolve date bounds
    if date_min is None or date_max is None:
        logger.info("Deriving date range from results collection ...")
        db_min, db_max = await get_results_date_range(db)
        if date_min is None:
            date_min = db_min
        if date_max is None:
            date_max = db_max

    logger.info(
        "Yearly batch recompute: range=%s \u2013 %s force=%s",
        date_min.date().isoformat(), date_max.date().isoformat(), force,
    )

    # 2) Generate yearly anchors (Dec 31 for each year in range)
    anchors = list_year_anchors(date_min, date_max)
    logger.info("Found %d yearly anchors in range", len(anchors))

    # 3) Pre-load existing non-superseded runs for skip logic (force=False)
    existing_anchor_dates: set[str] = set()
    if not force:
        cursor = db["anomaly_runs"].find(
            {
                "window_type": window_type,
                "is_superseded": {"$ne": True},
            },
            projection={"window.end_date": 1},
        )
        async for doc in cursor:
            end_date = doc.get("window", {}).get("end_date")
            if end_date is not None:
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                existing_anchor_dates.add(end_date.date().isoformat())

    # 4) Process each anchor
    batch_results: list[YearlyBatchItem] = []
    n_computed = 0
    n_skipped_existing = 0
    n_failed = 0

    for anchor_dt in anchors:
        anchor_str = anchor_dt.date().isoformat()
        w_start, w_end = window_for_anchor(anchor_dt, years=window_years)

        if (not force) and anchor_str in existing_anchor_dates:
            logger.info("Anchor %s already has a run \u2013 skipping (force=False)", anchor_str)
            batch_results.append(
                YearlyBatchItem(
                    anchor_date=anchor_str,
                    window_start=w_start,
                    window_end=w_end,
                    status="skipped_existing",
                )
            )
            n_skipped_existing += 1
            continue

        try:
            logger.info("Processing yearly anchor %s ...", anchor_str)
            summary = await recompute_for_window(
                db,
                anchor_date=anchor_dt.date(),
                window_years=window_years,
                window_type=window_type,
                min_results_used=min_results_used,
                use_adaptive_contamination=use_adaptive_contamination,
            )
            batch_results.append(
                YearlyBatchItem(
                    anchor_date=anchor_str,
                    window_start=summary.window_start,
                    window_end=summary.window_end,
                    status="computed",
                    run_id=summary.run_id,
                    processed=summary.processed,
                    skipped=summary.skipped,
                    failed=summary.failed,
                    scores_inserted=summary.scores_inserted,
                )
            )
            n_computed += 1
            logger.info(
                "Anchor %s done: processed=%d skipped=%d scores=%d",
                anchor_str, summary.processed, summary.skipped, summary.scores_inserted,
            )
        except Exception as exc:
            logger.exception("Anchor %s failed: %s", anchor_str, exc)
            batch_results.append(
                YearlyBatchItem(
                    anchor_date=anchor_str,
                    window_start=w_start,
                    window_end=w_end,
                    status="failed",
                    error=str(exc),
                )
            )
            n_failed += 1

    logger.info(
        "Yearly batch complete: anchors=%d computed=%d skipped=%d failed=%d",
        len(anchors), n_computed, n_skipped_existing, n_failed,
    )

    return YearlyBatchResponse(
        date_min=date_min.date().isoformat(),
        date_max=date_max.date().isoformat(),
        total_anchors=len(anchors),
        computed=n_computed,
        skipped_existing=n_skipped_existing,
        failed=n_failed,
        results=batch_results,
    )
