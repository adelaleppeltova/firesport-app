from bson import ObjectId
from app.db.database import db
from app.models.athlete import AthleteInDB, AthletesSearch, AthleteOverview, AthleteDetail, AthleteDetailAthlete, AthleteResultRow
from datetime import datetime
from typing import List, Dict



athletes_collection = db["athletes"]
results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]


async def list_athletes_service() -> List[AthleteInDB]:
    """Vrátí všechny atlety jako seznam Pydantic modelů."""
    athletes = await athletes_collection.find().to_list(length=1000)
    return [AthleteInDB.model_validate(a) for a in athletes]

async def get_athlete_overview_service(athlete_id: str) -> AthleteOverview:
    """Vrátí přehled výkonů atleta jako AthleteOverview."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")
    
    results = await results_collection.find({"athlete_id": athlete_oid}).to_list(length=None)

    if not results:
        return AthleteOverview(
            id=str(athlete["_id"]),
            first_name=athlete.get("first_name", ""),
            last_name=athlete.get("last_name", ""),
            birth_year=athlete.get("birth_year"),
            team=athlete.get("team"),
            last_active=None,
            total_competitions=0,
            best_time=None,
            average_time=None,
            best_time_in_year=None,
            average_time_in_year=None,
        )
    
    times = [r.get("final_time") for r in results if r.get("final_time") is not None]
    average_time = sum(times) / len(times) if times else None
    best_time = min(times) if times else None

    #Počet soutěží
    total_competitions = await get_athlete_competition_count(athlete_oid)

    # Poslední aktivita
    latest_competition_date = None
    for r in results:
        comp = None
        if r.get("competition_id"):
            comp = await competitions_collection.find_one({"_id": r["competition_id"]})
        comp_date = comp.get("competition_date") if comp else None
        if comp_date:
            if latest_competition_date is None or comp_date > latest_competition_date:
                latest_competition_date = comp_date

    if latest_competition_date:
        last_active = latest_competition_date.strftime("%d. %m. %Y")
    else:
        last_active = None

    # Výkon v aktuálním roce
    current_year = datetime.now().year
    best_time_in_year = await get_athlete_best_time_in_year(athlete_oid, current_year)
    average_time_in_year = await get_athlete_average_time_in_year(athlete_oid, current_year)

    return AthleteOverview(
        id=str(athlete["_id"]),
        first_name=athlete.get("first_name"),
        last_name=athlete.get("last_name"),
        birth_year=athlete.get("birth_year"),
        team=athlete.get("team"),
        last_active=last_active,
        total_competitions=total_competitions,
        best_time=best_time,
        average_time=average_time,
        best_time_in_year=best_time_in_year,
        average_time_in_year=average_time_in_year,
        )


async def get_athlete_detail_service(athlete_id: str) -> AthleteDetail:

    """Vrátí detail atleta jako AthleteDetail."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")
    
    results = await results_collection.find({"athlete_id": athlete_oid}).sort("competition_date", 1).to_list(length=None)

    rows: list[AthleteResultRow] = []
    best_time: float | None = None
    category_name: str | None = None

    for r in results:
        comp = None
        if r.get("competition_id"):
            comp = await competitions_collection.find_one({"_id": r["competition_id"]})
        
        competition_id = str(r.get("competition_id")) if r.get("competition_id") else ""
        competition_name = comp.get("competition_name") if comp and comp.get("competition_name") else "Neznámá soutěž"
        competition_date = (comp["competition_date"].strftime("%d. %m. %Y")
                            if comp and comp.get("competition_date") else "-")

        competition_place = comp.get("competition_place") if comp and comp.get("competition_place") else "-"

        final_time = r.get("final_time")
        rank = r.get("rank")

        # nejlepší čas
        if final_time is not None:
            if best_time is None or final_time < best_time:
                best_time = final_time

        # kategorie
        if category_name is None and r.get("category_id"):
            cat_id = r["category_id"]
            try:
                cat_oid = ObjectId(cat_id) if not isinstance(cat_id, ObjectId) else cat_id
                cat = await categories_collection.find_one({"_id": cat_oid})
                if cat:
                    category_name = cat.get("category_name")
            except Exception:
                category_name = str(cat_id)

        row = AthleteResultRow(
            competition_id=competition_id,
            competition_name=competition_name,
            competition_date=competition_date,
            competition_place=competition_place,
            final_time=final_time,
            rank=rank
        )
        rows.append(row)

    athlete_detail_athlete = AthleteDetailAthlete(
        id=str(athlete["_id"]),
        first_name=athlete.get("first_name"),
        last_name=athlete.get("last_name"),
        birth_year=athlete.get("birth_year"),
        fscode=athlete.get("fscode"),
        team=athlete.get("team"),
        category=category_name
    )

    return AthleteDetail(
        athlete=athlete_detail_athlete,
        best_time=best_time,
        results=rows
    )


async def search_athletes_service(q: str) -> AthletesSearch:
    query = {
        "$or": [
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            {"fscode": {"$regex": q, "$options": "i"}}
        ]
    }
    athletes = await athletes_collection.find(query).to_list(length=20)
    # Validace pomocí Pydantic modelu (Athlete)
    items = [AthleteInDB.model_validate(a) for a in athletes]
    return AthletesSearch(items=items)


# Počet závodů atleta
async def get_athlete_competition_count(oid: ObjectId) -> int:
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

    times = [r["final_time"] for r in results if r.get("final_time") is not None]
    if not times:
        return None

    return min(times)


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