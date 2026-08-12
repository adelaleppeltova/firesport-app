from typing import List, Dict, Any
from bson import ObjectId
import logging

from app.db.database import db
from app.models.result import ResultInDB

results_collection = db["results"]
athletes_collection = db["athletes"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]

logger = logging.getLogger(__name__)


PUBLIC_RESULTS_FILTER = {
    "$or": [
        {"match_status": "matched"},
        {"match_status": {"$exists": False}},
    ]
}


def _build_results_query(
    athlete_id: str | None = None,
    competition_id: str | None = None,
    category_id: str | None = None,
) -> Dict[str, Any]:
    """
    Složí Mongo query podle dostupných filtrů.
    """
    query: Dict[str, Any] = {}

    if athlete_id is not None:
        try:
            query["athlete"] = ObjectId(athlete_id)
        except Exception:
            raise ValueError("Invalid athlete_id")

    if competition_id is not None:
        try:
            query["competition"] = ObjectId(competition_id)
        except Exception:
            raise ValueError("Invalid competition_id")

    if category_id is not None:
        try:
            query["category"] = ObjectId(category_id)
        except Exception:
            raise ValueError("Invalid category_id")

    return query


async def get_result_detail_service(result_id: str) -> ResultInDB:
    """
    Vrátí jeden výsledek podle jeho ID jako ResultInDB.
    """
    try:
        oid = ObjectId(result_id)
    except Exception:
        raise ValueError("Invalid result_id")

    doc = await results_collection.find_one({"_id": oid})
    if not doc:
        raise ValueError("Result not found")

    # načteme referencované dokumenty (athlete, competition, category)
    # očekáváme, že v DB jsou reference uložené jako ObjectId
    athlete_doc = None
    competition_doc = None
    category_doc = None

    if doc.get("athlete") is not None:
        a_val = doc["athlete"]
        logger.debug("athlete reference raw value=%r type=%s", a_val, type(a_val))
        try:
            a_oid = a_val if isinstance(a_val, ObjectId) else ObjectId(str(a_val))
        except Exception:
                logger.exception("Invalid athlete reference: %r", a_val)
                raise ValueError("Invalid athlete reference")
        athlete_doc = await athletes_collection.find_one({"_id": a_oid})
        if not athlete_doc:
                logger.error("Referenced athlete not found for id=%s", a_oid)
                raise ValueError("Referenced athlete not found")

    if doc.get("competition") is not None:
        c_val = doc["competition"]
        logger.debug("competition reference raw value=%r type=%s", c_val, type(c_val))
        try:
            c_oid = c_val if isinstance(c_val, ObjectId) else ObjectId(str(c_val))
        except Exception:
                logger.exception("Invalid competition reference: %r", c_val)
                raise ValueError("Invalid competition reference")
        competition_doc = await competitions_collection.find_one({"_id": c_oid})
        if not competition_doc:
                logger.error("Referenced competition not found for id=%s", c_oid)
                raise ValueError("Referenced competition not found")

    if doc.get("category") is not None:
        cat_val = doc["category"]
        logger.debug("category reference raw value=%r type=%s", cat_val, type(cat_val))
        try:
            cat_oid = cat_val if isinstance(cat_val, ObjectId) else ObjectId(str(cat_val))
        except Exception:
                logger.exception("Invalid category reference: %r", cat_val)
                raise ValueError("Invalid category reference")
        category_doc = await categories_collection.find_one({"_id": cat_oid})
        if not category_doc:
                logger.error("Referenced category not found for id=%s", cat_oid)
                raise ValueError("Referenced category not found")

    # připravíme dokument ve tvaru očekávaném pydantic modelem
    out = dict(doc)
    # objektové ID pro _id převedeme na string
    out["_id"] = str(out["_id"])

    # nahradíme reference embedovanými dokumenty jako slovníky s _id jako string
    if athlete_doc is not None:
        a_payload = dict(athlete_doc)
        a_payload["_id"] = str(a_payload.get("_id"))
        out["athlete"] = a_payload
        logger.debug("Embedded athlete payload=%s", a_payload)
    if competition_doc is not None:
        c_payload = dict(competition_doc)
        c_payload["_id"] = str(c_payload.get("_id"))
        # normalize categories inside competition to list[str]
        cats = c_payload.get("categories")
        if isinstance(cats, list):
            c_payload["categories"] = [str(x) for x in cats]
        out["competition"] = c_payload
        logger.debug("Embedded competition payload=%s", c_payload)
    if category_doc is not None:
        cat_payload = dict(category_doc)
        cat_payload["_id"] = str(cat_payload.get("_id"))
        out["category"] = cat_payload
        logger.debug("Embedded category payload=%s", cat_payload)

    return ResultInDB.model_validate(out)


async def list_results_service(
    athlete_id: str | None = None,
    competition_id: str | None = None,
    category_id: str | None = None,
    limit: int = 1000,
) -> List[ResultInDB]:
    """
    Vrátí seznam výsledků jako ResultInDB, volitelně filtrováno
    podle atleta / soutěže / kategorie.
    """
    query = _build_results_query(
        athlete_id=athlete_id,
        competition_id=competition_id,
        category_id=category_id,
    )
    query.update(PUBLIC_RESULTS_FILTER)

    cursor = results_collection.find(query).limit(limit)
    docs = await cursor.to_list(length=limit)

    results: list[ResultInDB] = []
    for d in docs:
        out = dict(d)
        out["_id"] = str(out["_id"])

        # Resolve athlete
        if d.get("athlete") is not None:
            a_val = d["athlete"]
            try:
                a_oid = a_val if isinstance(a_val, ObjectId) else ObjectId(str(a_val))
            except Exception:
                raise ValueError("Invalid athlete reference")
            a_doc = await athletes_collection.find_one({"_id": a_oid})
            if not a_doc:
                raise ValueError("Referenced athlete not found")
            a_payload = dict(a_doc)
            a_payload["_id"] = str(a_payload.get("_id"))
            out["athlete"] = a_payload

        # Resolve competition
        if d.get("competition") is not None:
            c_val = d["competition"]
            try:
                c_oid = c_val if isinstance(c_val, ObjectId) else ObjectId(str(c_val))
            except Exception:
                raise ValueError("Invalid competition reference")
            c_doc = await competitions_collection.find_one({"_id": c_oid})
            if not c_doc:
                raise ValueError("Referenced competition not found")
            c_payload = dict(c_doc)
            c_payload["_id"] = str(c_payload.get("_id"))
            out["competition"] = c_payload

        # Resolve category
        if d.get("category") is not None:
            cat_val = d["category"]
            try:
                cat_oid = cat_val if isinstance(cat_val, ObjectId) else ObjectId(str(cat_val))
            except Exception:
                raise ValueError("Invalid category reference")
            cat_doc = await categories_collection.find_one({"_id": cat_oid})
            if not cat_doc:
                raise ValueError("Referenced category not found")
            cat_payload = dict(cat_doc)
            cat_payload["_id"] = str(cat_payload.get("_id"))
            out["category"] = cat_payload

        results.append(ResultInDB.model_validate(out))

    return results
