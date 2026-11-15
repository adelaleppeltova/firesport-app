from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status
from pymongo.errors import DuplicateKeyError

from app.db.database import db
from app.models.admin import (
    AdminImportStats,
    AdminReviewItem,
    AdminReviewResponse,
    AdminReviewSummary,
    ReviewCandidatesResponse,
)
from app.models.result import ImportedAthleteData, MatchStatus
from app.services.athlete_identity import active_athlete_query, build_fs_code_query, identity_group
from app.services.athlete_merge import (
    merge_athletes_service,
    search_merge_candidates_service,
)
from app.services.athletes import search_athletes_service
from app.services.data_import import DataImporter
from app.services.external_identity import ExternalIdentity, ExternalIdentitySidecar, external_identities
from app.services.result_matching import decide_athlete_match, name_key

results_collection = db["results"]
athletes_collection = db["athletes"]
competitions_collection = db["competitions"]


REVIEW_STATUSES = [MatchStatus.needs_review.value, MatchStatus.unmatched.value]


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID") from exc


def _snapshot(doc: dict) -> dict:
    return {key: doc.get(key) for key in ("_id", "athlete", "match_status", "match_reason", "updated_at")}


def _manual_record(reason: str, admin_id: str | None, athlete_id: ObjectId | None) -> dict:
    return {"reason": reason, "admin_id": admin_id, "athlete_id": athlete_id, "at": datetime.now(UTC)}


async def _apply_result_assignment(
    doc: dict, athlete_oid: ObjectId, *, match_reason: str, admin_id: str | None,
) -> bool:
    record = _manual_record(match_reason, admin_id, athlete_oid)
    outcome = await results_collection.update_one(
        _snapshot(doc),
        {
            "$set": {
                "athlete": athlete_oid,
                "match_status": MatchStatus.matched.value,
                "match_reason": match_reason,
                "updated_at": record["at"],
            },
            "$push": {"manual_identity_history": record},
        },
    )
    return outcome.modified_count == 1


def _external_observation(doc: dict) -> ExternalIdentity | None:
    raw = doc.get("external_identity")
    return ExternalIdentity.model_validate(raw) if raw else None


def _group_key(doc: dict) -> str | None:
    imported = doc.get("imported_athlete") or {}
    fingerprint = identity_group(
        name_key(imported.get("first_name")), name_key(imported.get("last_name")),
        imported.get("birth_year"), imported.get("fscode"), doc.get("team"),
    )
    if fingerprint is None:
        return None
    external = _external_observation(doc)
    return sha256(json.dumps([fingerprint, external.key if external else None]).encode()).hexdigest()


async def _review_decision(doc: dict, *, include_variants: bool = False) -> dict:
    imported = ImportedAthleteData.model_validate(doc.get("imported_athlete") or {})
    return await decide_athlete_match(
        **imported.model_dump(), team=doc.get("team"),
        external_identity=_external_observation(doc), include_variants=include_variants,
    )


