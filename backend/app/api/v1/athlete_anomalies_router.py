"""
Athlete anomaly detection endpoints.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/{athlete_id}/anomalies", response_model=AthleteAnomaliesResponse)
async def get_athlete_anomalies(
    athlete_id: str,
    db=Depends(get_db),
):
    """
    Get anomaly analysis for a specific athlete.
    
    Returns the latest anomaly run with all performance results and their anomaly scores.
    
    TODO: Add owner/admin authentication
    
    Args:
        athlete_id: String representation of athlete ObjectId
        db: Motor AsyncIOMotorDatabase instance
        
    Returns:
        AthleteAnomaliesResponse with run info and all scored items
    """
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid athlete_id: {e}")
    
    try:
        # Find the latest anomaly run for this athlete
        run = await db["anomaly_runs"].find_one(
            {"summary.athlete_id": athlete_oid},
            sort=[("created_at", -1)],
        )
        
        # If no run found, return empty response
        if not run:
            return AthleteAnomaliesResponse(
                athlete_id=athlete_id,
                run=None,
                items=[],
            )
        
        # Build run info from the latest run
        run_info = AnomalyRunInfo(
            run_id=run["run_id"],
            created_at=run["created_at"],
            window_start=run["window"]["start_date"],
            window_end=run["window"]["end_date"],
            n_valid_results_in_window=run["summary"]["n_valid_results_in_window"],
            n_anomalies=run["summary"].get("n_anomalies", 0),
            threshold_score=run["summary"].get("threshold_score"),
            median_time=run["summary"].get("median_time"),
            status=AnomalyRunStatus(run["status"]),
            reason=run["summary"].get("reason"),
        )
        
        # Fetch anomaly scores for this run
        cursor = db["anomaly_scores"].find(
            {
                "run_id": run["run_id"],
                "athlete_id": athlete_oid,
            },
            projection={
                "result_id": 1,
                "competition_date": 1,
                "final_time": 1,
                "score": 1,
                "is_anomaly": 1,
                "direction": 1,
            },
        ).sort("competition_date", -1)
        
        score_docs = await cursor.to_list(None)
        
        # Načti názvy soutěží přes result_id -> competition
        result_ids = [doc["result_id"] for doc in score_docs if doc.get("result_id")]
        results_map = {}
        if result_ids:
            results_cursor = db["results"].find(
                {"_id": {"$in": result_ids}},
                projection={"_id": 1, "competition": 1},
            )
            results_docs = await results_cursor.to_list(None)
            comp_ids = list({r["competition"] for r in results_docs if r.get("competition")})
            competitions_map = {}
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
                }
        
        # Convert to AnomalyItem response models with safe direction parsing
        items = []
        for item in score_docs:
            # Safe field reading with defaults
            result_id = item.get("result_id")
            competition_date = item.get("competition_date")
            final_time = item.get("final_time")
            score = item.get("score")
            is_anomaly = item.get("is_anomaly", False)
            
            # Skip item if critical fields are missing
            if result_id is None or competition_date is None or final_time is None or score is None:
                continue
            
            # Safe direction parsing with fallback
            raw_dir = item.get("direction", "none")
            try:
                direction = AnomalyDirection(raw_dir)
            except (ValueError, KeyError):
                direction = AnomalyDirection.none
            
            anomaly_item = AnomalyItem(
                result_id=str(result_id),
                competition_date=competition_date,
                final_time=final_time,
                score=score,
                is_anomaly=is_anomaly,
                direction=direction,
                competition_name=results_map.get(result_id, {}).get("name"),
                competition_place=results_map.get(result_id, {}).get("place"),
            )
            items.append(anomaly_item)
        
        return AthleteAnomaliesResponse(
            athlete_id=athlete_id,
            run=run_info,
            items=items,
        )
        
    except Exception as e:
        logger.exception(f"Error fetching anomalies for athlete {athlete_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching anomalies: {e}")
