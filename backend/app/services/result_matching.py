from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

from app.db.database import db
from app.models.result import MatchStatus
from app.person_names import normalize_person_name
from app.services.athlete_identity import (
    active_athlete_query,
    build_fs_code_query,
    normalize_athlete_document,
)
from app.services.search_utils import build_diacritic_fuzzy_regex

athletes_collection = db["athletes"]
DIFFERENT_TEAM = "name_birth_year_different_team"


def team_key(team: str | None) -> str:
    key = " ".join(unicodedata.normalize("NFC", team or "").lower().split())
    if key in {"sdh", "bez klubu", "bez sboru", "neznámý", "neznamy", "neuvedeno", "nezadáno", "null", "none", "n/a"}:
        return ""
    return key if any(char.isalpha() for char in key) else ""


def build_name_candidate_query(value: str) -> dict:
    unaccented = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if not unicodedata.combining(char)
    )
    pattern = r"\s*".join(build_diacritic_fuzzy_regex(char) for char in unaccented if char != " ")
    return {"$regex": rf"^\s*{pattern}\s*$", "$options": "i"}


async def _find_athletes(query: dict, *, limit: Optional[int] = None) -> list[dict]:
    cursor = athletes_collection.find(active_athlete_query(query))
    if limit is not None:
        cursor = cursor.limit(limit)
    return [normalize_athlete_document(doc) for doc in await cursor.to_list(length=limit)]


def _decision(status: MatchStatus, reason: str, athlete: Optional[dict] = None) -> dict:
    return {"match_status": status, "match_reason": reason, "matched_athlete": athlete}


def decide_team_match(candidates: list[dict], team: str | None) -> dict | None:
    """Resolve the club among profiles with an exact name and birth year."""
    key = team_key(team)
    if not key:
        return None

    matching = []
    known_team = False
    for candidate in candidates:
        teams = {team_key(value) for value in candidate.get("teams", [])} - {""}
        known_team |= bool(teams)
        if key in teams:
            matching.append(candidate)
    if len(matching) == 1:
        return _decision(MatchStatus.matched, "name_birth_year_team", matching[0])
    if matching:
        return _decision(MatchStatus.needs_review, "multiple_name_candidates")
    if known_team:
        return _decision(MatchStatus.needs_review, DIFFERENT_TEAM)
    return None


async def decide_athlete_match(
    *,
    first_name: str,
    last_name: str,
    birth_year: Optional[int],
    fscode: Optional[str],
    team: Optional[str] = None,
) -> dict[str, Any]:
    first_name = normalize_person_name(first_name)
    last_name = normalize_person_name(last_name)
    if not first_name or not last_name:
        return _decision(MatchStatus.needs_review, "missing_name")

    code_query = build_fs_code_query(fscode)
    code_matches = await _find_athletes(code_query, limit=2) if code_query else []
    first_pattern, last_pattern = build_name_candidate_query(first_name), build_name_candidate_query(last_name)
    name_matches = await _find_athletes({"first_name": first_pattern, "last_name": last_pattern})
    exact_name_ids = {
        athlete["_id"] for athlete in name_matches
        if normalize_person_name(athlete.get("first_name")).casefold() == first_name.casefold()
        and normalize_person_name(athlete.get("last_name")).casefold() == last_name.casefold()
    }
    compatible = [
        athlete for athlete in name_matches
        if birth_year is None or athlete.get("birth_year") in (None, birth_year)
    ]

    if type(birth_year) is int and birth_year >= 1900:
        same_year = [
            athlete for athlete in compatible
            if athlete["_id"] in exact_name_ids and athlete.get("birth_year") == birth_year
        ]
        if team_match := decide_team_match(same_year, team):
            return team_match

    if len(code_matches) > 1:
        return _decision(MatchStatus.needs_review, "shared_fscode")

    if code_matches:
        owner = code_matches[0]
        conflicting_year = birth_year is not None and owner.get("birth_year") not in (None, birth_year)
        if owner["_id"] not in exact_name_ids or conflicting_year:
            return _decision(MatchStatus.needs_review, "conflicting_fscode")
        if birth_year is not None and owner.get("birth_year") is None and any(
            other["_id"] != owner["_id"] and other.get("birth_year") == birth_year
            for other in compatible
        ):
            return _decision(MatchStatus.needs_review, "conflicting_fscode")
        return _decision(MatchStatus.matched, "name_plus_fscode", owner)

    if len(compatible) == 1:
        athlete = compatible[0]
        if (
            athlete["_id"] in exact_name_ids and birth_year is not None
            and athlete.get("birth_year") == birth_year
        ):
            if code_query and athlete.get("fs_codes"):
                return _decision(MatchStatus.needs_review, "unrecognized_fscode")
            return _decision(MatchStatus.matched, "name_plus_birth_year", athlete)

    if len(compatible) > 1:
        return _decision(MatchStatus.needs_review, "multiple_name_candidates")
    if name_matches:
        reason = "insufficient_identity" if compatible else "conflicting_birth_year"
        return _decision(MatchStatus.needs_review, reason)

    # A matching year or historical team can surface a possible typo in one name.
    supporting = []
    if birth_year is not None:
        supporting.append({"birth_year": birth_year})
    if team:
        supporting.append({"teams": {"$regex": rf"^{re.escape(team)}$", "$options": "i"}})
    if supporting and await _find_athletes(
        {"$and": [
            {"$or": [{"first_name": first_pattern}, {"last_name": last_pattern}]},
            {"$or": supporting},
        ]},
        limit=1,
    ):
        return _decision(MatchStatus.needs_review, "possible_name_variant")

    return _decision(MatchStatus.unmatched, "no_match")
