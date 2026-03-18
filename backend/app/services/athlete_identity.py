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


def normalize_athlete_document(doc: Optional[dict]) -> Optional[dict]:
    if doc is None:
        return None

    normalized = dict(doc)
    normalized["fs_codes"] = normalize_fs_codes(
        normalized.get("fs_codes"),
        normalized.get("fscode"),
    )
    normalized["fscode"] = (
        normalized["fs_codes"][0] if normalized["fs_codes"] else None
    )
    normalized["teams"] = normalize_teams(
        normalized.get("teams"),
        normalized.get("team"),
    )
    return normalized


def active_athlete_query(query: Optional[dict] = None) -> dict:
    normalized_query = dict(query or {})
    normalized_query["is_active"] = {"$ne": False}
    return normalized_query


def build_fs_code_query(fs_code: Any) -> Optional[dict]:
    normalized_code = normalize_fs_code(fs_code)
    if not normalized_code:
        return None

    variants: list[Any] = [normalized_code]
    if normalized_code.isdigit():
        variants.append(int(normalized_code))

    return {
        "$or": [
            {"fs_codes": normalized_code},
            {"fscode": {"$in": variants}},
        ]
    }
