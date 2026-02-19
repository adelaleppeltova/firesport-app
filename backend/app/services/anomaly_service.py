import logging
from datetime import datetime, timezone
from uuid import uuid4
from typing import Tuple, List, Dict, Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError

from app.models.anomaly import AnomalyRunStatus, AnomalyDirection
from ml.isolation_forest import compute_iforest_anomalies


logger = logging.getLogger(__name__)

# Constants
MIN_RESULTS = 15


def _build_window(window_start: datetime, window_end: datetime) -> Dict[str, Any]:
    """Build window configuration document."""
    return {
        "start_date": window_start,
        "end_date": window_end,
        "years": 3,
        "min_results": MIN_RESULTS,
    }


def _build_model() -> Dict[str, Any]:
    """Build model configuration document."""
    return {
        "name": "IsolationForest",
        "params": {
            "n_estimators": 200,
            "contamination": 0.05,
            "random_state": 42,
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
    """Build run document for anomaly_runs collection."""
    return {
        "run_id": run_id,
        "created_at": created_at,
        "window": window,
        "model": model,
        "status": status,
        "summary": summary,
    }


async def compute_for_athlete(
    db: AsyncIOMotorDatabase,
    athlete_id: str,
    window_start: datetime,
    window_end: datetime,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Compute anomalies for a single athlete within a time window.
    
    Args:
        db: Motor AsyncIOMotorDatabase instance
        athlete_id: String representation of athlete ObjectId
        window_start: Start date of the window
        window_end: End date of the window
        
    Returns:
        Tuple of (run_doc, score_docs_list)
        - run_doc: document to insert into anomaly_runs collection
        - score_docs_list: list of documents to insert into anomaly_scores collection
        
    Never raises exceptions; catches all errors and returns run_doc with status="failed"
    """
    run_id = str(uuid4())
    created_at = datetime.now(timezone.utc)
    window = _build_window(window_start, window_end)
    model = _build_model()
    
    try:
        # Convert athlete_id string to ObjectId
        athlete_oid = ObjectId(athlete_id)
        
        # Load valid results for athlete in window
        results = await db["results"].find(
            {
                "athlete": athlete_oid,
                "final_time_status": "valid",
                "date": {
                    "$gte": window_start,
                    "$lte": window_end,
                }
            },
            projection={"_id": 1, "final_time": 1, "date": 1},
        ).sort("date", 1).to_list(None)
        
        n_valid_results = len(results)
        
        # Check minimum results threshold
        if n_valid_results < MIN_RESULTS:
            summary = {
                "athlete_id": athlete_oid,
                "n_valid_results_in_window": n_valid_results,
                "n_anomalies": 0,
                "threshold_score": None,
                "median_time": None,
                "reason": f"Insufficient results: {n_valid_results} < {MIN_RESULTS}",
            }
            run_doc = _build_run_doc(
                run_id, created_at, window, model, AnomalyRunStatus.skipped.value, summary
            )
            return run_doc, []
        
        # Prepare input for ML: list of times
        times = [r["final_time"] for r in results]
        
        # Compute anomalies using ML
        ml_result = compute_iforest_anomalies(times)
        
        ml_status = ml_result.get("status")
        
        # If ML returned skipped, return skipped run_doc
        if ml_status == "skipped":
            reason = ml_result.get("reason", "Unknown")
            summary = {
                "athlete_id": athlete_oid,
                "n_valid_results_in_window": n_valid_results,
                "n_anomalies": 0,
                "threshold_score": None,
                "median_time": None,
                "reason": reason,
            }
            run_doc = _build_run_doc(
                run_id, created_at, window, model, AnomalyRunStatus.skipped.value, summary
            )
            return run_doc, []
        
        # ML succeeded
        scores = ml_result.get("scores", [])
        threshold_score = ml_result.get("threshold_score", 0.0)
        median_time = ml_result.get("median_time", 0.0)
        n_anomalies = ml_result.get("n_anomalies", 0)
        is_anomaly_list = ml_result.get("is_anomaly", [])
        direction_list = ml_result.get("direction", [])
        
        # Create run_doc
        summary = {
            "athlete_id": athlete_oid,
            "n_valid_results_in_window": n_valid_results,
            "n_anomalies": n_anomalies,
            "threshold_score": threshold_score,
            "median_time": median_time,
            "reason": None,
        }
        run_doc = _build_run_doc(
            run_id, created_at, window, model, AnomalyRunStatus.success.value, summary
        )
        
        # Create score_docs only on success
        score_docs = []
        for i, result in enumerate(results):
            score_doc = {
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
                "direction": direction_list[i] if i < len(direction_list) else AnomalyDirection.none.value,
            }
            score_docs.append(score_doc)
        
        return run_doc, score_docs
        
    except Exception as e:
        logger.exception(f"Error computing anomalies for athlete {athlete_id}: {e}")
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
        run_doc = _build_run_doc(
            run_id, created_at, window, model, AnomalyRunStatus.failed.value, summary
        )
        return run_doc, []


async def recompute_for_all_athletes(
    db: AsyncIOMotorDatabase,
    window_start: datetime,
    window_end: datetime,
) -> Dict[str, int]:
    """
    Recompute anomalies for all athletes.
    
    Iterates through all athletes, computes anomalies for each, saves run_doc to anomaly_runs,
    and if successful, saves score_docs to anomaly_scores.
    
    Args:
        db: Motor AsyncIOMotorDatabase instance
        window_start: Start date of the window
        window_end: End date of the window
        
    Returns:
        Dict with counters:
        - processed: total athletes processed successfully
        - skipped: athletes with insufficient results
        - failed: athletes with errors
        - scores_inserted: total score documents inserted
    """
    counters = {
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "scores_inserted": 0,
    }
    
    try:
        # Get all athletes
        athletes = await db["athletes"].find(
            {},
            projection={"_id": 1}
        ).to_list(None)
        
        logger.info(f"Starting anomaly computation for {len(athletes)} athletes")
        
        for athlete_doc in athletes:
            athlete_id = str(athlete_doc["_id"])
            
            # Compute anomalies for athlete
            run_doc, score_docs = await compute_for_athlete(
                db, athlete_id, window_start, window_end
            )
            
            # Insert run_doc
            await db["anomaly_runs"].insert_one(run_doc)
            
            # Check status and update counters
            status = run_doc["status"]
            if status == AnomalyRunStatus.success.value:
                counters["processed"] += 1
                # Insert score_docs if any
                if score_docs:
                    try:
                        result = await db["anomaly_scores"].insert_many(score_docs, ordered=False)
                        counters["scores_inserted"] += len(result.inserted_ids)
                    except BulkWriteError as e:
                        # Log warning but don't fail - some docs may have been inserted
                        logger.warning(
                            f"BulkWriteError inserting scores for athlete {athlete_id}: {e.details}"
                        )
                        # Try to count successfully inserted documents
                        if e.details and "nInserted" in e.details:
                            counters["scores_inserted"] += e.details["nInserted"]
                        else:
                            # Fallback: assume all were attempted
                            counters["scores_inserted"] += len(score_docs)
            elif status == AnomalyRunStatus.skipped.value:
                counters["skipped"] += 1
            elif status == AnomalyRunStatus.failed.value:
                counters["failed"] += 1
        
        logger.info(
            f"Anomaly computation completed. "
            f"Processed: {counters['processed']}, "
            f"Skipped: {counters['skipped']}, "
            f"Failed: {counters['failed']}, "
            f"Scores inserted: {counters['scores_inserted']}"
        )
        
        return counters
        
    except Exception as e:
        logger.exception(f"Critical error in recompute_for_all_athletes: {e}")
        return counters
