"""
Isolation Forest anomaly detection module.

Provides anomaly detection for athlete performance data using
Isolation Forest.  All hyper-parameters come from ``AnomalyConfig`` –
there are **no module-level magic numbers**.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np
from sklearn.ensemble import IsolationForest

from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG


def compute_iforest_anomalies(
    times: List[float],
    *,
    config: AnomalyConfig | None = None,
) -> Dict[str, Any]:
    """Compute anomalies on a 1-D time series using Isolation Forest.

    Parameters
    ----------
    times:
        Raw ``final_time`` values for one athlete.  NaN / ±inf values
        are silently dropped before any check.
    config:
        Full parameter set.  Falls back to ``DEFAULT_CONFIG`` when
        *None* (safe defaults, reproducible).

    Returns
    -------
    dict
        Always contains ``"status"`` (``"success"`` | ``"skipped"``).

        On **skip** the dict also carries ``"reason"`` and ``"n"``.

        On **success** the dict carries:
        ``scores``, ``threshold_score``, ``median_time``,
        ``is_anomaly``, ``direction``, ``n_anomalies``, ``n``,
        plus the five config values that were actually used.
    """
    cfg = config or DEFAULT_CONFIG

    # --- clean inputs: drop NaN / ±inf -----------------------------------
    arr = np.asarray(times, dtype=np.float64)
    mask = np.isfinite(arr)
    arr = arr[mask]

    # --- guard: not enough data ------------------------------------------
    if len(arr) < cfg.min_results:
        reason = (
            "not_enough_data"
            if mask.all()
            else "not_enough_data_after_cleaning"
        )
        return {
            "status": "skipped",
            "reason": reason,
            "n": int(len(arr)),
            **_used_params(cfg),
        }

    # --- guard: low variance ---------------------------------------------
    if float(np.std(arr)) < cfg.eps_std:
        return {
            "status": "skipped",
            "reason": "low_variance",
            "n": int(len(arr)),
            **_used_params(cfg),
        }

    # --- fit Isolation Forest --------------------------------------------
    X = arr.reshape(-1, 1)
    model = IsolationForest(
        n_estimators=cfg.n_estimators,
        contamination=cfg.contamination,
        random_state=cfg.random_state,
        n_jobs=-1,
    )
    model.fit(X)

    # --- scores & threshold -----------------------------------------------
    scores = (-model.decision_function(X)).astype(float)
    threshold_q = 1.0 - cfg.contamination
    threshold_score = float(np.quantile(scores, threshold_q))
    median_time = float(np.median(arr))

    # --- anomaly flags & direction ----------------------------------------
    is_anomaly = [bool(s >= threshold_score) for s in scores]
    direction: List[str] = []
    for t, flag in zip(arr, is_anomaly):
        if not flag:
            direction.append("none")
        elif t < median_time:
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
        "n": int(len(arr)),
        **_used_params(cfg),
    }


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------

def _used_params(cfg: AnomalyConfig) -> Dict[str, Any]:
    """Return the five config values as a flat dict (for embedding in results)."""
    return {
        "min_results_used": cfg.min_results,
        "contamination_used": cfg.contamination,
        "eps_std_used": cfg.eps_std,
        "n_estimators_used": cfg.n_estimators,
        "random_state_used": cfg.random_state,
    }
