"""
Isolation Forest anomaly detection module.

This module provides anomaly detection for performance data using Isolation Forest algorithm.
"""

from typing import List, Dict, Any
import numpy as np
from sklearn.ensemble import IsolationForest


MIN_RESULTS = 15
N_ESTIMATORS = 200
CONTAMINATION = 0.05
RANDOM_STATE = 42
EPS_STD = 0.01


def compute_iforest_anomalies(times: List[float]) -> Dict[str, Any]:
    """
    Compute anomalies using Isolation Forest algorithm.
    
    Args:
        times: List of final_time values (float)
        
    Returns:
        Dict with status and either:
        - On success: scores, threshold_score, median_time, is_anomaly, direction, n_anomalies
        - On skip: reason string
    """
    # Guard rails
    if len(times) < MIN_RESULTS:
        return {"status": "skipped", "reason": "not_enough_data"}
    
    arr = np.array(times, dtype=float)
    if np.std(arr) < EPS_STD:
        return {"status": "skipped", "reason": "low_variance"}

    # Train Isolation Forest
    X = arr.reshape(-1, 1)
    model = IsolationForest(
        n_estimators=N_ESTIMATORS,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    model.fit(X)

    # Compute scores and threshold
    scores = (-model.decision_function(X)).astype(float)
    threshold_score = float(np.quantile(scores, 0.95))
    median_time = float(np.median(arr))

    # Determine anomalies and directions
    is_anomaly = [bool(s >= threshold_score) for s in scores]
    direction = []
    for t, flag in zip(arr, is_anomaly):
        if not flag:
            direction.append("none")
        else:
            if t < median_time:
                direction.append("fast")
            elif t > median_time:
                direction.append("slow")
            else:
                direction.append("none")

    n_anomalies = int(sum(is_anomaly))
    
    return {
        "status": "success",
        "scores": [float(s) for s in scores],
        "threshold_score": threshold_score,
        "median_time": median_time,
        "is_anomaly": is_anomaly,
        "direction": direction,
        "n_anomalies": n_anomalies,
    }
