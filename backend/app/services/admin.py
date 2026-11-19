from __future__ import annotations

from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException, UploadFile, status

from app.category_catalog import active_results
from app.db.database import db
from app.models.admin import AdminImportStats, AdminReviewItem, AdminReviewResponse, AdminReviewSummary, AdminSourceNameDetail
from app.models.result import ImportedAthleteData, MatchStatus
from app.person_names import NAME_FIELDS, missing_name, name_issues
from app.services.athlete_identity import active_athlete_query, build_fs_code_query
from app.services.athlete_merge import (
    merge_athletes_service,
    search_merge_candidates_service,
)
from app.services.athletes import search_athletes_service
from app.services.data_import import DataImporter
from app.services.result_matching import build_name_candidate_query, decide_athlete_match, normalize_person_name

results_collection = db["results"]
athletes_collection = db["athletes"]


def _assignment_fields(athlete_oid: ObjectId, reason: str) -> dict:
    return {
        "athlete": athlete_oid,
        "match_status": MatchStatus.matched.value,
        "match_reason": reason,
        "updated_at": datetime.utcnow(),
    }


async def _apply_result_assignment(
    result_oid: ObjectId, athlete_oid: ObjectId, *, match_reason: str
) -> None:
    await results_collection.update_one(
        {"_id": result_oid},
        {"$set": _assignment_fields(athlete_oid, match_reason)},
    )


async def _rematch_review_results(athlete: dict) -> int:
    review_query = {
        **active_results(individual=True),
        "match_status": {"$in": [MatchStatus.needs_review.value, MatchStatus.unmatched.value]},
        "athlete": None,
        "match_reason": {"$not": {"$regex": "^manual_admin_"}},
    }
    first_name = normalize_person_name(athlete.get("first_name"))
    last_name = normalize_person_name(athlete.get("last_name"))
    if not first_name or not last_name:
        return 0

    docs = results_collection.find({
        **review_query,
        "imported_athlete.first_name": build_name_candidate_query(first_name),
        "imported_athlete.last_name": build_name_candidate_query(last_name),
    })

    reassigned = 0
    async for doc in docs:
        imported = doc.get("imported_athlete") or {}
        decision = await decide_athlete_match(
            first_name=imported.get("first_name", ""),
            last_name=imported.get("last_name", ""),
            birth_year=imported.get("birth_year"),
            fscode=imported.get("fscode"),
            team=doc.get("team"),
        )
        matched_athlete = decision.get("matched_athlete")
        if not matched_athlete or matched_athlete["_id"] != athlete["_id"]:
            continue

        outcome = await results_collection.update_one(
            {"_id": doc["_id"], **review_query},
            {"$set": _assignment_fields(athlete["_id"], f"auto_reassigned_{decision['match_reason']}")},
        )
        reassigned += outcome.modified_count

    return reassigned


async def import_results_from_files(files: list[UploadFile]) -> dict:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Je potřeba vybrat alespoň jeden JSON soubor.",
        )

    import json

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
        stats = await importer.import_from_dict(data)
        aggregated["files_processed"] += 1
        for key, value in stats.items():
            if key != "errors":
                aggregated[key] += value
        aggregated["errors"].extend(stats.get("errors", []))

    return aggregated


