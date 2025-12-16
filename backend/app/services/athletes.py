from bson import ObjectId
from app.db.database import db
from app.models.athlete import AthleteInDB, AthletesSearch, AthleteOverview, AthleteDetail, PerformanceTrend, RecentResult
from app.models.result import ResultBase
from datetime import datetime
from typing import List, Dict
from ml.utils.trend_analyzer import analyze_performance_trend, get_recent_results_from_times
from ml.utils.stability_evaluator import get_stability_analysis

from app.models.models import AthleteDetailPage



athletes_collection = db["athletes"]
results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]


async def list_athletes_service() -> List[AthleteInDB]:
    """Vrátí všechny atlety jako seznam Pydantic modelů."""
    athletes = await athletes_collection.find().to_list(length=1000)
    for a in athletes:
        a["_id"] = str(a["_id"])
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
    
    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)

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
            performance_trend=PerformanceTrend.stable,
            recent_results=[],
            performance_variability=None,
            stability_rating="Nedostatek dat",
        )
    
    times = [r.get("final_time") for r in results if r.get("final_time") is not None]
    average_time = sum(times) / len(times) if times else None
    best_time = min(times) if times else None

    #Počet soutěží
    total_competitions = await get_athlete_competition_count(athlete_oid)

    # Poslední aktivita
    latest_date = None
    for r in results:
        comp = None
        if r.get("competition"):
            comp = await competitions_collection.find_one({"_id": r["competition"]})
        comp_date = comp.get("date") if comp else None
        if comp_date:
            if latest_date is None or comp_date > latest_date:
                latest_date = comp_date

    if latest_date:
        last_active = latest_date.strftime("%d. %m. %Y")
    else:
        last_active = None

    # Výkon v aktuálním roce
    current_year = datetime.now().year
    best_time_in_year = await get_athlete_best_time_in_year(athlete_oid, current_year)
    average_time_in_year = await get_athlete_average_time_in_year(athlete_oid, current_year)

    # Trend výkonu - seřazení podle času (nejstarší první)
    sorted_results = sorted(results, key=lambda r: r.get("final_time") or float('inf'))
    times_sorted = [r.get("final_time") for r in sorted_results if r.get("final_time") is not None]
    ranks_sorted = [r.get("rank") for r in sorted_results if r.get("rank") is not None]
    
    performance_trend = analyze_performance_trend(times_sorted)
    recent_results = get_recent_results_from_times(times_sorted[-5:] if len(times_sorted) > 5 else times_sorted, 
                                       ranks_sorted[-5:] if len(ranks_sorted) > 5 else ranks_sorted)

    # Stabilita výkonu v aktuálním roce
    current_year = datetime.now().year
    year_results = [
        r.get("final_time")
        for r in results
        if r.get("final_time") is not None
    ]
    
    stability_info = get_stability_analysis(year_results)
    performance_variability = stability_info["stats"]["std_dev"]
    stability_rating = stability_info["rating"]

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
        performance_trend=performance_trend,
        recent_results=recent_results,
        performance_variability=performance_variability,
        stability_rating=stability_rating,
        )


async def get_athlete_detail_service(athlete_id: str) -> AthleteDetailPage:

    """Vrátí detail atleta jako AthleteDetail."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")
    
    results_raw = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)

    # prepare athlete payload
    athlete_payload = dict(athlete)
    athlete_payload["_id"] = str(athlete_payload.get("_id"))

    results: list = []
    best_time: float | None = None
    category_name: str | None = None

    for r in results_raw:
        # compute best_time
        final_time = r.get("final_time")
        if final_time is not None:
            if best_time is None or final_time < best_time:
                best_time = final_time

        # resolve competition
        comp_payload = None
        if r.get("competition"):
            c_val = r["competition"]
            try:
                c_oid = c_val if isinstance(c_val, ObjectId) else ObjectId(str(c_val))
            except Exception:
                raise ValueError("Invalid competition reference")
            c_doc = await competitions_collection.find_one({"_id": c_oid})
            if not c_doc:
                raise ValueError("Referenced competition not found")
            comp_payload = dict(c_doc)
            comp_payload["_id"] = str(comp_payload.get("_id"))
            # normalize categories
            cats = comp_payload.get("categories")
            if isinstance(cats, list):
                comp_payload["categories"] = [str(x) for x in cats]

        # resolve category
        cat_payload = None
        if r.get("category"):
            cat_val = r["category"]
            try:
                cat_oid = cat_val if isinstance(cat_val, ObjectId) else ObjectId(str(cat_val))
            except Exception:
                raise ValueError("Invalid category reference")
            cat_doc = await categories_collection.find_one({"_id": cat_oid})
            if not cat_doc:
                raise ValueError("Referenced category not found")
            cat_payload = dict(cat_doc)
            cat_payload["_id"] = str(cat_payload.get("_id"))
            if category_name is None:
                category_name = cat_payload.get("name")

        # build result payload matching ResultBase
        result_payload = {
            "athlete": athlete_payload,
            "competition": comp_payload,
            "category": cat_payload,
            "start_number": r.get("start_number"),
            "time_1": r.get("time_1"),
            "time_1_status": r.get("time_1_status"),
            "time_2": r.get("time_2"),
            "time_2_status": r.get("time_2_status"),
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
        }

        # validate as ResultBase and append
        validated = ResultBase.model_validate(result_payload)
        results.append(validated)

    # build AthleteDetail for response
    athlete_detail = AthleteDetail(
        id=str(athlete_payload["_id"]),
        first_name=athlete.get("first_name"),
        last_name=athlete.get("last_name"),
        birth_year=athlete.get("birth_year"),
        fscode=athlete.get("fscode"),
        team=athlete.get("team"),
        category=category_name,
        best_time=best_time,
    )
    return AthleteDetailPage(
        athlete=athlete_detail,
        results=results,
        best_time=best_time
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
    for a in athletes:
        a["_id"] = str(a["_id"])
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
    results: List[Dict] = await results_collection.find({"athlete": oid}).to_list(length=None)
    competition_ids = set()
    for r in results:
        if r.get("competition"):
            competition_ids.add(r["competition"])
    competition_count = len(competition_ids)
    return competition_count

# Získání soutěží v daném roceß
async def get_competitions_in_year(oid: ObjectId, year:int):
    """
    Vrátí seznam soutěží, kterých se atlet zúčastnil v daném roce.

    Args:
        oid (ObjectId): ID atleta (MongoDB ObjectId)
        year (int): Rok pro filtraci výsledků"""
    start_of_year = datetime(year, 1, 1)
    end_of_year = datetime(year, 12, 31, 23, 59, 59)

    competitions_in_year = await competitions_collection.find({
        "date": {"$gte": start_of_year, "$lte": end_of_year}
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
        "athlete": oid,
        "competition": {"$in": await get_competitions_in_year(oid, year)},
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
        "athlete": oid,
        "competition": {"$in": await get_competitions_in_year(oid, year)},
        "final_time": {"$ne": None}
    }).to_list(length=None)

    if not results:
        return None

    times = [r["final_time"] for r in results if r.get("final_time") is not None]
    if not times:
        return None

    return sum(times) / len(times)