async def get_result_candidates(result_id: str) -> ReviewCandidatesResponse:
    doc = await results_collection.find_one({"_id": _oid(result_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")
    decision = await _review_decision(doc, include_variants=True)
    return ReviewCandidatesResponse(items=[
        {
            "athlete_id": str(candidate["profile"]["_id"]),
            "first_name": candidate["profile"].get("first_name") or "",
            "last_name": candidate["profile"].get("last_name") or "",
            "birth_year": candidate["profile"].get("birth_year"),
            "fs_codes": candidate["profile"]["fs_codes"],
            "teams": candidate["profile"]["teams"],
            **{key: candidate[key] for key in ("strong", "supporting", "conflicts")},
        }
        for candidate in decision["candidates"][:10]
    ])


async def verify_result_external_identity(
    result_id: str, athlete_id: str, provider: str, person_id: str, *, admin_id: str,
) -> dict:
    doc = await results_collection.find_one({"_id": _oid(result_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")
    observation = _external_observation(doc)
    athlete_oid = _oid(athlete_id)
    if (not observation or doc.get("athlete") != athlete_oid
            or (observation.provider, observation.person_id) != (provider, person_id)
            or not (doc.get("match_reason") or "").startswith("manual_admin_")):
        raise HTTPException(status_code=409, detail="Je třeba ručně potvrzený výsledek s externím ID ze zdroje.")
    if not await athletes_collection.find_one(active_athlete_query({"_id": athlete_oid})):
        raise HTTPException(status_code=409, detail="Profil už není aktivní.")
    try:
        await external_identities.insert_one({
            "_id": observation.key, **observation.model_dump(), "athlete_id": athlete_oid,
            "verified_from_result_id": doc["_id"], "verified_by": admin_id, "verified_at": datetime.now(UTC),
        })
    except DuplicateKeyError:
        existing = await external_identities.find_one({"_id": observation.key})
        if not existing or existing.get("athlete_id") != athlete_oid:
            raise HTTPException(status_code=409, detail="Tento externí identifikátor už patří jinému profilu.")
    return {"ok": True}


async def import_results_from_files(
    files: list[UploadFile], *, external_sidecar: ExternalIdentitySidecar | None = None,
) -> dict:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Je potřeba vybrat alespoň jeden JSON soubor.",
        )

    if external_sidecar and len(files) != 1:
        raise HTTPException(status_code=400, detail="Provenience se vztahuje k jedinému souboru s výsledky.")
    aggregated = AdminImportStats().model_dump()

    for file in files:
        if not file.filename or not file.filename.endswith(".json"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Všechny soubory musí být JSON (*.json)",
            )

        try:
            content = await file.read()
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Neplatný JSON formát v souboru {file.filename}",
            ) from exc

        importer = DataImporter()
        stats = await importer.import_from_dict(data, external_sidecar=external_sidecar)
        aggregated["files_processed"] += 1
        for key, value in stats.items():
            if key != "errors":
                aggregated[key] += value
        aggregated["errors"].extend(stats.get("errors", []))

    return aggregated


async def get_review_results() -> AdminReviewResponse:
    query = {
        "match_status": {
            "$in": [MatchStatus.needs_review.value, MatchStatus.unmatched.value]
        }
    }
    docs = (
        await results_collection.find(query)
        .sort("date", -1)
        .to_list(length=None)
    )

    competition_ids = {doc["competition"] for doc in docs if doc.get("competition")}
    names = {}
    if competition_ids:
        competitions = competitions_collection.find({"_id": {"$in": list(competition_ids)}}, {"name": 1})
        names = {doc["_id"]: doc.get("name") async for doc in competitions}

    items: list[AdminReviewItem] = []
    needs_review_count = 0
    unmatched_count = 0

    for doc in docs:
        status_value = doc.get("match_status", MatchStatus.unmatched.value)
        if status_value == MatchStatus.needs_review.value:
            needs_review_count += 1
        else:
            unmatched_count += 1

        imported = doc.get("imported_athlete") or {}

        items.append(
            AdminReviewItem(
                result_id=str(doc["_id"]),
                imported_athlete=ImportedAthleteData.model_validate(imported),
                match_status=status_value,
                match_reason=doc.get("match_reason"),
                team=doc.get("imported_team", doc.get("team")),
                date=doc.get("date").isoformat() if doc.get("date") else None,
                group_id=_group_key(doc),
                competition_name=names.get(doc.get("competition")),
                start_number=str(doc["start_number"]) if doc.get("start_number") is not None else None,
            )
        )

    return AdminReviewResponse(
        summary=AdminReviewSummary(
            total=len(items),
            needs_review=needs_review_count,
            unmatched=unmatched_count,
        ),
        items=items,
    )


async def assign_result_to_athlete(result_id: str, athlete_id: str, *, admin_id: str | None = None) -> dict:
    result_oid, athlete_oid = _oid(result_id), _oid(athlete_id)
    if not await athletes_collection.find_one(active_athlete_query({"_id": athlete_oid})):
        raise HTTPException(status_code=404, detail="Athlete not found")

    doc = await results_collection.find_one({"_id": result_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")
    if doc.get("athlete") or doc.get("match_status") not in REVIEW_STATUSES:
        raise HTTPException(status_code=409, detail="Výsledek už byl vyřešen.")
    if not await _apply_result_assignment(doc, athlete_oid, match_reason="manual_admin_assignment", admin_id=admin_id):
        raise HTTPException(status_code=409, detail="Výsledek byl mezitím změněn.")
    return {"ok": True, "result_id": result_id, "athlete_id": athlete_id, "auto_reassigned": 0}


async def assign_result_group(result_ids: list[str], athlete_id: str, *, admin_id: str) -> dict:
    ids, athlete_oid = [_oid(value) for value in result_ids], _oid(athlete_id)
    if len(set(ids)) != len(ids) or not 2 <= len(ids) <= 50:
        raise HTTPException(status_code=400, detail="Vyber 2 až 50 různých výsledků.")
    docs = await results_collection.find({"_id": {"$in": ids}}).to_list(len(ids))
    groups = {_group_key(doc) for doc in docs}
    if len(docs) != len(ids) or len(groups) != 1 or None in groups or any(
        doc.get("athlete") or doc.get("match_status") not in REVIEW_STATUSES
        or doc.get("match_reason") == "manual_admin_unassignment"
        for doc in docs
    ):
        raise HTTPException(status_code=409, detail="Vybrané výsledky nejsou ve stejné skupině ke kontrole.")
    # The grouping key includes every matching input, so this evidence applies to each selected row.
    decision = await _review_decision(docs[0])
    candidate = next((item for item in decision["candidates"] if item["profile"]["_id"] == athlete_oid), None)
    other_identifier_owner = any(
        item["profile"]["_id"] != athlete_oid and item["strong"] for item in decision["candidates"]
    )
    if (not candidate or candidate["conflicts"] or other_identifier_owner
            or "exact_name" not in candidate["supporting"]
            or not (candidate["strong"] or "birth_year" in candidate["supporting"])
            or decision["match_reason"] in ("candidate_limit", "inactive_external_identity", "unverified_external_id", "invalid_fscode")):
        raise HTTPException(status_code=409, detail="Rozpory nebo chybějící identifikace vyžadují jednotlivou kontrolu.")

    if not candidate["strong"] and len({doc.get("competition") for doc in docs}) != len(docs):
        raise HTTPException(status_code=409, detail="Bez potvrzeného kódu vybírej nejvýše jeden záznam na soutěž.")

    assigned, skipped = [], []
    for doc in docs:
        changed = await _apply_result_assignment(
            doc, athlete_oid, match_reason="manual_admin_bulk_assignment", admin_id=admin_id,
        )
        (assigned if changed else skipped).append(str(doc["_id"]))
    return {"assigned": assigned, "skipped": skipped}


async def create_athlete_from_result(result_id: str, *, admin_id: str | None = None) -> dict:
    try:
        result_oid = ObjectId(result_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid result_id") from exc

    result_doc = await results_collection.find_one({"_id": result_oid})
    if not result_doc:
        raise HTTPException(status_code=404, detail="Result not found")

    imported = result_doc.get("imported_athlete") or {}
    first_name = (imported.get("first_name") or "").strip()
    last_name = (imported.get("last_name") or "").strip()
    if not first_name or not last_name:
        raise HTTPException(
            status_code=400,
            detail="Importovaný záznam neobsahuje dost údajů pro vytvoření závodníka.",
        )

    if result_doc.get("athlete") or result_doc.get("match_status") not in REVIEW_STATUSES:
        raise HTTPException(status_code=409, detail="Výsledek už je přiřazen závodníkovi.")

    code_query = build_fs_code_query(imported.get("fscode"))
    if code_query and await athletes_collection.find_one(active_athlete_query(code_query)):
        raise HTTPException(status_code=409, detail="FSCode už patří aktivnímu závodníkovi.")

    team = result_doc.get("team")
    athlete_doc = {
        "first_name": first_name,
        "last_name": last_name,
        "birth_year": imported.get("birth_year"),
        "fs_codes": [imported.get("fscode")] if imported.get("fscode") else [],
        "teams": [team] if team else [],
        "is_active": True,
        "merged_into_athlete_id": None,
        "created_at": datetime.now(UTC),
    }

    insert_result = await athletes_collection.insert_one(athlete_doc)
    athlete_id = str(insert_result.inserted_id)

    if not await _apply_result_assignment(
        result_doc, insert_result.inserted_id, match_reason="manual_admin_create_athlete", admin_id=admin_id,
    ):
        raise HTTPException(status_code=409, detail="Výsledek byl mezitím změněn.")

    return {
        "ok": True,
        "result_id": result_id,
        "athlete_id": athlete_id,
        "auto_reassigned": 0,
    }


async def delete_review_results() -> dict:
    query = {
        "match_status": {
            "$in": [MatchStatus.needs_review.value, MatchStatus.unmatched.value]
        }
    }
    query.update({
        "athlete": None,
        "manual_identity_history": {"$exists": False},
        "match_reason": {"$not": {"$regex": "^manual_admin_"}},
        "external_identity": {"$exists": False},
    })
    result = await results_collection.delete_many(query)
    return {"ok": True, "deleted_count": result.deleted_count}


async def unassign_result_from_athlete(result_id: str, *, admin_id: str | None = None) -> dict:
    try:
        result_oid = ObjectId(result_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid result_id") from exc

    doc = await results_collection.find_one({"_id": result_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")

    if not doc.get("athlete"):
        raise HTTPException(status_code=409, detail="Výsledek už je bez přiřazení.")
    match = await _review_decision(doc)
    record = _manual_record("manual_admin_unassignment", admin_id, doc.get("athlete"))
    next_status = (
        MatchStatus.unmatched.value
        if match["match_status"] == MatchStatus.matched
        else match["match_status"].value
    )

    outcome = await results_collection.update_one(
        _snapshot(doc),
        {
            "$unset": {"athlete": ""},
            "$set": {
                "match_status": next_status,
                "match_reason": record["reason"],
                "updated_at": record["at"],
            },
            "$push": {"manual_identity_history": record},
        },
    )
    if outcome.modified_count != 1:
        raise HTTPException(status_code=409, detail="Výsledek byl mezitím změněn.")

    return {"ok": True, "result_id": result_id, "match_status": next_status}


async def search_athletes_for_admin(q: str):
    return await search_athletes_service(q)


async def search_merge_candidates_for_admin(athlete_id: str, q: str | None = None):
    return await search_merge_candidates_service(athlete_id=athlete_id, q=q)


async def merge_athletes_for_admin(source_athlete_id: str, target_athlete_id: str):
    return await merge_athletes_service(source_athlete_id, target_athlete_id)