async def get_review_results() -> AdminReviewResponse:
    query = {
        **active_results(individual=True),
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
        imported = doc.get("imported_athlete") or {}
        incomplete = missing_name(imported)
        source_name = doc.get("source_full_name")
        reason = ("name_segmentation_review" if source_name else "missing_name") if incomplete else doc.get("match_reason")
        status_value = MatchStatus.needs_review.value if incomplete else doc.get("match_status", MatchStatus.unmatched.value)
        if status_value == MatchStatus.needs_review.value:
            needs_review_count += 1
        else:
            unmatched_count += 1

        items.append(
            AdminReviewItem(
                result_id=str(doc["_id"]),
                imported_athlete=ImportedAthleteData.model_validate(imported),
                match_status=status_value,
                match_reason=reason,
                source_full_name=source_name,
                name_issues=name_issues(imported),
                source_person_name=doc.get("source_person_name") or {field: imported.get(field) for field in NAME_FIELDS},
                source_url=(doc.get("source_category") or {}).get("source_url"),
                team=doc.get("imported_team", doc.get("team")),
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


async def get_source_name_detail(result_id: str) -> AdminSourceNameDetail:
    if not ObjectId.is_valid(result_id):
        raise HTTPException(status_code=400, detail="Neplatné ID výsledku.")
    row = await results_collection.find_one(
        {"_id": ObjectId(result_id), "source_full_name": {"$type": "string"}},
        {"classification_status": 1, "imported_athlete": 1, "source_full_name": 1,
         "source_name_evidence.segmentation": 1},
    )
    if not row:
        raise HTTPException(status_code=404, detail="Výsledek se zdrojovým jménem nebyl nalezen.")
    return AdminSourceNameDetail(
        result_id=result_id, classification_status=row.get("classification_status"),
        imported_athlete=ImportedAthleteData.model_validate(row.get("imported_athlete") or {}),
        source_full_name=row["source_full_name"],
        segmentation=(row.get("source_name_evidence") or {}).get("segmentation"),
    )


async def get_category_review(page: int, page_size: int) -> dict:
    query = {"classification_status": {"$in": ["review", "unsupported"]}}
    cursor = results_collection.find(query, {
        "competition": 1, "source_category": 1, "classification_reason": 1,
        "classification_status": 1, "date": 1, "rank": 1,
    }).sort("_id", 1).skip((page - 1) * page_size).limit(page_size)
    documents = await cursor.to_list(page_size)
    items = []
    for document in documents:
        source = document.get("source_category") or {}
        items.append({
            "result_id": str(document["_id"]),
            "competition_id": str(document["competition"]) if document.get("competition") else None,
            "date": document.get("date"),
            "rank": document.get("rank"),
            "category": source.get("name"),
            "discipline": source.get("discipline"),
            "source_url": source.get("source_url"),
            "status": document["classification_status"],
            "reason": document.get("classification_reason"),
        })
    return {"total": await results_collection.count_documents(query), "items": items}


async def assign_result_to_athlete(result_id: str, athlete_id: str) -> dict:
    try:
        result_oid = ObjectId(result_id)
        athlete_oid = ObjectId(athlete_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid ID") from exc

    athlete = await athletes_collection.find_one(active_athlete_query({"_id": athlete_oid}))
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")

    result_doc = await results_collection.find_one({"_id": result_oid, **active_results(individual=True)})
    if not result_doc:
        raise HTTPException(status_code=404, detail="Result not found")

    await _apply_result_assignment(
        result_oid,
        athlete_oid,
        match_reason="manual_admin_assignment",
    )
    auto_reassigned = await _rematch_review_results(athlete)

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

    result_doc = await results_collection.find_one({"_id": result_oid, **active_results(individual=True)})
    if not result_doc:
        raise HTTPException(status_code=404, detail="Result not found")

    imported = result_doc.get("imported_athlete") or {}
    first_name = normalize_person_name(imported.get("first_name"))
    last_name = normalize_person_name(imported.get("last_name"))
    if not first_name or not last_name:
        raise HTTPException(
            status_code=400,
            detail="Importovaný záznam neobsahuje dost údajů pro vytvoření závodníka.",
        )

    if result_doc.get("athlete"):
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
        "created_at": datetime.utcnow(),
    }

    insert_result = await athletes_collection.insert_one(athlete_doc)
    athlete_id = str(insert_result.inserted_id)

    await _apply_result_assignment(
        result_oid,
        insert_result.inserted_id,
        match_reason="manual_admin_create_athlete",
    )
    auto_reassigned = await _rematch_review_results({**athlete_doc, "_id": insert_result.inserted_id})

    return {
        "ok": True,
        "result_id": result_id,
        "athlete_id": athlete_id,
        "auto_reassigned": auto_reassigned,
    }


async def delete_review_results() -> dict:
    query = {
        **active_results(individual=True),
        "imported_athlete.first_name": {"$regex": r"\S"},
        "imported_athlete.last_name": {"$regex": r"\S"},
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

    doc = await results_collection.find_one({"_id": result_oid, **active_results(individual=True)})
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
