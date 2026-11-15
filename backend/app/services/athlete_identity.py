from __future__ import annotations

from typing import Any, Optional


def normalize_fs_code(value: Any) -> Optional[str]:
    if value is None:
        return None
    code = str(value).strip()
    return code or None


def normalize_fs_codes(*values: Any) -> list[str]:
    normalized: list[str] = []
    seen = set()

    for value in values:
        if value is None:
            continue

        items = value if isinstance(value, list) else [value]
        for item in items:
            code = normalize_fs_code(item)
            if not code or code in seen:
                continue
            seen.add(code)
            normalized.append(code)

    return normalized


def normalize_teams(*values: Any) -> list[str]:
    normalized: list[str] = []
    seen = set()

    for value in values:
        if value is None:
            continue

        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None:
                continue
            team = str(item).strip()
            if not team:
                continue
            key = team.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(team)

    return normalized


def normalize_athlete_identity(
    *,
    fs_codes: Any = None,
    teams: Any = None,
) -> tuple[list[str], list[str]]:
    normalized_fs_codes = normalize_fs_codes(fs_codes)
    normalized_teams = normalize_teams(teams)
    return normalized_fs_codes, normalized_teams


def normalize_athlete_document(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None

    normalized = dict(doc)
    (
        normalized["fs_codes"],
        normalized["teams"],
    ) = normalize_athlete_identity(
        fs_codes=normalized.get("fs_codes"),
        teams=normalized.get("teams"),
    )
    normalized.pop("fscode", None)
    normalized.pop("team", None)
    return normalized


def active_athlete_query(query: Optional[dict] = None) -> dict:
    normalized_query = dict(query or {})
    normalized_query["is_active"] = {"$ne": False}
    return normalized_query


def build_fs_code_query(fs_code: Any) -> Optional[dict]:
    normalized_code = normalize_fs_code(fs_code)
    if not normalized_code:
        return None

    # Historical imports can contain numerical codes in the array.
    values = [normalized_code]
    if normalized_code.isascii() and normalized_code.isdecimal() and len(normalized_code) <= 18:
        number = int(normalized_code)
        if str(number) == normalized_code:
            values.append(number)
    return {"fs_codes": {"$in": values}}


def is_valid_fs_code(code: str) -> bool:
    return len(code) >= 4 and code.isascii() and code.isdecimal()


def identity_group(
    first_name: str, last_name: str, birth_year: Optional[int], fscode: Any, team: Optional[str],
) -> tuple[str, str, int | None, str | None, str] | None:
    """Group explicit, equal observations. Membership is a review aid only."""
    code = normalize_fs_code(fscode)
    team_key = " ".join((team or "").casefold().split())
    if not first_name or not last_name or (code and not is_valid_fs_code(code)):
        return None
    if not code and (birth_year is None or not team_key):
        return None
    return first_name, last_name, birth_year, code, team_key
