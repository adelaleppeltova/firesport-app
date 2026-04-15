from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from app.db.database import db
from app.models.result import MatchStatus
from app.services.athlete_identity import (
    active_athlete_query,
    build_fs_code_query,
    normalize_athlete_document,
    normalize_fs_code,
)

athletes_collection = db["athletes"]


def normalize_person_name(value: Optional[str]) -> str:
    stripped = (value or "").strip()
    if not stripped:
        return ""
    return "".join(part[:1].upper() + part[1:].lower() for part in stripped.split())


async def _find_athletes(query: Dict[str, Any], limit: int = 10) -> list[dict]:
    docs = await athletes_collection.find(active_athlete_query(query)).limit(limit).to_list(
        length=limit
    )
    return [normalize_athlete_document(doc) for doc in docs]


def _team_matches(imported_team: Optional[str], athlete_teams: Optional[list[str]]) -> bool:
    if not imported_team or not athlete_teams:
        return False

    normalized_imported = imported_team.strip().casefold()
    return any((team or "").strip().casefold() == normalized_imported for team in athlete_teams)


def _has_conflicting_birth_year(athlete: dict, imported_birth_year: Optional[int]) -> bool:
    existing_value = athlete.get("birth_year")
    return (
        imported_birth_year is not None
        and existing_value is not None
        and existing_value != imported_birth_year
    )


def _athlete_has_fs_code(athlete: dict, imported_fscode: Optional[str]) -> bool:
    normalized_fscode = normalize_fs_code(imported_fscode)
    if not normalized_fscode:
        return False

    fs_codes = athlete.get("fs_codes") or []
    return normalized_fscode in fs_codes


def build_match_enrichment_update(
    *,
    athlete: dict,
    imported_athlete: Dict[str, Any],
    team: Optional[str],
    match_reason: Optional[str],
) -> Dict[str, Any]:
    update: Dict[str, Any] = {}
    set_fields: Dict[str, Any] = {}
    add_to_set_fields: Dict[str, Any] = {}

    normalized_athlete = normalize_athlete_document(athlete) or athlete

    if (
        imported_athlete.get("birth_year") is not None
        and normalized_athlete.get("birth_year") is None
    ):
        set_fields["birth_year"] = imported_athlete["birth_year"]

    normalized_fscode = normalize_fs_code(imported_athlete.get("fscode"))
    if normalized_fscode and normalized_fscode not in (
        normalized_athlete.get("fs_codes") or []
    ):
        add_to_set_fields["fs_codes"] = normalized_fscode

    if team and team not in (normalized_athlete.get("teams") or []):
        add_to_set_fields["teams"] = team

    if set_fields:
        set_fields["updated_at"] = datetime.utcnow()
        update["$set"] = set_fields
    elif add_to_set_fields:
        update["$set"] = {"updated_at": datetime.utcnow()}

    if add_to_set_fields:
        update["$addToSet"] = {
            key: value for key, value in add_to_set_fields.items() if value is not None
        }

    return update


async def decide_athlete_match(
    *,
    first_name: str,
    last_name: str,
    birth_year: Optional[int],
    fscode: Optional[str],
    team: Optional[str] = None,
) -> Dict[str, Any]:
    if not first_name or not last_name:
        return {
            "match_status": MatchStatus.unmatched,
            "match_reason": "missing_name",
            "matched_athlete": None,
        }

    name_matches = await _find_athletes(
        {"first_name": first_name, "last_name": last_name},
        limit=10,
    )

    if not name_matches:
        return {
            "match_status": MatchStatus.unmatched,
            "match_reason": "no_match",
            "matched_athlete": None,
        }

    team_matches = [
        athlete for athlete in name_matches if _team_matches(team, athlete.get("teams"))
    ]

    if birth_year is None:
        if len(team_matches) == 1:
            return {
                "match_status": MatchStatus.matched,
                "match_reason": "name_plus_team",
                "matched_athlete": team_matches[0],
            }
        if len(team_matches) > 1:
            return {
                "match_status": MatchStatus.needs_review,
                "match_reason": "multiple_name_plus_team_candidates",
                "matched_athlete": None,
            }
        return {
            "match_status": MatchStatus.needs_review,
            "match_reason": "name_only_missing_birth_year",
            "matched_athlete": None,
        }

    strong_matches = [
        athlete
        for athlete in name_matches
        if athlete.get("birth_year") == birth_year
    ]

    if len(strong_matches) == 1:
        return {
            "match_status": MatchStatus.matched,
            "match_reason": "name_plus_birth_year",
            "matched_athlete": strong_matches[0],
        }

    if len(strong_matches) > 1:
        fs_code_matches = [
            athlete for athlete in strong_matches if _athlete_has_fs_code(athlete, fscode)
        ]
        if len(fs_code_matches) == 1:
            return {
                "match_status": MatchStatus.matched,
                "match_reason": "name_plus_birth_year_and_fscode",
                "matched_athlete": fs_code_matches[0],
            }
        return {
            "match_status": MatchStatus.needs_review,
            "match_reason": "multiple_name_plus_birth_year_candidates",
            "matched_athlete": None,
        }

    compatible_team_matches = [
        athlete for athlete in team_matches if not _has_conflicting_birth_year(athlete, birth_year)
    ]
    if len(compatible_team_matches) == 1 and compatible_team_matches[0].get("birth_year") is None:
        return {
            "match_status": MatchStatus.matched,
            "match_reason": "name_plus_team",
            "matched_athlete": compatible_team_matches[0],
        }
    if len(compatible_team_matches) > 1:
        return {
            "match_status": MatchStatus.needs_review,
            "match_reason": "multiple_name_plus_team_candidates",
            "matched_athlete": None,
        }

    if any(_has_conflicting_birth_year(athlete, birth_year) for athlete in name_matches):
        return {
            "match_status": MatchStatus.unmatched,
            "match_reason": "name_match_conflicting_birth_year_create_new",
            "matched_athlete": None,
        }

    fs_code_query = build_fs_code_query(fscode)
    if fs_code_query:
        fs_code_matches = await _find_athletes(fs_code_query, limit=10)
        named_fs_code_matches = [
            athlete
            for athlete in fs_code_matches
            if athlete.get("first_name") == first_name and athlete.get("last_name") == last_name
        ]
        if len(named_fs_code_matches) == 1 and not _has_conflicting_birth_year(
            named_fs_code_matches[0], birth_year
        ):
            return {
                "match_status": MatchStatus.matched,
                "match_reason": "name_plus_fscode_missing_birth_year_on_athlete",
                "matched_athlete": named_fs_code_matches[0],
            }

    return {
        "match_status": MatchStatus.needs_review,
        "match_reason": "name_only",
        "matched_athlete": None,
    }
