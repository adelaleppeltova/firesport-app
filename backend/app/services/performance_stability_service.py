from __future__ import annotations

import math
from typing import Any, Mapping, Optional, Sequence, TypedDict


class PerformanceStabilityResult(TypedDict):
    stability_rating: str
    performance_variability: Optional[float]
    n_used: int


_INSUFFICIENT_RATING = "Nedostatek dat"
_THRESHOLDS = (
    (0.20, "Velmi stabilní výkony"),
    (0.50, "Stabilní výkony"),
    (1.00, "Kolísavé výkony"),
)
_DEFAULT_RATING = "Velmi kolísavé výkony"


def _normalize_status(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw).strip().lower() if raw is not None else ""


def _parse_time(
    value: object,
    status: object | None = None,
    validity: object | None = None,
) -> Optional[float]:
    status_value = _normalize_status(status)
    if status_value in {"invalid", "dnf"}:
        return None

    if validity is not None:
        if isinstance(validity, bool):
            if not validity:
                return None
        else:
            validity_value = _normalize_status(validity)
            if validity_value in {"invalid", "dnf", "false", "0"}:
                return None

    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            return None
    try:
        time_value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(time_value):
        return None
    if time_value >= 999:
        return None
    return time_value


def _order_entries(
    entries: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    entries_list = list(entries)
    if not entries_list:
        return []
    has_dates = any(entry.get("competition_date") is not None for entry in entries_list)
    if not has_dates:
        return entries_list
    dated = [entry for entry in entries_list if entry.get("competition_date") is not None]
    dated.sort(key=lambda entry: entry["competition_date"], reverse=True)
    undated = [entry for entry in entries_list if entry.get("competition_date") is None]
    return dated + undated


def _rating_for_variability(variability: float) -> str:
    for threshold, label in _THRESHOLDS:
        if variability <= threshold:
            return label
    return _DEFAULT_RATING


def evaluate_performance_stability(
    results: Sequence[Mapping[str, Any]],
) -> PerformanceStabilityResult:
    """
    Compute stability from the last 6 valid times.
    Validity is derived from final_time_status or a 'validity' flag when present.
    """
    ordered = _order_entries(results)
    valid_times: list[float] = []
    for entry in ordered:
        time_value = _parse_time(
            entry.get("final_time"),
            entry.get("final_time_status"),
            entry.get("validity"),
        )
        if time_value is None:
            continue
        valid_times.append(time_value)
        if len(valid_times) >= 6:
            break

    n_used = len(valid_times)
    if n_used < 3:
        return {
            "stability_rating": _INSUFFICIENT_RATING,
            "performance_variability": None,
            "n_used": n_used,
        }

    variability = max(valid_times) - min(valid_times)
    return {
        "stability_rating": _rating_for_variability(variability),
        "performance_variability": variability,
        "n_used": n_used,
    }
