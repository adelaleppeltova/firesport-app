"""Unit tests for the Isolation Forest anomaly detection pipeline.

Covers the four key scenarios requested:
1. Not enough data → skipped
2. Low variance → skipped
3. Success returns arrays of the same length as input
4. Threshold quantile is tied to contamination (1 − contamination)
"""

import math

import numpy as np
import pytest

from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG
from app.ml.isolation_forest import compute_iforest_anomalies


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _make_config(**overrides) -> AnomalyConfig:
    """Return a config with optional overrides on top of defaults."""
    return AnomalyConfig(**overrides)


# -----------------------------------------------------------------
# 1. Not enough data → skipped
# -----------------------------------------------------------------

class TestNotEnoughData:
    """compute_iforest_anomalies must skip when len(times) < min_results."""

    def test_empty_list(self):
        result = compute_iforest_anomalies([])
        assert result["status"] == "skipped"
        assert result["reason"] == "not_enough_data"

    def test_below_default_min(self):
        times = [15.0] * (DEFAULT_CONFIG.min_results - 1)
        result = compute_iforest_anomalies(times)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_enough_data"

    def test_custom_min_results(self):
        cfg = _make_config(min_results=20)
        times = [15.0] * 19
        result = compute_iforest_anomalies(times, config=cfg)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_enough_data"

    def test_nan_inf_cleaning_triggers_skip(self):
        """10 values but 5 are NaN → only 5 clean → skip."""
        cfg = _make_config(min_results=10)
        times = [15.0] * 5 + [float("nan")] * 5
        result = compute_iforest_anomalies(times, config=cfg)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_enough_data_after_cleaning"


# -----------------------------------------------------------------
# 2. Low variance → skipped
# -----------------------------------------------------------------

class TestLowVariance:
    """Skip when std(times) < eps_std."""

    def test_constant_times(self):
        times = [20.0] * 15
        result = compute_iforest_anomalies(times)
        assert result["status"] == "skipped"
        assert result["reason"] == "low_variance"

    def test_near_zero_std(self):
        cfg = _make_config(eps_std=0.1)
        rng = np.random.default_rng(0)
        times = (20.0 + rng.normal(0, 0.001, 20)).tolist()
        result = compute_iforest_anomalies(times, config=cfg)
        assert result["status"] == "skipped"
        assert result["reason"] == "low_variance"


# -----------------------------------------------------------------
# 3. Success returns arrays of same length as input
# -----------------------------------------------------------------

class TestSuccessShape:
    """On success, list outputs must match the (cleaned) input length."""

    @pytest.fixture()
    def success_result(self):
        rng = np.random.default_rng(42)
        times = (18.0 + rng.normal(0, 2, 50)).tolist()
        return compute_iforest_anomalies(times)

    def test_status_is_success(self, success_result):
        assert success_result["status"] == "success"

    def test_scores_length(self, success_result):
        n = success_result["n"]
        assert len(success_result["scores"]) == n

    def test_is_anomaly_length(self, success_result):
        n = success_result["n"]
        assert len(success_result["is_anomaly"]) == n

    def test_direction_length(self, success_result):
        n = success_result["n"]
        assert len(success_result["direction"]) == n

    def test_n_anomalies_is_int(self, success_result):
        assert isinstance(success_result["n_anomalies"], int)
        assert success_result["n_anomalies"] >= 0


# -----------------------------------------------------------------
# 4. Threshold quantile is tied to contamination
# -----------------------------------------------------------------

class TestThresholdQuantile:
    """threshold_score == quantile(scores, 1 - contamination)."""

    @pytest.mark.parametrize("contamination", [0.05, 0.10, 0.20])
    def test_threshold_matches_quantile(self, contamination):
        rng = np.random.default_rng(123)
        times = (20.0 + rng.normal(0, 3, 100)).tolist()
        cfg = _make_config(contamination=contamination)
        result = compute_iforest_anomalies(times, config=cfg)

        assert result["status"] == "success"

        scores = np.array(result["scores"])
        expected_q = 1.0 - contamination
        expected_threshold = float(np.quantile(scores, expected_q))

        assert math.isclose(
            result["threshold_score"],
            expected_threshold,
            rel_tol=1e-9,
        ), (
            f"threshold_score={result['threshold_score']} != "
            f"quantile(scores, {expected_q})={expected_threshold}"
        )


# -----------------------------------------------------------------
# 5. Used params are always echoed back
# -----------------------------------------------------------------

class TestUsedParamsEchoed:
    """Every result dict must include the five *_used keys."""

    _USED_KEYS = {
        "min_results_used",
        "contamination_used",
        "eps_std_used",
        "n_estimators_used",
        "random_state_used",
    }

    def test_echoed_on_skip(self):
        result = compute_iforest_anomalies([])
        assert self._USED_KEYS.issubset(result.keys())

    def test_echoed_on_success(self):
        rng = np.random.default_rng(7)
        times = (18.0 + rng.normal(0, 2, 50)).tolist()
        result = compute_iforest_anomalies(times)
        assert self._USED_KEYS.issubset(result.keys())

    def test_custom_config_values_echoed(self):
        cfg = _make_config(min_results=5, contamination=0.10, n_estimators=50)
        rng = np.random.default_rng(7)
        times = (18.0 + rng.normal(0, 2, 50)).tolist()
        result = compute_iforest_anomalies(times, config=cfg)
        assert result["min_results_used"] == 5
        assert result["contamination_used"] == 0.10
        assert result["n_estimators_used"] == 50


# -----------------------------------------------------------------
# 6. Reproducibility (random_state)
# -----------------------------------------------------------------

class TestReproducibility:
    """Same input + same random_state → identical output."""

    def test_deterministic_scores(self):
        rng = np.random.default_rng(99)
        times = (20.0 + rng.normal(0, 3, 60)).tolist()

        r1 = compute_iforest_anomalies(times)
        r2 = compute_iforest_anomalies(times)

        assert r1["scores"] == r2["scores"]
        assert r1["threshold_score"] == r2["threshold_score"]
        assert r1["is_anomaly"] == r2["is_anomaly"]
