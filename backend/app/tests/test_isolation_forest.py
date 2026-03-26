"""Unit tests for the Isolation Forest anomaly detection pipeline."""

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from app.ml.anomaly_config import AnomalyConfig, DEFAULT_CONFIG
from app.ml.isolation_forest import compute_iforest_anomalies


def _make_config(**overrides) -> AnomalyConfig:
    """Return a config with optional overrides on top of defaults."""
    return AnomalyConfig(**overrides)


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

    def test_nan_inf_cleaning_triggers_skip(self):
        cfg = _make_config(min_results=10)
        times = [15.0] * 5 + [float("nan")] * 3 + [float("inf"), float("-inf")]
        result = compute_iforest_anomalies(times, config=cfg)
        assert result["status"] == "skipped"
        assert result["reason"] == "not_enough_data_after_cleaning"


class TestLowVariance:
    """Skip when std(times) < eps_std."""

    def test_constant_times(self):
        times = [20.0] * 15
        result = compute_iforest_anomalies(times)
        assert result["status"] == "skipped"
        assert result["reason"] == "low_variance"


class TestSuccessShape:
    """On success, list outputs must match the cleaned input length."""

    @pytest.fixture()
    def success_result(self):
        rng = np.random.default_rng(42)
        times = (18.0 + rng.normal(0, 2, 50)).tolist()
        return compute_iforest_anomalies(times)

    def test_status_is_success(self, success_result):
        assert success_result["status"] == "success"

    def test_scores_length(self, success_result):
        assert len(success_result["scores"]) == success_result["n"]

    def test_is_anomaly_length(self, success_result):
        assert len(success_result["is_anomaly"]) == success_result["n"]

    def test_direction_length(self, success_result):
        assert len(success_result["direction"]) == success_result["n"]


class TestIsolationForestDecisionRule:
    """The classifier must follow Isolation Forest directly."""

    def test_score_is_negated_decision_function_and_flags_match_predict(self):
        times = [20.2, 20.1, 20.4, 20.3, 20.5, 20.6, 20.0, 20.2, 19.9, 20.1, 16.5, 24.8]
        cfg = _make_config(min_results=10, n_estimators=64, random_state=7, contamination=0.2)

        result = compute_iforest_anomalies(times, config=cfg)

        assert result["status"] == "success"
        X = np.asarray(times, dtype=np.float64).reshape(-1, 1)
        model = IsolationForest(
            n_estimators=cfg.n_estimators,
            contamination="auto",
            random_state=cfg.random_state,
            n_jobs=-1,
        )
        model.fit(X)

        expected_scores = (-model.decision_function(X)).astype(float).tolist()
        expected_flags = [bool(flag == -1) for flag in model.predict(X)]

        assert result["scores"] == pytest.approx(expected_scores)
        assert result["is_anomaly"] == expected_flags

    def test_contamination_mode_is_auto(self):
        small = compute_iforest_anomalies([20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.0, 20.7, 20.8, 24.0])
        large = compute_iforest_anomalies(
            [20.0, 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7, 20.8, 20.9, 21.0, 21.1, 21.2, 25.0]
        )

        assert small["status"] == "success"
        assert large["status"] == "success"
        assert small["contamination_mode"] == "auto"
        assert large["contamination_mode"] == "auto"


class TestUsedParamsEchoed:
    """Every result dict must include the expected *_used keys."""

    _USED_KEYS = {
        "min_results_used",
        "contamination_mode",
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


class TestReproducibility:
    """Same input + same random_state -> identical output."""

    def test_deterministic_scores(self):
        rng = np.random.default_rng(99)
        times = (20.0 + rng.normal(0, 3, 60)).tolist()

        r1 = compute_iforest_anomalies(times)
        r2 = compute_iforest_anomalies(times)

        assert r1["scores"] == r2["scores"]
        assert r1["is_anomaly"] == r2["is_anomaly"]
