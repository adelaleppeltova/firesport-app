"""
Single source of truth for anomaly-detection hyper-parameters.

Every other module (isolation_forest, anomaly_service, models) imports
AnomalyConfig from here so there are **no duplicated magic numbers**.

The current methodology always fits Isolation Forest with
``contamination="auto"``.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


from app.category_catalog import Category


def get_category_group(category: Category) -> str:
    """Use comparable individual groups while keeping disciplines separate."""
    if category.discipline == "60m":
        return category.name
    if category.gender == "female":
        return "zena"
    return "muz" if category.min_age >= 17 else "mladsi_dorostenci"


class AnomalyConfig(BaseModel):
    """Immutable configuration for one anomaly-detection run.

    Attributes:
        min_results:   Minimum number of valid times required to run the
                       model.  Below this the athlete is *skipped*.
        contamination: Isolation Forest contamination mode. The pipeline
                       always uses ``"auto"`` and does not derive any
                       custom score quantile threshold.
        eps_std:       If ``std(times) < eps_std`` the series has
                       effectively no variance → skip.
        n_estimators:  Number of trees in the Isolation Forest ensemble.
        random_state:  Seed for reproducibility.
    """

    min_results: int = Field(default=10, ge=2, description="Min valid times to run model")
    contamination: Literal["auto"] = Field(
        default="auto",
        description='Isolation Forest contamination mode. Always "auto".',
    )
    eps_std: float = Field(default=0.01, ge=0.0, description="Low-variance guard (std threshold)")
    n_estimators: int = Field(default=200, ge=1, description="Number of Isolation Forest trees")
    random_state: int = Field(default=42, description="RNG seed for reproducibility")

    model_config = ConfigDict(frozen=True)


# Module-level singleton with safe defaults.
# Import this when you just need "the defaults" without constructing your own.
DEFAULT_CONFIG = AnomalyConfig()
