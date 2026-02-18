from bson import ObjectId
from app.db.database import db
from app.models.athlete import AthleteInDB, AthletesSearch, AthleteOverview, AthleteDetail, BestPerformance
from app.models.result import ResultBase
from datetime import datetime
from typing import List, Dict

from app.models.models import AthleteDetailPage
from app.services.performance_indicator import calculate_performance_indicator
from app.services.performance_stability_service import evaluate_performance_stability



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
            recent_results=[],
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

    # Trend indicator: last 6 valid results ordered by competition date.
    competition_ids = {
        r.get("competition") for r in results if r.get("competition")
    }
    competition_dates = {}
    if competition_ids:
        competitions = await competitions_collection.find(
            {"_id": {"$in": list(competition_ids)}}
        ).to_list(length=None)
        competition_dates = {
            c["_id"]: c.get("date")
            for c in competitions
            if c.get("date") is not None
        }

    indicator_entries = []
    for r in results:
        comp_id = r.get("competition")
        comp_date = competition_dates.get(comp_id) if comp_id else None
        if comp_date is None:
            continue
        indicator_entries.append(
            {
                "competition_date": comp_date,
                "final_time": r.get("final_time"),
                "final_time_status": r.get("final_time_status"),
                "rank": r.get("rank"),
            }
        )

    performance_indicator, recent_results = calculate_performance_indicator(indicator_entries)

    stability_info = evaluate_performance_stability(indicator_entries)
    performance_variability = stability_info["performance_variability"]
    stability_rating = stability_info["stability_rating"]

    # Najdi soutěž s nejlepším časem
    best_performance_info = {}
    if best_time is not None:
        best_result = None
        for r in results:
            final_time = r.get("final_time")
            if final_time is not None and final_time == best_time:
                best_result = r
                break
        
        if best_result and best_result.get("competition"):
            comp = await competitions_collection.find_one({"_id": best_result["competition"]})
            if comp:
                best_performance_info = {
                    "time": best_time,
                    "competition_place": comp.get("place"),
                    "competition_date": comp.get("date").strftime("%d. %m. %Y") if comp.get("date") else None
                }

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
        performance_indicator=performance_indicator,
        recent_results=recent_results,
        performance_variability=performance_variability,
        stability_rating=stability_rating,
        best_performance=best_performance_info,
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


async def get_athlete_performance_by_year_service(athlete_id: str):
    """
    Vrátí data pro graf vývoje výkonu po sezónách.
    Vrací výkonnostní data seřazená po jednotlivých letech.
    
    Args:
        athlete_id (str): ID atleta
        
    Returns:
        PerformanceByYear: Data obsahující roky a výkonnostní body pro každý rok
    """
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    
    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")
    
    # Získej všechny výsledky atleta
    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)
    if not results:
        return {"years": [], "data": {}}
    
    # Počet roků v datech
    competition_ids = {r.get("competition") for r in results if r.get("competition")}
    if not competition_ids:
        return {"years": [], "data": {}}
    
    competitions = await competitions_collection.find(
        {"_id": {"$in": list(competition_ids)}}
    ).to_list(length=None)
    
    # Mapování competition_id -> date
    comp_dates = {c["_id"]: c.get("date") for c in competitions if c.get("date")}
    
    # Seskup výsledky po jednotlivých letech
    data_by_year = {}
    years_set = set()
    
    for r in results:
        comp_id = r.get("competition")
        comp_date = comp_dates.get(comp_id) if comp_id else None
        
        if comp_date is None or r.get("final_time") is None:
            continue
        
        year = comp_date.year
        years_set.add(year)
        
        if year not in data_by_year:
            data_by_year[year] = []
        
        data_by_year[year].append({
            "date": comp_date.strftime("%Y-%m-%d"),
            "time": r.get("final_time"),
            "rank": r.get("rank")
        })
    
    # Seřad výsledky pro každý rok chronologicky
    for year in data_by_year:
        data_by_year[year].sort(key=lambda x: x["date"])
    
    years = sorted(list(years_set))
    
    return {"years": years, "data": data_by_year}
