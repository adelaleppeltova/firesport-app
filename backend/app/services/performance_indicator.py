from __future__ import annotations

import math
from typing import Iterable, Optional

from app.models.athlete import (
    PerformanceIndicator,
    PerformanceIndicatorTrend,
    RecentResult,
)


def _parse_time(value: object, status: Optional[str]) -> Optional[float]:
    status_raw = getattr(status, "value", status)
    status_value = str(status_raw).lower() if status_raw is not None else ""
    if status_value in {"invalid", "dnf"}:
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


def _median(values: Iterable[float]) -> Optional[float]:
    values_sorted = sorted(values)
    if not values_sorted:
        return None
    mid = len(values_sorted) // 2
    if len(values_sorted) % 2 == 1:
        return values_sorted[mid]
    return (values_sorted[mid - 1] + values_sorted[mid]) / 2


def _mean(values: Iterable[float]) -> Optional[float]:
    values_list = list(values)
    if not values_list:
        return None
    return sum(values_list) / len(values_list)


def _center_value(values: Iterable[float]) -> Optional[float]:
    # Prefer median (robust to outliers), fall back to mean if needed.
    median_value = _median(values)
    return median_value if median_value is not None else _mean(values)


def calculate_performance_indicator(entries: list[dict]) -> PerformanceIndicator:
    """
    Compute trend from last 6 valid results by competition date (newer 3 vs older 3).
    """
    dated_entries = [
        entry for entry in entries if entry.get("competition_date") is not None
    ]
    dated_entries.sort(key=lambda entry: entry["competition_date"], reverse=True)

    # Exclude invalid results (DNF, 999, null) before trend computation.
    valid_entries: list[dict] = []
    for entry in dated_entries:
        time_value = _parse_time(
            entry.get("final_time"), entry.get("final_time_status")
        )
        if time_value is None:
            continue
        valid_entries.append(
            {"time": time_value, "rank": entry.get("rank")}
        )

    recent_results = [
        RecentResult(final_time=item["time"], rank=item.get("rank"))
        for item in valid_entries[:5]
    ]

    sample = valid_entries[:6]
    if len(sample) < 6:
        return PerformanceIndicator(
            trend=PerformanceIndicatorTrend.insufficient,
            recent_results=recent_results,
        )

    # Method note: split last 6 into two groups of 3 and compare their medians.
    new_value = _center_value([item["time"] for item in sample[:3]])
    old_value = _center_value([item["time"] for item in sample[3:6]])
    if new_value is None or old_value is None:
        return PerformanceIndicator(
            trend=PerformanceIndicatorTrend.insufficient,
            recent_results=recent_results,
        )

    delta = old_value - new_value
    # Tolerance prevents labeling small noise as a trend.
    tau = max(0.05, 0.01 * old_value)
    if abs(delta) <= tau:
        trend = PerformanceIndicatorTrend.stable
    elif delta > tau:
        trend = PerformanceIndicatorTrend.up
    else:
        trend = PerformanceIndicatorTrend.down

    average_time = _mean([item["time"] for item in sample])

    return PerformanceIndicator(
        trend=trend,
        delta_seconds=delta,
        new_value=new_value,
        old_value=old_value,
        average_time=average_time,
        recent_results=recent_results,
    )
