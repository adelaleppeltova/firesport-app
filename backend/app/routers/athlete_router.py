from typing import Dict, List
from fastapi import APIRouter, Query, HTTPException, Depends
from app.models.athlete import Athlete
from app.db.database import db
from app.dependencies import get_current_user
from bson import ObjectId

import logging


router = APIRouter(prefix="/athletes", tags=["athletes"])

athletes_collection = db["athletes"]
results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]

logger = logging.getLogger("firesport.overview")

@router.post("/")
async def create_athlete(athlete: Athlete):
    result = await athletes_collection.insert_one(athlete.dict())
    return {"id": str(result.inserted_id)}

def convert_objectids(doc):
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            doc[k] = str(v)
        elif isinstance(v, list):
            doc[k] = [str(i) if isinstance(i, ObjectId) else i for i in v]
        elif isinstance(v, dict):
            doc[k] = convert_objectids(v)
    return doc

@router.get("/")
async def list_athletes():
    athletes = await athletes_collection.find().to_list(length=None)
    for a in athletes:
        convert_objectids(a)
    return athletes

@router.get("/search")
async def search_athletes(q: str = Query(..., min_length=2)):
    """Vyhledá atlety podle jména, příjmení nebo FS kódu"""
    query = {
        "$or": [
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"fscode": {"$regex": q, "$options": "i"}}
        ]
    }
    athletes = await athletes_collection.find(query).to_list(length=20)
    for a in athletes:
        convert_objectids(a)
    return {"items": athletes}

@router.get("/{athlete_id}/overview")
async def get_athlete_overview(athlete_id: str, user=Depends(get_current_user)):
    """Vrátí přehled výkonů atleta (poslední aktivita, statistiky)"""
    logger.warning(f"[overview] athlete_id param: {athlete_id}")
    try:
        athlete_oid = ObjectId(athlete_id)
    except:
        logger.error(f"[overview] Invalid athlete_id: {athlete_id}")
        raise HTTPException(status_code=400, detail="Invalid athlete_id")
    
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    logger.warning(f"[overview] athlete from DB: {athlete}")
    if not athlete:
        logger.error(f"[overview] Athlete not found for id: {athlete_id}")
        raise HTTPException(status_code=404, detail="Athlete not found")
    
    results = await results_collection.find({"athlete_id": athlete_oid}).sort("rank", 1).to_list(length=None)
    logger.warning(f"[overview] results found: {len(results)}")
    if results:
        logger.warning(f"[overview] first result: {results[0]}")
    def to_str_id(val):
        if isinstance(val, ObjectId):
            return str(val)
        return val

    if not results:
        logger.warning(f"[overview] No results for athlete {athlete_id}")
        return {
            "athlete_id": str(athlete_id),
            "athlete_name": f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}".strip(),
            "athlete_team": athlete.get("team"),
            "category": None,
            "last_activity": None,
            "avg_time": None,
            "best_time": None,
            "competition_count": 0
        }

    best_result = results[0]

    # Join s competitions pro získání názvu a data
    competition_id = to_str_id(best_result.get("competition_id"))
    logger.warning(f"[overview] competition_id: {competition_id}")
    competition = await competitions_collection.find_one({"_id": best_result.get("competition_id")})
    logger.warning(f"[overview] competition from DB: {competition}")

    # Join s categories pro získání názvu kategorie (podpora category i category_id)
    category_id = to_str_id(best_result.get("category") or best_result.get("category_id"))
    category_name = None
    if category_id:
        try:
            cat_oid = ObjectId(category_id)
            category = await categories_collection.find_one({"_id": cat_oid})
            logger.warning(f"[overview] category from DB: {category}")
            category_name = category.get("category_name") if category else None
        except Exception:
            category_name = category_id 

    last_activity = {
        "competition_id": competition_id,
        "competition_name": competition.get("competition_name", "Neznámá soutěž") if competition else "Neznámá soutěž",
        "competition_date": competition.get("competition_date") if competition else None,
        "competition_place": competition.get("competition_place", "") if competition else "",
        "final_time": best_result.get("final_time", 0),
        "rank": best_result.get("rank", 0)
    }
    logger.warning(f"[overview] last_activity: {last_activity}")

    # Statistiky z výsledků
    times = [r.get("final_time", 0) for r in results if r.get("final_time")]
    avg_time = sum(times) / len(times) if times else None
    best_time = min(times) if times else None
    logger.warning(f"[overview] avg_time: {avg_time}, best_time: {best_time}")

    competition_count = await get_athlete_competition_count(athlete_oid)

    return {
        "athlete_id": str(athlete_id),
        "athlete_name": f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}".strip(),
        "athlete_team": athlete.get("team"),
        "category": category_name,
        "last_activity": last_activity,
        "avg_time": avg_time,
        "best_time": best_time,
        "competition_count": competition_count,
        "athlete_birth_year": athlete.get("birth_year")  
    }



@router.get("/{athlete_id}/detail")
async def get_athlete_detail(athlete_id: str):
    try:
        oid = ObjectId(athlete_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid athlete_id")
    athlete = await athletes_collection.find_one({"_id": oid})
    if not athlete:
        raise HTTPException(status_code=404, detail="Athlete not found")
    # Najdi všechny výsledky závodníka
    results = await results_collection.find({"athlete_id": oid}).sort("competition_date", 1).to_list(length=None)
    # Join s competitions
    rows = []
    best_time = None
    category = None
    for r in results:
        comp = None
        if r.get("competition_id"):
            comp = await competitions_collection.find_one({"_id": r["competition_id"]})
        date = comp["competition_date"].strftime("%d. %m. %Y") if comp and comp.get("competition_date") else "-"
        place = comp["competition_place"] if comp and comp.get("competition_place") else "-"
        final_time = r.get("final_time")
        if final_time is not None:
            if best_time is None or final_time < best_time:
                best_time = final_time
        # Kategorie z results (nově category_id)
        if not category and r.get("category_id"):
            cat_id = r["category_id"]
            try:
                cat_oid = ObjectId(cat_id) if not isinstance(cat_id, ObjectId) else cat_id
                cat = await categories_collection.find_one({"_id": cat_oid})
                if cat:
                    category = cat.get("category_name")
            except Exception:
                category = str(cat_id)
        rows.append({
            "_id": str(r["_id"]),
            "date": date,
            "place": place,
            "final_time": final_time
        })
    return {
        "athlete": {
            "first_name": athlete.get("first_name"),
            "last_name": athlete.get("last_name"),
            "birth_year": athlete.get("birth_year"),
            "team": athlete.get("team"),
            "fscode": athlete.get("fscode"),
            "category": category,
        },
        "best_time": best_time,
        "results": rows
    }


# Počet závodů atleta
async def get_athlete_competition_count(oid: ObjectId):
    """
    Vrátí počet unikátních závodů, kterých se atlet zúčastnil.

    Args:
        oid (ObjectId): ID atleta (MongoDB ObjectId)

    Returns:
        int: Počet unikátních závodů
    """
    results: List[Dict] = await results_collection.find({"athlete_id": oid}).to_list(length=None)
    competition_ids = set()
    for r in results:
        if r.get("competition_id"):
            competition_ids.add(r["competition_id"])
    competition_count = len(competition_ids)
    return competition_count
    