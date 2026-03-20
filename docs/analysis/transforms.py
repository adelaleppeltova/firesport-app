"""Pandas transforms and summaries for exploratory data analysis."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd


def results_to_dataframe(results: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert flattened results to a pandas DataFrame."""
    df = pd.DataFrame(results)

    if "competition_date" in df.columns:
        df["competition_date"] = pd.to_datetime(df["competition_date"], errors="coerce")

    if "final_time" in df.columns:
        df["final_time"] = pd.to_numeric(df["final_time"], errors="coerce")

    if "birth_year" in df.columns:
        df["birth_year"] = pd.to_numeric(df["birth_year"], errors="coerce")

    if "rank" in df.columns:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce")

    return df


def competitions_to_dataframe(competitions: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert competition rows to a pandas DataFrame."""
    df = pd.DataFrame(competitions)

    if "competition_date" in df.columns:
        df["competition_date"] = pd.to_datetime(df["competition_date"], errors="coerce")

    return df


def add_quality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add helper columns for simple data quality checks."""
    flagged = df.copy()
    first_name = flagged.get("first_name", pd.Series("", index=flagged.index))
    last_name = flagged.get("last_name", pd.Series("", index=flagged.index))
    birth_year = flagged.get("birth_year", pd.Series([pd.NA] * len(flagged), index=flagged.index))
    fscode = flagged.get("fscode", pd.Series([None] * len(flagged), index=flagged.index))
    team = flagged.get("team", pd.Series([None] * len(flagged), index=flagged.index))
    final_time = flagged.get("final_time", pd.Series([pd.NA] * len(flagged), index=flagged.index))
    final_status = flagged.get("final_status", pd.Series([None] * len(flagged), index=flagged.index))

    flagged["athlete_full_name"] = (
        first_name.fillna("").astype(str).str.strip()
        + " "
        + last_name.fillna("").astype(str).str.strip()
    ).str.strip()

    flagged["has_missing_birth_year"] = birth_year.isna()
    flagged["has_missing_fscode"] = _is_missing_text(fscode)
    flagged["has_missing_team"] = _is_missing_text(team)
    flagged["final_time_is_missing"] = final_time.isna()
    flagged["final_time_is_invalid"] = final_status.fillna("").ne("valid")

    times_series = flagged.get("times", pd.Series([None] * len(flagged), index=flagged.index))
    flagged["has_missing_attempts"] = times_series.apply(_has_missing_attempts)
    flagged["invalid_attempt_count"] = times_series.apply(_count_invalid_attempts)
    flagged["valid_attempt_count"] = times_series.apply(_count_valid_attempts)

    flagged["suspicious_final_time"] = (
        flagged["final_time_is_missing"]
        | flagged["final_time_is_invalid"]
        | final_time.ge(90).fillna(False)
        | final_time.eq(999).fillna(False)
    )

    return flagged


def summarize_dataset(df: pd.DataFrame) -> dict[str, Any]:
    """Return a compact overview of the dataset."""
    date_series = pd.to_datetime(df.get("competition_date"), errors="coerce")
    disciplines = sorted(value for value in df.get("discipline", pd.Series(dtype=object)).dropna().unique())

    return {
        "athlete_count": int(df.get("athlete_full_name", _build_full_name(df)).replace("", pd.NA).dropna().nunique()),
        "result_count": int(len(df)),
        "competition_count": int(
            df[["competition_name", "competition_place", "competition_date"]]
            .drop_duplicates()
            .shape[0]
        )
        if {"competition_name", "competition_place", "competition_date"}.issubset(df.columns)
        else 0,
        "min_date": date_series.min().date().isoformat() if date_series.notna().any() else None,
        "max_date": date_series.max().date().isoformat() if date_series.notna().any() else None,
        "disciplines": disciplines,
    }


def summarize_final_times(df: pd.DataFrame) -> dict[str, Any]:
    """Return basic statistics for reliable final times only."""
    working = df.copy()

    if "suspicious_final_time" not in working.columns:
        working = add_quality_flags(working)

    valid_times = working.loc[
        (working.get("final_status") == "valid")
        & working.get("final_time").notna()
        & ~working.get("suspicious_final_time"),
        "final_time",
    ]

    if valid_times.empty:
        return {"mean": None, "median": None, "min": None, "max": None, "std": None}

    return {
        "mean": float(valid_times.mean()),
        "median": float(valid_times.median()),
        "min": float(valid_times.min()),
        "max": float(valid_times.max()),
        "std": float(valid_times.std()),
    }


def summarize_data_quality(df: pd.DataFrame) -> dict[str, int]:
    """Return counts for selected quality issues."""
    working = df.copy()

    if "has_missing_birth_year" not in working.columns:
        working = add_quality_flags(working)

    return {
        "missing_birth_year_count": int(working["has_missing_birth_year"].sum()),
        "missing_fscode_count": int(working["has_missing_fscode"].sum()),
        "missing_team_count": int(working["has_missing_team"].sum()),
        "missing_attempts_count": int(working["has_missing_attempts"].sum()),
        "suspicious_final_time_count": int(working["suspicious_final_time"].sum()),
        "duplicate_rows_count": int(_prepare_for_duplicate_check(working).duplicated().sum()),
    }


def find_possible_duplicate_athletes(df: pd.DataFrame) -> pd.DataFrame:
    """Find athlete names with multiple teams, FS codes or birth years."""
    working = df.copy()

    if "athlete_full_name" not in working.columns:
        working = add_quality_flags(working)

    grouped = (
        working.assign(
            team_normalized=working.get("team", pd.Series([None] * len(working), index=working.index)).apply(_normalize_text),
            fscode_normalized=working.get("fscode", pd.Series([None] * len(working), index=working.index)).apply(_normalize_text),
        )
        .groupby("athlete_full_name", dropna=False)
        .agg(
            team_count=("team_normalized", _count_non_null_unique),
            fscode_count=("fscode_normalized", _count_non_null_unique),
            birth_year_count=("birth_year", lambda s: s.dropna().nunique()),
            teams=("team", _sorted_unique_values),
            fs_codes=("fscode", _sorted_unique_values),
            birth_years=("birth_year", _sorted_unique_values),
            result_count=("athlete_full_name", "size"),
        )
        .reset_index()
    )

    filtered = grouped.loc[
        grouped["athlete_full_name"].fillna("").ne("")
        & (
            (grouped["team_count"] > 1)
            | (grouped["fscode_count"] > 1)
            | (grouped["birth_year_count"] > 1)
        )
    ]

    return filtered.sort_values(["result_count", "athlete_full_name"], ascending=[False, True]).reset_index(drop=True)


def find_inconsistent_team_names(df: pd.DataFrame) -> pd.DataFrame:
    """Find team names that differ only in casing or surrounding spaces."""
    if "team" not in df.columns:
        return pd.DataFrame(columns=["team_key", "variant_count", "variants", "result_count"])

    working = df.copy()
    working["team_key"] = working["team"].apply(_normalize_text)
    working = working.loc[working["team_key"].notna()].copy()

    if working.empty:
        return pd.DataFrame(columns=["team_key", "variant_count", "variants", "result_count"])

    grouped = (
        working.groupby("team_key")
        .agg(
            variant_count=("team", lambda s: s.dropna().astype(str).str.strip().nunique()),
            variants=("team", _sorted_unique_values),
            result_count=("team", "size"),
        )
        .reset_index()
    )

    return grouped.loc[grouped["variant_count"] > 1].sort_values(
        ["variant_count", "result_count", "team_key"], ascending=[False, False, True]
    ).reset_index(drop=True)


def find_missing_attempts(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with missing or incomplete attempts."""
    working = df.copy()

    if "has_missing_attempts" not in working.columns:
        working = add_quality_flags(working)

    return working.loc[working["has_missing_attempts"]].reset_index(drop=True)


def _build_full_name(df: pd.DataFrame) -> pd.Series:
    first_names = df.get("first_name", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
    last_names = df.get("last_name", pd.Series("", index=df.index)).fillna("").astype(str).str.strip()
    return (first_names + " " + last_names).str.strip()


def _is_missing_text(series: pd.Series | None) -> pd.Series:
    if series is None:
        return pd.Series(dtype=bool)
    text = series.fillna("").astype(str).str.strip()
    return text.eq("")


def _has_missing_attempts(times: Any) -> bool:
    if not isinstance(times, list) or len(times) < 2:
        return True

    for attempt in times:
        if not isinstance(attempt, dict):
            return True
        if "try" not in attempt or "status" not in attempt:
            return True

    return False


def _count_invalid_attempts(times: Any) -> int:
    if not isinstance(times, list):
        return 0
    return sum(1 for attempt in times if isinstance(attempt, dict) and attempt.get("status") != "valid")


def _count_valid_attempts(times: Any) -> int:
    if not isinstance(times, list):
        return 0
    return sum(1 for attempt in times if isinstance(attempt, dict) and attempt.get("status") == "valid")


def _normalize_text(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    return text.lower()


def _sorted_unique_values(series: pd.Series) -> list[Any]:
    values: list[Any] = []

    for value in series.dropna():
        if hasattr(value, "item"):
            value = value.item()
        if value not in values:
            values.append(value)

    return sorted(values, key=lambda item: str(item))


def _count_non_null_unique(series: pd.Series) -> int:
    return int(series.dropna().nunique())


def _prepare_for_duplicate_check(df: pd.DataFrame) -> pd.DataFrame:
    """Convert unhashable values to stable strings before duplicate checks."""
    comparable = df.copy()

    for column in comparable.columns:
        comparable[column] = comparable[column].apply(_make_hashable)

    return comparable


def _make_hashable(value: Any) -> Any:
    if isinstance(value, list):
        return json.dumps([_make_hashable(item) for item in value], ensure_ascii=False, sort_keys=True)

    if isinstance(value, dict):
        return json.dumps(
            {str(key): _make_hashable(item) for key, item in sorted(value.items())},
            ensure_ascii=False,
            sort_keys=True,
        )

    return value
