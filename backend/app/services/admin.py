from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from app.db.database import db
from app.models.admin import AdminReviewItem, AdminReviewResponse, AdminReviewSummary
from app.models.result import ImportedAthleteData, MatchStatus
from app.services.athlete_identity import normalize_athlete_document
from app.services.athlete_merge import (
    merge_athletes_service,
    search_merge_candidates_service,
)
from app.services.athletes import search_athletes_service
from app.services.data_import import DataImporter
from app.services.result_matching import build_match_enrichment_update, decide_athlete_match

results_collection = db["results"]
athletes_collection = db["athletes"]


async def _apply_result_assignment(
    result_oid: ObjectId,
    athlete_oid: ObjectId,
    *,
    match_reason: str,
) -> None:
    await results_collection.update_one(
        {"_id": result_oid},
        {
            "$set": {
                "athlete": athlete_oid,
                "match_status": MatchStatus.matched.value,
                "match_reason": match_reason,
                "updated_at": datetime.utcnow(),
            }
        },
    )


async def _enrich_athlete_from_result(athlete_oid: ObjectId, result_doc: dict) -> None:
    imported = result_doc.get("imported_athlete") or {}
    team = result_doc.get("team")

    athlete = normalize_athlete_document(
        await athletes_collection.find_one({"_id": athlete_oid})
    )
    if not athlete:
        return

    update_fields = {}
    add_to_set = {}
    if imported.get("birth_year") is not None and not athlete.get("birth_year"):
        update_fields["birth_year"] = imported.get("birth_year")
    if imported.get("fscode") is not None:
        add_to_set["fs_codes"] = imported.get("fscode")
    if team:
        add_to_set["teams"] = team

    update = {}
    if update_fields:
        update_fields["updated_at"] = datetime.utcnow()
        update["$set"] = update_fields
    elif add_to_set:
        update["$set"] = {"updated_at": datetime.utcnow()}
    if add_to_set:
        update["$addToSet"] = add_to_set

    if update:
        await athletes_collection.update_one({"_id": athlete_oid}, update)


async def _rematch_review_results() -> int:
    docs = await results_collection.find(
        {"match_status": {"$in": [MatchStatus.needs_review.value, MatchStatus.unmatched.value]}}
    ).to_list(length=None)

    reassigned = 0
    for doc in docs:
        imported = doc.get("imported_athlete") or {}
        decision = await decide_athlete_match(
            first_name=imported.get("first_name", ""),
            last_name=imported.get("last_name", ""),
            birth_year=imported.get("birth_year"),
            fscode=imported.get("fscode"),
            team=doc.get("team"),
        )
        matched_athlete = decision.get("matched_athlete")
        if decision["match_status"] != MatchStatus.matched or not matched_athlete:
            continue

        athlete_oid = (
            matched_athlete["_id"]
            if isinstance(matched_athlete.get("_id"), ObjectId)
            else ObjectId(str(matched_athlete["_id"]))
        )
        enrichment_update = build_match_enrichment_update(
            athlete=matched_athlete,
            imported_athlete=imported,
            team=doc.get("team"),
            match_reason=decision.get("match_reason"),
        )
        if enrichment_update:
            await athletes_collection.update_one({"_id": athlete_oid}, enrichment_update)
        await _apply_result_assignment(
            doc["_id"],
            athlete_oid,
            match_reason=f"auto_reassigned_{decision.get('match_reason', 'matched')}",
        )
        reassigned += 1

    return reassigned


