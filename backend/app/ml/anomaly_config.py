"""
Single source of truth for anomaly-detection hyper-parameters.

Every other module (isolation_forest, anomaly_service, models) imports
AnomalyConfig from here so there are **no duplicated magic numbers**.

The current methodology always fits Isolation Forest with
``contamination="auto"``.
"""

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


# ------------------------------------------------------------------
# Skupiny porovnatelných kategorií
# ------------------------------------------------------------------

# Klíč: normalizovaný název kategorie (lowercase, strip)
# Hodnota: identifikátor skupiny
#
# Logika seskupení dle uživatelské definice:
#   muz              → muži + starší dorostenci + muži a starší dorostenci
#   zena             → ženy + mladší dorostenky + střední dorostenky +
#                      starší dorostenky + ženy a starší dorostenky
#   mladsi_dorostenci → mladší dorostenci + střední dorostenci

CATEGORY_GROUP_MAP: dict[str, str] = {
    # muži skupinka
    "muži": "muz",
    "dorostenci": "muz",
    "starší dorostenci": "muz",
    "muži a starší dorostenci": "muz",
    "muži hzs": "muz",
    # ženy skupinka
    "ženy": "zena",
    "dorostenky": "zena",
    "mladší dorostenky": "zena",
    "střední dorostenky": "zena",
    "starší dorostenky": "zena",
    "ženy a starší dorostenky": "zena",
    # mladší/střední dorostenci skupinka
    "mladší dorostenci": "mladsi_dorostenci",
    "střední dorostenci": "mladsi_dorostenci",
    "dorostenci střední": "mladsi_dorostenci",
}


def get_category_group(category_name: str) -> str:
    """Vrátí identifikátor skupiny porovnatelných kategorií.

    Porovnání je case-insensitive a ignoruje okolní bílé znaky.
    Pokud kategorie neodpovídá žádné definované skupině, vrátí
    normalizovaný název kategorie (každá neznámá kategorie je sama
    sobě skupinou – výsledky se nemíchají s jinými).

    Parameters
    ----------
    category_name:
        Název kategorie z databáze (např. "Muži", "Ženy", ...).

    Returns
    -------
    str
        Identifikátor skupiny, např. ``"muz"``, ``"zena"``,
        ``"mladsi_dorostenci"``, nebo normalizovaný název kategorie.
    """
    normalized = category_name.strip().lower()
    return CATEGORY_GROUP_MAP.get(normalized, normalized)


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
