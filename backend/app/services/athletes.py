from bson import ObjectId
from app.db.database import db
from app.models.athlete import AthleteInDB
from app.models.result import ResultInDB
from app.models.competition import CompetitionInDB
from app.models.category import CategoryInDB
from datetime import datetime
from typing import List, Dict


athletes_collection = db["athletes"]
results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]
async def list_athletes_service() -> List[AthleteInDB]:
    """Vrátí všechny atlety jako seznam Pydantic modelů."""
    athletes = await athletes_collection.find().to_list(length=1000)
    return [AthleteInDB(**a) for a in athletes]

async def get_athlete_overview_service(athlete_id: str) -> Dict:
    """Vrátí přehled výkonů atleta (poslední aktivita, statistiky)"""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")
    results = await results_collection.find({"athlete_id": athlete_oid}).sort("rank", 1).to_list(length=None)
    def to_str_id(val):
        if isinstance(val, ObjectId):
            return str(val)
        return val
    if not results:
        return {
            "athlete_id": str(athlete_id),
            "athlete_name": f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}".strip(),
            "athlete_team": athlete.get("team"),
            "category": None,
            "last_activity": None,
            "avg_time": None,
            "best_time": None,
            "competition_count": 0,
            "best_time_in_actual_year": None
        }
    best_result = results[0]
    competition_id = to_str_id(best_result.get("competition_id"))
    competition = await competitions_collection.find_one({"_id": best_result.get("competition_id")})
    category_id = to_str_id(best_result.get("category") or best_result.get("category_id"))
    category_name = None
    if category_id:
        try:
            cat_oid = ObjectId(category_id)
            category = await categories_collection.find_one({"_id": cat_oid})
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
    times = [r.get("final_time", 0) for r in results if r.get("final_time")]
    avg_time = sum(times) / len(times) if times else None
    best_time = min(times) if times else None
    competition_count = await get_athlete_competition_count(athlete_oid)
    best_time_in_year = await get_athlete_best_time_in_year(athlete_oid, datetime.now().year)
    average_time_in_year = await get_athlete_average_time_in_year(athlete_oid, datetime.now().year)
    return {
        "athlete_id": str(athlete_id),
        "athlete_name": f"{athlete.get('first_name', '')} {athlete.get('last_name', '')}".strip(),
        "athlete_team": athlete.get("team"),
        "category": category_name,
        "last_activity": last_activity,
        "avg_time": avg_time,
        "best_time": best_time,
        "competition_count": competition_count,
        "athlete_birth_year": athlete.get("birth_year"),
        "best_time_in_year": best_time_in_year,
        "average_time_in_year": average_time_in_year
    }

async def get_athlete_detail_service(athlete_id: str) -> Dict:
    from bson import ObjectId
    try:
        oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    athlete = await athletes_collection.find_one({"_id": oid})
    if not athlete:
        raise ValueError("Athlete not found")
    results = await results_collection.find({"athlete_id": oid}).sort("competition_date", 1).to_list(length=None)
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


async def search_athletes_service(q: str) -> dict:
    query = {
        "$or": [
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"fscode": {"$regex": q, "$options": "i"}}
        ]
    }
    athletes = await athletes_collection.find(query).to_list(length=20)
    # Validace pomocí Pydantic modelu (Athlete)
    result = {"items": [AthleteInDB(**a) for a in athletes]}
    return result




results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]
athletes_collection = db["athletes"]




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

# Získání soutěží v daném roce
async def get_competitions_in_year(oid: ObjectId, year:int):
    """
    Vrátí seznam soutěží, kterých se atlet zúčastnil v daném roce.

    Args:
        oid (ObjectId): ID atleta (MongoDB ObjectId)
        year (int): Rok pro filtraci výsledků"""
    start_of_year = datetime(year, 1, 1)
    end_of_year = datetime(year, 12, 31, 23, 59, 59)

    competitions_in_year = await competitions_collection.find({
        "competition_date": {"$gte": start_of_year, "$lte": end_of_year}
    }).to_list(length=None)
    competition_ids = [c["_id"] for c in competitions_in_year]
    if not competition_ids:
        return None

    return competition_ids


# Získání nejlepšího času atleta v daném roce
async def get_athlete_best_time_in_year(oid: ObjectId, year: int):
    """
    Vrátí nejlepší čas atleta v daném roce.

    Args:
        oid (ObjectId): ID atleta (MongoDB ObjectId)
        year (int): Rok pro filtraci výsledků

    Returns:
        float | None: Nejlepší čas v sekundách nebo None, pokud nejsou výsledky
    """

    results: List[Dict] = await results_collection.find({
        "athlete_id": oid,
        "competition_id": {"$in": await get_competitions_in_year(oid, year)},
        "final_time": {"$ne": None}
    }).to_list(length=None)

    if not results:
        return None

    return min(r["final_time"] for r in results if r.get("final_time") is not None)


# Získání průměrného času atleta v daném roce
async def get_athlete_average_time_in_year(oid: ObjectId, year: int):
    """
    Vrátí průměrný čas atleta v daném roce.
    Args:
        oid (ObjectId): ID atleta (MongoDB ObjectId)
        year (int): Rok pro filtraci výsledků  
    Returns:
        float | None: Průměrný čas v sekundách nebo None, pokud nejsou výsledky
    """

    results: List[Dict] = await results_collection.find({
        "athlete_id": oid,
        "competition_id": {"$in": await get_competitions_in_year(oid, year)},
        "final_time": {"$ne": None}
    }).to_list(length=None)

    if not results:
        return None

    times = [r["final_time"] for r in results if r.get("final_time") is not None]
    if not times:
        return None

    return sum(times) / len(times)