async def import_results_from_files(files: list[UploadFile]) -> dict:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Je potřeba vybrat alespoň jeden JSON soubor.",
        )

    import json

    aggregated = {
        "files_processed": 0,
        "total_imported": 0,
        "review_required": 0,
        "athletes_created_new": 0,
        "athletes_existing_matched": 0,
        "categories_created": 0,
        "competitions_created": 0,
        "results_created": 0,
        "results_matched": 0,
        "results_needs_review": 0,
        "results_unmatched": 0,
        "errors": [],
    }

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
        stats = await importer.import_from_dict(data)
        aggregated["files_processed"] += 1
        for key in (
            "total_imported",
            "review_required",
            "athletes_created_new",
            "athletes_existing_matched",
            "categories_created",
            "competitions_created",
            "results_created",
            "results_matched",
            "results_needs_review",
            "results_unmatched",
        ):
            aggregated[key] += stats.get(key, 0)
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
                team=doc.get("team"),
                date=doc.get("date").isoformat() if doc.get("date") else None,
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


async def assign_result_to_athlete(result_id: str, athlete_id: str) -> dict:
    try:
        result_oid = ObjectId(result_id)
        athlete_oid = ObjectId(athlete_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID") from exc

    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    result_doc = await results_collection.find_one({"_id": result_oid})
    if not result_doc:
        raise HTTPException(status_code=404, detail="Result not found")

    await _enrich_athlete_from_result(athlete_oid, result_doc)
    await _apply_result_assignment(
        result_oid,
        athlete_oid,
        match_reason="manual_admin_assignment",
    )
    auto_reassigned = await _rematch_review_results()

    return {
        "ok": True,
        "result_id": result_id,
        "athlete_id": athlete_id,
        "auto_reassigned": auto_reassigned,
    }


async def create_athlete_from_result(result_id: str) -> dict:
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

    team = result_doc.get("team")
    athlete_doc = {
        "first_name": first_name,
        "last_name": last_name,
        "birth_year": imported.get("birth_year"),
        "fs_codes": [imported.get("fscode")] if imported.get("fscode") else [],
        "teams": [team] if team else [],
        "is_active": True,
        "merged_into_athlete_id": None,
        "created_at": datetime.utcnow(),
    }

    insert_result = await athletes_collection.insert_one(athlete_doc)
    athlete_id = str(insert_result.inserted_id)

    await _apply_result_assignment(
        result_oid,
        insert_result.inserted_id,
        match_reason="manual_admin_create_athlete",
    )
    auto_reassigned = await _rematch_review_results()

    return {
        "ok": True,
        "result_id": result_id,
        "athlete_id": athlete_id,
        "auto_reassigned": auto_reassigned,
    }


async def delete_review_results() -> dict:
    query = {
        "match_status": {
            "$in": [MatchStatus.needs_review.value, MatchStatus.unmatched.value]
        }
    }
    result = await results_collection.delete_many(query)
    return {"ok": True, "deleted_count": result.deleted_count}


async def unassign_result_from_athlete(result_id: str) -> dict:
    try:
        result_oid = ObjectId(result_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid result_id") from exc

    doc = await results_collection.find_one({"_id": result_oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Result not found")

    imported = doc.get("imported_athlete") or {}
    match = await decide_athlete_match(
        first_name=imported.get("first_name", ""),
        last_name=imported.get("last_name", ""),
        birth_year=imported.get("birth_year"),
        fscode=imported.get("fscode"),
        team=doc.get("team"),
    )
    next_status = (
        MatchStatus.unmatched.value
        if match["match_status"] == MatchStatus.matched
        else match["match_status"].value
    )

    await results_collection.update_one(
        {"_id": result_oid},
        {
            "$unset": {"athlete": ""},
            "$set": {
                "match_status": next_status,
                "match_reason": "manual_admin_unassignment",
                "updated_at": datetime.utcnow(),
            },
        },
    )

    return {"ok": True, "result_id": result_id, "match_status": next_status}


async def search_athletes_for_admin(q: str):
    return await search_athletes_service(q)


async def search_merge_candidates_for_admin(athlete_id: str, q: str | None = None):
    return await search_merge_candidates_service(athlete_id=athlete_id, q=q)


async def merge_athletes_for_admin(source_athlete_id: str, target_athlete_id: str):
    return await merge_athletes_service(source_athlete_id, target_athlete_id)
