"""Name validation and interpretation of result values, including legacy rows."""

import math
import re
import unicodedata
from collections.abc import Mapping

NAME_FIELDS = ("first_name", "last_name")
_NAME_PLACEHOLDERS = {
    "n/a",
    "null",
    "none",
    "neznamy",
    "neznama",
    "bez jmena",
    "neobsazen",
    "neobsazena",
    "neobsazeno",
    "nestartuje",
    "nestartoval",
    "nestartovala",
    "nestartovalo",
    "nestartovali",
    "volno",
    "np",
    "dns",
    "dnf",
    "dsq",
}
_TIME_SENTINELS = {998, 999, 999.99, 999990}


def valid_name_component(value: object) -> bool:
    if not isinstance(value, str):
        return False
    value = unicodedata.normalize("NFC", value).strip()
    folded = "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )
    if not value or " ".join(folded.split()) in _NAME_PLACEHOLDERS:
        return False
    return all(
        part
        and part[0].isalpha()
        and all(
            char.isalpha() or unicodedata.category(char).startswith("M")
            for char in part
        )
        for part in re.split(
            r"[ '\u2019\u02bc\-\u2010\u2011]+", " ".join(value.split())
        )
    )


def invalid_name_fields(person: object) -> tuple[str, ...]:
    if not isinstance(person, Mapping):
        return NAME_FIELDS
    return tuple(
        field for field in NAME_FIELDS if not valid_name_component(person.get(field))
    )


def measured_seconds(value: object) -> float | None:
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    elif type(value) not in (int, float):
        return None
    try:
        seconds = float(value)
    except (ValueError, OverflowError):
        return None
    if math.isfinite(seconds) and seconds > 0 and seconds not in _TIME_SENTINELS:
        return seconds
    return None


def valid_seconds(value: object, status: str | None) -> float | None:
    """Allow numeric legacy values with no status, honor explicit statuses."""
    if status is None or status == "valid":
        return measured_seconds(value)
    return None


def final_result_fields(row: Mapping, *, status_key: str = "final_time_status") -> dict:
    raw_time, status = row.get("final_time"), row.get(status_key)
    seconds = valid_seconds(raw_time, status)
    if seconds is not None:
        status = "valid"
    elif status != "missing":
        status = "missing" if status is None and raw_time is None else "invalid"
    source = row.get("final_time_source")
    return {
        "final_time": seconds,
        "final_time_status": status,
        "final_time_source": source
        if seconds is not None and source in ("published", "derived_from_attempts")
        else None,
    }


VALID_FINAL_QUERY = {
    "final_time_status": {"$in": ["valid", None]},
    "final_time": {"$ne": None},
}


def valid_final_time(row: Mapping) -> float | None:
    return valid_seconds(row.get("final_time"), row.get("final_time_status"))


def select_performance_series(results, categories, discipline=None):
    """Select one known discipline or one legacy category for scalar metrics."""

    def category(row):
        return categories.get(str(row.get("category")), {})

    known = {
        item["discipline"]
        for row in results
        if (item := category(row)).get("discipline")
    }
    if discipline is not None or known:
        selected = discipline
        if selected is None:
            selected = next((code for code in ("100m", "60m") if code in known), None)
            if selected is None and len(known) == 1:
                selected = next(iter(known))
        return (
            [
                row
                for row in results
                if selected and category(row).get("discipline") == selected
            ],
            selected,
            None,
        )

    legacy = {
        str(row["category"]) for row in results if row.get("category") is not None
    }
    if len(legacy) == 1:
        category_id = next(iter(legacy))
        if category_id in categories:
            return (
                [row for row in results if str(row.get("category")) == category_id],
                None,
                category_id,
            )
    return [], None, None


def attempt_result_fields(attempt: Mapping) -> dict:
    raw_time, status = attempt.get("time"), attempt.get("status")
    time = measured_seconds(raw_time)
    if status is None:
        status = (
            "missing"
            if raw_time is None
            else "valid"
            if time is not None
            else "invalid"
        )
    elif status != "missing" and (status != "valid" or time is None):
        status = "invalid"
    return {"time": None if status == "missing" else time, "status": status}


def best_valid_attempt(attempts) -> float | None:
    return min(
        (
            time
            for attempt in attempts
            if attempt.get("try") in (1, 2)
            and attempt.get("status") == "valid"
            and (time := measured_seconds(attempt.get("time"))) is not None
        ),
        default=None,
    )
