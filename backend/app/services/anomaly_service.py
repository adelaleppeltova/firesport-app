"""Anomaly detection service for yearly 3-year window Isolation Forest runs.

All hyper-parameters are read from ``AnomalyConfig`` (single source of truth).
No magic numbers live in this file.
"""

import logging
from datetime import date, datetime, timezone
from uuid import uuid4
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError

from app.models.anomaly import (
    AnomalyRunStatus,
    AnomalyDirection,
    YearlyBatchItem,
    YearlyBatchResponse,
    SkipReasonCounts,
    WindowRecomputeSummary,
)
from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG, get_category_group
from app.ml.isolation_forest import compute_iforest_anomalies
from app.services.windows import (
    window_for_anchor,
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
        "name": "Isolation Forest",
        "params": {
            "n_estimators": cfg.n_estimators,
            "contamination_mode": "auto",
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
                # Do výpisu patří jen window-level runy, které mají "stats".
                "stats": {"$exists": True},
            }
        },
        {
            "$group": {
                "_id": {
                    "window_start": "$window.start_date",
                    "window_end": "$window.end_date",
                },
                # Vybíráme $last (nejnovější) místo $first, aby se při více
                # non-superseded runech pro stejné okno (edge-case) vrátil
                # ten nejčerstvější.
                "run_id": {"$last": "$run_id"},
                "processed": {"$last": "$stats.processed"},
                "scores_inserted": {"$last": "$stats.scores_inserted"},
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

        # Filter 4 (strict): skip window runs with zero results.
        # Díky filtru "stats exists" v pipeline jsou zde pouze window-level
        # runy, které stats mají vždy.
        processed = row.get("processed") or 0
        scores = row.get("scores_inserted") or 0
        if processed == 0 and scores == 0:
            logger.debug(
                "Skipping empty window run %s (0 processed, 0 scores)",
                row.get("run_id"),
            )
            continue

        result.append(row)

    return result


# ------------------------------------------------------------------
# Single-window recomputation
# ------------------------------------------------------------------

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
            # Supersedujeme pouze window-level runy.
            "stats": {"$exists": True},
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
    counters: Dict[str, Any],
    cfg: AnomalyConfig,
) -> Dict[str, Any]:
    """Assemble the single ``anomaly_runs`` document for a window-level run."""
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
            "name": "Isolation Forest",
            "params": {
                "n_estimators": cfg.n_estimators,
                "contamination_mode": "auto",
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
        },
    }


async def recompute_for_window(
    db: AsyncIOMotorDatabase,
    *,
    anchor_date: date,
    window_years: int = 3,
    window_type: str = "yearly_3y",
    min_results_used: int = 10,
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
    Isolation Forest is always fit with ``contamination="auto"``, so we do
    not prescribe our own anomaly fraction or derive a custom score
    quantile threshold.

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

    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)

    counters: Dict[str, Any] = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "scores_inserted": 0,
        "skip_reason_counts": _empty_skip_reason_counts(),
    }
    cfg_base = AnomalyConfig(
        min_results=min_results_used,
        n_estimators=DEFAULT_CONFIG.n_estimators,
        eps_std=DEFAULT_CONFIG.eps_std,
        random_state=DEFAULT_CONFIG.random_state,
        contamination="auto",
    )

    try:
        # 2) Idempotence: supersede previous run for this window if any
        await _supersede_existing_window_run(db, window_type, anchor_dt)

        # 3) Načti mapu kategorie_id → skupina (jedno DB volání před smyčkou)
        category_group_map: Dict[str, str] = {}
        async for cat_doc in db["categories"].find({}, projection={"_id": 1, "name": 1}):
            cat_name = cat_doc.get("name") or ""
            category_group_map[str(cat_doc["_id"])] = get_category_group(cat_name)

        # 4) Load all valid results in window (one DB round-trip)
        raw_results = await db["results"].find(
            {
                "final_time_status": "valid",
                "final_time": {"$ne": None},
                "date": {"$gte": window_start, "$lte": window_end},
            },
            projection={"_id": 1, "athlete": 1, "category": 1, "final_time": 1, "date": 1},
        ).sort("date", 1).to_list(None)

        # 5) Group by (athlete_id, category_group)
        #    Výsledky ze srovnatelných kategorií se počítají dohromady;
        #    nesrovnatelné kategorie jsou izolovány vlastní skupinou.
        athlete_group_results: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for r in raw_results:
            aid = str(r["athlete"])
            cat_oid = r.get("category")
            cg = category_group_map.get(str(cat_oid), str(cat_oid)) if cat_oid is not None else "unknown"
            key = (aid, cg)
            athlete_group_results.setdefault(key, []).append(r)

        all_score_docs: List[Dict[str, Any]] = []

        # 6) Per-athlete + category-group processing
        for (athlete_id, category_group), results in athlete_group_results.items():
            n = len(results)
            sr = counters["skip_reason_counts"]

            if n < min_results_used:
                counters["skipped"] += 1
                sr["not_enough_data"] = sr.get("not_enough_data", 0) + 1
                continue

            times = [r["final_time"] for r in results]
            try:
                ml_result = compute_iforest_anomalies(times, config=cfg_base)
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
                continue

            # ML succeeded – build score docs
            scores = ml_result.get("scores", [])
            is_anomaly_list = ml_result.get("is_anomaly", [])
            direction_list = ml_result.get("direction", [])
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
                    "median_time": median_time,
                    "is_anomaly": is_anomaly_list[i] if i < len(is_anomaly_list) else False,
                    "direction": (
                        direction_list[i]
                        if i < len(direction_list)
                        else AnomalyDirection.none.value
                    ),
                    "contamination_mode": "auto",
                    "category_group": category_group,
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

        # 7) Persist run document
        run_doc = _build_window_run_doc(
            run_id=run_id,
            created_at=created_at,
            window_start=window_start,
            window_end=window_end,
            window_years=window_years,
            window_type=window_type,
            min_results_used=min_results_used,
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

    # 3) Pre-load existing non-superseded window runs for skip logic (force=False)
    existing_anchor_dates: set[str] = set()
    if not force:
        cursor = db["anomaly_runs"].find(
            {
                "window_type": window_type,
                "is_superseded": {"$ne": True},
                "stats": {"$exists": True},
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
