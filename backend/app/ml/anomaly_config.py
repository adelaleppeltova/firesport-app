"""
Single source of truth for anomaly-detection hyper-parameters.

Every other module (isolation_forest, anomaly_service, models) imports
AnomalyConfig from here so there are **no duplicated magic numbers**.

Values can be overridden per-call; defaults are academically defensible
for Isolation Forest on small univariate time series.
"""

from pydantic import BaseModel, ConfigDict, Field


class AnomalyConfig(BaseModel):
    """Immutable configuration for one anomaly-detection run.

    Attributes:
        min_results:   Minimum number of valid times required to run the
                       model.  Below this the athlete is *skipped*.
        contamination: Expected proportion of anomalies (0 < c < 0.5).
                       Also drives the score threshold quantile
                       ``1 - contamination``.
        eps_std:       If ``std(times) < eps_std`` the series has
                       effectively no variance → skip.
        n_estimators:  Number of trees in the Isolation Forest ensemble.
        random_state:  Seed for reproducibility.
    """

    min_results: int = Field(default=10, ge=2, description="Min valid times to run model")
    contamination: float = Field(default=0.05, gt=0.0, lt=0.5, description="Expected anomaly fraction")
    eps_std: float = Field(default=0.01, ge=0.0, description="Low-variance guard (std threshold)")
    n_estimators: int = Field(default=200, ge=1, description="Number of Isolation Forest trees")
    random_state: int = Field(default=42, description="RNG seed for reproducibility")

    model_config = ConfigDict(frozen=True)


# Module-level singleton with safe defaults.
# Import this when you just need "the defaults" without constructing your own.
DEFAULT_CONFIG = AnomalyConfig()
