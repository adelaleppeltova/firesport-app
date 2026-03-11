"""
Athlete anomaly detection endpoints.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.db.database import get_db
from app.models.anomaly import (
    AthleteAnomaliesResponse,
    AnomalyRunInfo,
    AnomalyItem,
    AnomalyDirection,
    AnomalyRunStatus,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/athletes", tags=["anomalies"])


# ------------------------------------------------------------------
# Internal helper: resolve a run document from various selectors
# ------------------------------------------------------------------

async def _resolve_run(
    db,
    athlete_oid: ObjectId,
    run_id: Optional[str],
    anchor_date: Optional[str],
) -> Optional[dict]:
    """Return the anomaly_runs document to use for this request.

    Selection priority
    ------------------
    1. ``run_id`` supplied → look up run by ``run_id`` field directly.
    2. ``anchor_date`` supplied (YYYY-MM-DD) → find non-superseded
       ``yearly_3y`` run whose ``window.end_date`` falls on that date.
    3. Neither supplied → find the most recent non-superseded
       ``yearly_3y`` run; if none exists, fall back to any latest run
       matching ``summary.athlete_id`` (legacy per-athlete runs).

    Returns ``None`` when nothing is found.
    """
    if run_id is not None:
        return await db["anomaly_runs"].find_one({"run_id": run_id})

    if anchor_date is not None:
        try:
            parsed = datetime.strptime(anchor_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"anchor_date must be in YYYY-MM-DD format, got {anchor_date!r}.",
            )
        return await db["anomaly_runs"].find_one(
            {
                "window_type": "yearly_3y",
                "window.end_date": parsed,
                "is_superseded": {"$ne": True},
            },
            sort=[("created_at", -1)],
        )

    # Default: latest non-superseded yearly_3y run
    run = await db["anomaly_runs"].find_one(
        {
            "window_type": "yearly_3y",
            "is_superseded": {"$ne": True},
        },
        sort=[("created_at", -1)],
    )
    if run is not None:
        return run

    # Fallback: legacy per-athlete run (old recompute_for_all_athletes format)
    return await db["anomaly_runs"].find_one(
        {"summary.athlete_id": athlete_oid},
        sort=[("created_at", -1)],
    )


@router.get("/{athlete_id}/anomalies", response_model=AthleteAnomaliesResponse)
async def get_athlete_anomalies(
    athlete_id: str,
    run_id: Optional[str] = Query(
        default=None,
        description="Specific run_id to use. Mutually exclusive with anchor_date.",
    ),
    anchor_date: Optional[str] = Query(
        default=None,
        description=(
            "Year-end anchor date (YYYY-12-31, e.g. '2025-12-31'). "
            "Selects the latest non-superseded yearly_3y run for that anchor."
        ),
    ),
    category_group: Optional[str] = Query(
        default=None,
        description=(
            "Filtruje skóre podle skupiny kategorií.  "
            "Možné hodnoty: 'muz', 'zena', 'mladsi_dorostenci' nebo jiný "
            "identifikátor skupiny uložený v poli category_group.  "
            "Pokud není zadáno, vrátí se skóre ze všech skupin."
        ),
    ),
    db=Depends(get_db),
):
    """Get anomaly analysis for a specific athlete.

    Returns the scored performance results for the resolved run window.

    Run selection
    -------------
    * ``run_id`` – explicit run identifier.
    * ``anchor_date`` – selects the latest non-superseded ``yearly_3y``
      run whose ``window.end_date`` matches the given date.
    * Neither → uses the most recent non-superseded ``yearly_3y`` run.

    Returns 404 when no matching run is found.
    """
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid athlete_id: {e}")

    try:
        run = await _resolve_run(db, athlete_oid, run_id, anchor_date)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error resolving run for athlete %s: %s", athlete_id, e)
        raise HTTPException(status_code=500, detail=f"Error resolving run: {e}")

    if run is None:
        detail = "No anomaly run found"
        if run_id:
            detail = f"No anomaly run found with run_id={run_id!r}."
        elif anchor_date:
            detail = (
                f"No non-superseded yearly_3y run found for anchor_date={anchor_date!r}."
            )
        raise HTTPException(status_code=404, detail=detail)

    resolved_run_id: str = run["run_id"]

    # Build AnomalyRunInfo -----------------------------------------------
    # Window-level runs (recompute_for_window) store aggregate stats in
    # run["stats"] instead of a per-athlete "summary" sub-document.
    # Derive per-athlete values from the scores we will fetch.
    summary = run.get("summary") or {}
    window = run.get("window") or {}

    # Fetch scores for this athlete in this run first so we can derive stats
    score_filter: dict = {
        "run_id": resolved_run_id,
        "athlete_id": athlete_oid,
    }
    if category_group is not None:
        score_filter["category_group"] = category_group

    cursor = db["anomaly_scores"].find(
        score_filter,
        projection={
            "result_id": 1,
            "competition_date": 1,
            "final_time": 1,
            "score": 1,
            "is_anomaly": 1,
            "direction": 1,
            "threshold_score": 1,
            "median_time": 1,
            "category_group": 1,
        },
    ).sort("competition_date", -1)

    score_docs = await cursor.to_list(None)

    # Derive per-athlete stats from scores when not available on summary
    n_anomalies = summary.get("n_anomalies", sum(1 for s in score_docs if s.get("is_anomaly")))
    threshold_score = summary.get("threshold_score") or (
        score_docs[0].get("threshold_score") if score_docs else None
    )
    median_time = summary.get("median_time") or (
        score_docs[0].get("median_time") if score_docs else None
    )

    # Count valid and invalid results directly from the results collection
    n_valid = 0
    n_invalid = 0
    window_start = window.get("start_date")
    window_end = window.get("end_date")
    if window_start and window_end:
        n_valid = await db["results"].count_documents(
            {
                "athlete": athlete_oid,
                "final_time_status": "valid",
                "date": {"$gte": window_start, "$lte": window_end},
            }
        )
        n_invalid = await db["results"].count_documents(
            {
                "athlete": athlete_oid,
                "final_time_status": {"$ne": "valid"},
                "date": {"$gte": window_start, "$lte": window_end},
            }
        )
    else:
        # Fallback when window dates are not available
        n_valid = summary.get("n_valid_results_in_window", len(score_docs))

    run_info = AnomalyRunInfo(
        run_id=resolved_run_id,
        created_at=run["created_at"],
        window_start=window.get("start_date"),
        window_end=window.get("end_date"),
        n_valid_results_in_window=n_valid,
        n_invalid_results_in_window=n_invalid,
        n_anomalies=n_anomalies,
        threshold_score=threshold_score,
        median_time=median_time,
        status=AnomalyRunStatus(run.get("status", "success")),
        reason=summary.get("reason"),
    )

    # No scores → return empty items list (run exists but athlete was skipped)
    if not score_docs:
        return AthleteAnomaliesResponse(
            athlete_id=athlete_id,
            run=run_info,
            items=[],
        )

    # Enrich with competition name/place and quality_flag via result_id join
    result_ids = [doc["result_id"] for doc in score_docs if doc.get("result_id")]
    results_map: dict = {}
    if result_ids:
        results_cursor = db["results"].find(
            {"_id": {"$in": result_ids}},
            projection={"_id": 1, "competition": 1, "quality_flag": 1},
        )
        results_docs = await results_cursor.to_list(None)
        comp_ids = list({r["competition"] for r in results_docs if r.get("competition")})
        competitions_map: dict = {}
        if comp_ids:
            comps_cursor = db["competitions"].find(
                {"_id": {"$in": comp_ids}},
                projection={"_id": 1, "name": 1, "place": 1},
            )
            comps = await comps_cursor.to_list(None)
            competitions_map = {c["_id"]: c for c in comps}
        for r in results_docs:
            comp = competitions_map.get(r.get("competition"))
            results_map[r["_id"]] = {
                "name": comp.get("name") if comp else None,
                "place": comp.get("place") if comp else None,
                "quality_flag": r.get("quality_flag", "ok"),
            }

    # Build AnomalyItem list
    items = []
    for item in score_docs:
        result_id = item.get("result_id")
        competition_date = item.get("competition_date")
        final_time = item.get("final_time")
        score = item.get("score")
        is_anomaly = item.get("is_anomaly", False)

        if result_id is None or competition_date is None or final_time is None or score is None:
            continue

        raw_dir = item.get("direction", "none")
        try:
            direction = AnomalyDirection(raw_dir)
        except (ValueError, KeyError):
            direction = AnomalyDirection.none

        items.append(
            AnomalyItem(
                result_id=str(result_id),
                competition_date=competition_date,
                final_time=final_time,
                score=score,
                is_anomaly=is_anomaly,
                direction=direction,
                competition_name=results_map.get(result_id, {}).get("name"),
                competition_place=results_map.get(result_id, {}).get("place"),
                quality_flag=results_map.get(result_id, {}).get("quality_flag", "ok"),
                category_group=item.get("category_group"),
            )
        )

    return AthleteAnomaliesResponse(
        athlete_id=athlete_id,
        run=run_info,
        items=items,
    )
