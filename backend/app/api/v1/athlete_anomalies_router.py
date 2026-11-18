"""
Athlete anomaly detection endpoints.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId

from app.db.database import get_db
from app.ml.anomaly_config import category_performance_group
from app.result_values import final_result_fields, measured_seconds, valid_final_time
from app.models.anomaly import (
    AthleteAnomaliesResponse,
    AnomalyRunInfo,
    AnomalyItem,
    AnomalyDirection,
    AnomalyRunStatus,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/athletes", tags=["anomalies"])


def comparable_scores(scores, results, groups, requested_group=None):
    """Suppress stored runs fitted across different disciplines or missing source rows."""
    fitted_groups = defaultdict(set)
    stale_groups = set()
    normalized = []
    for score in scores:
        result_id = score.get("result_id")
        group = groups.get(result_id)
        stored_group = score.get("category_group")
        fitted_groups[stored_group].add(group)
        time = valid_final_time(results.get(result_id, {}))
        if group is None or time is None or time != measured_seconds(score.get("final_time")):
            stale_groups.add(stored_group)
            continue
        normalized.append((stored_group, {**score, "category_group": group, "final_time": time}))

    compatible = [
        score for stored_group, score in normalized
        if stored_group not in stale_groups and fitted_groups[stored_group] == {score["category_group"]}
    ]
    if requested_group is None:
        return compatible, None
    aliases = fitted_groups.get(requested_group, set())
    exact_exists = requested_group in groups.values()
    target = next(iter(aliases)) if not exact_exists and len(aliases) == 1 else requested_group
    target = target or requested_group
    return [score for score in compatible if score["category_group"] == target], target


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
       ``yearly_3y`` run.

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
    return None


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

    cursor = db["anomaly_scores"].find(
        score_filter,
        projection={
            "result_id": 1,
            "competition_date": 1,
            "final_time": 1,
            "score": 1,
            "is_anomaly": 1,
            "direction": 1,
            "median_time": 1,
            "category_group": 1,
            "contamination_mode": 1,
        },
    ).sort("competition_date", -1)

    score_docs = await cursor.to_list(None)

    window_start, window_end = window.get("start_date"), window.get("end_date")
    scope = {"athlete": athlete_oid}
    result_ids = [score["result_id"] for score in score_docs if score.get("result_id")]
    if window_start and window_end:
        scope["$or"] = [
            {"date": {"$gte": window_start, "$lte": window_end}},
            {"_id": {"$in": result_ids}},
        ]
    else:
        scope["_id"] = {"$in": result_ids}
    rows = await db["results"].find(scope, projection={
        "category": 1, "competition": 1, "quality_flag": 1, "date": 1,
        "final_time": 1, "final_time_status": 1,
    }).to_list(None)
    result_by_id = {row["_id"]: row for row in rows}
    category_ids = list({row["category"] for row in rows if row.get("category")})
    categories = {
        cat["_id"]: cat for cat in await db["categories"].find(
            {"_id": {"$in": category_ids}}, projection={"name": 1, "discipline": 1}
        ).to_list(None)
    } if category_ids else {}
    groups = {
        row["_id"]: category_performance_group(categories[row["category"]])
        for row in rows if row.get("category") in categories
    }
    score_docs, selected_group = comparable_scores(score_docs, result_by_id, groups, category_group)
    n_anomalies = sum(1 for score in score_docs if score.get("is_anomaly"))
    medians = {measured_seconds(score.get("median_time")) for score in score_docs}
    scored_groups = {score["category_group"] for score in score_docs}
    median_time = next(iter(medians)) if len(scored_groups) == len(medians) == 1 else None

    counted = [
        row for row in rows if selected_group is None or groups.get(row["_id"]) == selected_group
    ]
    if window_start and window_end:
        def timestamp(when):
            return (when if when.tzinfo else when.replace(tzinfo=timezone.utc)).timestamp()
        start, end = timestamp(window_start), timestamp(window_end)
        counted = [
            row for row in counted if isinstance(row.get("date"), datetime)
            and start <= timestamp(row["date"]) <= end
        ]
    statuses = Counter(final_result_fields(row)["final_time_status"] for row in counted)
    disciplines = {categories.get(row.get("category"), {}).get("discipline") for row in counted}
    discipline_val = next(iter(disciplines)) if len(disciplines) == 1 else None
    model_doc = run.get("model") or {}
    model_params = model_doc.get("params") or {}

    contamination_mode: Optional[str] = (
        score_docs[0].get("contamination_mode")
        if score_docs
        else model_params.get("contamination_mode")
    )

    run_info = AnomalyRunInfo(
        run_id=resolved_run_id,
        created_at=run["created_at"],
        window_start=window.get("start_date"),
        window_end=window.get("end_date"),
        n_valid_results_in_window=statuses["valid"],
        n_invalid_results_in_window=statuses["invalid"],
        n_missing_results_in_window=statuses["missing"],
        n_anomalies=n_anomalies,
        median_time=median_time,
        status=AnomalyRunStatus(run.get("status", "success")),
        reason=summary.get("reason"),
        # Model parameters
        model_name=model_doc.get("name"),
        contamination_mode=contamination_mode,
        n_estimators=model_params.get("n_estimators"),
        random_state=model_params.get("random_state"),
        max_samples=str(model_params.get("max_samples", "auto")),
        eps_std=model_params.get("eps_std"),
        discipline=discipline_val,
    )

    # No scores → return empty items list (run exists but athlete was skipped)
    if not score_docs:
        return AthleteAnomaliesResponse(
            athlete_id=athlete_id,
            run=run_info,
            items=[],
        )

    selected_rows = [result_by_id[score["result_id"]] for score in score_docs]
    comp_ids = list({row["competition"] for row in selected_rows if row.get("competition")})
    competitions = {
        comp["_id"]: comp for comp in await db["competitions"].find(
            {"_id": {"$in": comp_ids}}, projection={"name": 1, "place": 1}
        ).to_list(None)
    } if comp_ids else {}

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

        source = result_by_id[result_id]
        competition = competitions.get(source.get("competition"), {})
        items.append(
            AnomalyItem(
                result_id=str(result_id),
                competition_date=competition_date,
                final_time=final_time,
                score=score,
                is_anomaly=is_anomaly,
                direction=direction,
                competition_name=competition.get("name"),
                competition_place=competition.get("place"),
                quality_flag=source.get("quality_flag", "ok"),
                category_group=item.get("category_group"),
            )
        )

    return AthleteAnomaliesResponse(
        athlete_id=athlete_id,
        run=run_info,
        items=items,
    )
