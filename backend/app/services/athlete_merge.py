from __future__ import annotations

from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.db.database import db
from app.models.admin import AthleteMergeCandidate, AthleteMergeCandidatesResponse
from app.services.athlete_identity import (
    active_athlete_query,
    normalize_athlete_document,
)
from app.services.search_utils import build_diacritic_fuzzy_regex

athletes_collection = db["athletes"]
results_collection = db["results"]
users_collection = db["users"]


def _parse_oid(value: str, field_name: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}") from exc


def _resolve_birth_year(target: dict, source: dict) -> Optional[int]:
    target_birth_year = target.get("birth_year")
    source_birth_year = source.get("birth_year")

    if target_birth_year is None:
        return source_birth_year
    if source_birth_year is None:
        return target_birth_year
    if target_birth_year == source_birth_year:
        return target_birth_year

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Závodníci mají rozdílný rok narození, sloučení není bezpečné.",
    )


async def merge_athletes_service(source_athlete_id: str, target_athlete_id: str) -> dict:
    source_oid = _parse_oid(source_athlete_id, "source_athlete_id")
    target_oid = _parse_oid(target_athlete_id, "target_athlete_id")

    if source_oid == target_oid:
        raise HTTPException(
            status_code=400,
            detail="Source a target athlete musí být různí.",
        )

    source = normalize_athlete_document(
        await athletes_collection.find_one({"_id": source_oid})
    )
    target = normalize_athlete_document(
        await athletes_collection.find_one({"_id": target_oid})
    )

    if not source:
        raise HTTPException(status_code=404, detail="Source athlete not found")
    if not target:
        raise HTTPException(status_code=404, detail="Target athlete not found")
    if source.get("is_active") is False:
        raise HTTPException(status_code=409, detail="Source athlete už je neaktivní.")
    if target.get("is_active") is False:
        raise HTTPException(status_code=409, detail="Target athlete je neaktivní.")

    birth_year = _resolve_birth_year(target, source)
    merged_fs_codes = sorted(set((target.get("fs_codes") or []) + (source.get("fs_codes") or [])))
    merged_teams = sorted(
        set((target.get("teams") or []) + (source.get("teams") or [])),
        key=str.casefold,
    )

    moved_results_response = await results_collection.update_many(
        {"athlete": source_oid},
        {
            "$set": {
                "athlete": target_oid,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    await athletes_collection.update_one(
        {"_id": target_oid},
        {
            "$set": {
                "birth_year": birth_year,
                "fs_codes": merged_fs_codes,
                "teams": merged_teams,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    await athletes_collection.update_one(
        {"_id": source_oid},
        {
            "$set": {
                "is_active": False,
                "merged_into_athlete_id": str(target_oid),
                "updated_at": datetime.utcnow(),
                "merged_at": datetime.utcnow(),
            }
        },
    )

    await users_collection.update_many(
        {"athlete_id": str(source_oid)},
        {"$set": {"athlete_id": str(target_oid)}},
    )

    return {
        "ok": True,
        "source_athlete_id": source_athlete_id,
        "target_athlete_id": target_athlete_id,
        "moved_results": moved_results_response.modified_count,
    }


async def search_merge_candidates_service(
    athlete_id: str,
    q: Optional[str] = None,
    limit: int = 10,
) -> AthleteMergeCandidatesResponse:
    athlete_oid = _parse_oid(athlete_id, "athlete_id")
    athlete = normalize_athlete_document(
        await athletes_collection.find_one({"_id": athlete_oid})
    )
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    raw_query = (q or f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}").strip()
    if not raw_query:
        return AthleteMergeCandidatesResponse(items=[])

    tokens = [token for token in raw_query.split() if token]
    and_conditions = []
    for token in tokens:
        regex = build_diacritic_fuzzy_regex(token)
        and_conditions.append(
            {
                "$or": [
                    {"first_name": {"$regex": regex, "$options": "i"}},
                    {"last_name": {"$regex": regex, "$options": "i"}},
                ]
            }
        )

    query = active_athlete_query(
        {
            "_id": {"$ne": athlete_oid},
            "$and": and_conditions,
        }
    )
    candidates = (
        await athletes_collection.find(query)
        .sort([("last_name", 1), ("first_name", 1)])
        .limit(limit)
        .to_list(length=limit)
    )

    items: list[AthleteMergeCandidate] = []
    for candidate in candidates:
        normalized_candidate = normalize_athlete_document(candidate) or candidate
        result_count = await results_collection.count_documents({"athlete": candidate["_id"]})
        items.append(
            AthleteMergeCandidate(
                athlete_id=str(candidate["_id"]),
                first_name=normalized_candidate.get("first_name", ""),
                last_name=normalized_candidate.get("last_name", ""),
                birth_year=normalized_candidate.get("birth_year"),
                fs_codes=normalized_candidate.get("fs_codes", []),
                teams=normalized_candidate.get("teams", []),
                result_count=result_count,
            )
        )

    return AthleteMergeCandidatesResponse(items=items)
