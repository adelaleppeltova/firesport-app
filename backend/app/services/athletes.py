from bson import ObjectId
from app.db.database import db
from app.models.athlete import (
    AthleteCategoryStatsResponse, AthleteInDB, AthletesSearch, AthletesPage, AthleteOverview, AthleteDetail,
    BestPerformance, AthleteProfile, AthletePerformanceHistoryResponse,
    AthletePerformanceStabilityResponse, CategoryRaceStats,
    AthletePerCategoryStats, AthletePerCategoryStatsResponse,
)
from app.models.result import ResultAthleteDetail
from datetime import datetime
from typing import List, Dict, Optional, Any, Set

from app.models.models import AthleteDetailPage
from app.ml.anomaly_config import get_category_group
from app.services.athlete_identity import active_athlete_query, normalize_athlete_document
from app.services.performance_indicator import calculate_performance_indicator
from app.services.performance_stability_service import evaluate_performance_stability
from app.services.search_utils import build_diacritic_fuzzy_regex



athletes_collection = db["athletes"]
results_collection = db["results"]
competitions_collection = db["competitions"]
categories_collection = db["categories"]


async def list_athletes_service(
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 25,
    anomaly_status: Optional[str] = None,
    run_id: Optional[str] = None,
) -> AthletesPage:
    """Vrátí stránkovaný seznam atletů s volitelným vyhledáváním."""
    query: Dict[str, Any] = active_athlete_query()

    if anomaly_status == "processed":
        if run_id:
            # Filtrujeme podle konkrétního runu
            processed_athlete_ids: List[ObjectId] = await db["anomaly_scores"].distinct(
                "athlete_id",
                {"run_id": run_id},
            )
        else:
            # Vyhledáváme přes VŠECHNY anomaly runy – bez omezení na jeden run
            processed_athlete_ids = await db["anomaly_scores"].distinct(
                "athlete_id",
                {},
            )

        if not processed_athlete_ids:
            return AthletesPage(items=[], total=0, page=page, page_size=page_size)

        query["_id"] = {"$in": processed_athlete_ids}

    if search and search.strip():
        raw = search.strip()
        # Rozděl na klíčová slova podle mezer, ale zachovej data (např. "2024-01-15") jako celek
        import re
        tokens = re.findall(r'\d{4}[-/.]\d{2}[-/.]\d{2}|\S+', raw)

        if len(tokens) > 1:
            # Víc klíčových slov → každé musí matchnout alespoň jedno pole (AND logika)
            and_conditions = []
            for token in tokens:
                token_regex = build_diacritic_fuzzy_regex(token)
                or_cond: list = [
                    {"first_name": {"$regex": token_regex, "$options": "i"}},
                    {"last_name": {"$regex": token_regex, "$options": "i"}},
                    {
                        "teams": {
                            "$elemMatch": {
                                "$regex": token_regex,
                                "$options": "i",
                            }
                        }
                    },
                    {
                        "fs_codes": {
                            "$elemMatch": {
                                "$regex": re.escape(token),
                                "$options": "i",
                            }
                        }
                    },
                ]
                if token.isdigit():
                    or_cond.append({"birth_year": int(token)})
                    or_cond.append({"fs_codes": token})
                and_conditions.append({"$or": or_cond})
            query["$and"] = and_conditions
        else:
            # Jedno klíčové slovo → původní OR logika
            q = tokens[0]
            q_regex = build_diacritic_fuzzy_regex(q)
            or_conditions: list = [
                {"first_name": {"$regex": q_regex, "$options": "i"}},
                {"last_name": {"$regex": q_regex, "$options": "i"}},
                {"teams": {"$elemMatch": {"$regex": q_regex, "$options": "i"}}},
                {"fs_codes": {"$elemMatch": {"$regex": re.escape(q), "$options": "i"}}},
            ]
            if q.isdigit():
                or_conditions.append({"birth_year": int(q)})
                or_conditions.append({"fs_codes": q})
            query["$or"] = or_conditions

    total = await athletes_collection.count_documents(query)
    skip = (page - 1) * page_size

    athletes = (
        await athletes_collection.find(query)
        .collation({"locale": "cs", "strength": 1})
        .sort("last_name", 1)
        .skip(skip)
        .limit(page_size)
        .to_list(length=page_size)
    )
    for a in athletes:
        a["_id"] = str(a["_id"])

    return AthletesPage(
        items=[AthleteInDB.model_validate(a) for a in athletes],
        total=total,
        page=page,
        page_size=page_size,
    )

async def get_athlete_overview_service(athlete_id: str) -> AthleteOverview:
    """Vrátí přehled výkonů atleta jako AthleteOverview."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")
    
    athlete = normalize_athlete_document(
        await athletes_collection.find_one({"_id": athlete_oid})
    )
    if not athlete:
        raise ValueError("Athlete not found")
    
    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)

    if not results:
        return AthleteOverview(
            id=str(athlete["_id"]),
            first_name=athlete.get("first_name", ""),
            last_name=athlete.get("last_name", ""),
            birth_year=athlete.get("birth_year"),
            teams=athlete.get("teams", []),
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

    performance_indicator = calculate_performance_indicator(indicator_entries)

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
        teams=athlete.get("teams", []),
        last_active=last_active,
        total_competitions=total_competitions,
        best_time=best_time,
        average_time=average_time,
        performance_indicator=performance_indicator,
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
    
    athlete = normalize_athlete_document(
        await athletes_collection.find_one({"_id": athlete_oid})
    )
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

        # build result payload matching ResultAthleteDetail
        result_payload = {
            "competition": comp_payload,
            "category": cat_payload,
            "date": r.get("date"),
            "team": r.get("team"),
            "start_number": r.get("start_number"),
            "times": r.get("times", []),
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
        }

        # validate as ResultBase and append
        validated = ResultAthleteDetail.model_validate(result_payload)
        results.append(validated)

    # build AthleteDetail for response
    athlete_detail = AthleteDetail(
        id=str(athlete_payload["_id"]),
        first_name=athlete.get("first_name"),
        last_name=athlete.get("last_name"),
        birth_year=athlete.get("birth_year"),
        fs_codes=athlete.get("fs_codes", []),
        teams=athlete.get("teams", []),
        category=category_name,
        best_time=best_time,
    )
    return AthleteDetailPage(
        athlete=athlete_detail,
        results=results,
        best_time=best_time
    )


async def search_athletes_service(q: str) -> AthletesSearch:
    raw = q.strip()
    if not raw:
        return AthletesSearch(items=[])

    import re

    tokens = re.findall(r"\S+", raw)

    if len(tokens) > 1:
        and_conditions = []
        for token in tokens:
            token_regex = build_diacritic_fuzzy_regex(token)
            or_conditions = [
                {"first_name": {"$regex": token_regex, "$options": "i"}},
                {"last_name": {"$regex": token_regex, "$options": "i"}},
                {"fs_codes": {"$elemMatch": {"$regex": re.escape(token), "$options": "i"}}},
            ]
            if token.isdigit():
                or_conditions.append({"birth_year": int(token)})
                or_conditions.append({"fs_codes": token})
            and_conditions.append({"$or": or_conditions})
        query = {"$and": and_conditions}
    else:
        token = tokens[0]
        token_regex = build_diacritic_fuzzy_regex(token)
        or_conditions = [
            {"first_name": {"$regex": token_regex, "$options": "i"}},
            {"last_name": {"$regex": token_regex, "$options": "i"}},
            {"fs_codes": {"$elemMatch": {"$regex": re.escape(token), "$options": "i"}}},
        ]
        if token.isdigit():
            or_conditions.append({"birth_year": int(token)})
            or_conditions.append({"fs_codes": token})
        query = {"$or": or_conditions}

    athletes = await athletes_collection.find(active_athlete_query(query)).to_list(length=20)
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
    
    athlete = normalize_athlete_document(
        await athletes_collection.find_one({"_id": athlete_oid})
    )
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
    
    # Mapování competition_id -> date a place
    comp_dates = {c["_id"]: c.get("date") for c in competitions if c.get("date")}
    comp_places = {c["_id"]: c.get("place") for c in competitions}
    
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
            "rank": r.get("rank"),
            "place": comp_places.get(comp_id)
        })
    
    # Seřad výsledky pro každý rok chronologicky
    for year in data_by_year:
        data_by_year[year].sort(key=lambda x: x["date"])
    
    years = sorted(list(years_set))
    
    return {"years": years, "data": data_by_year}


async def get_athlete_year_summary_service(athlete_id: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Vrátí souhrn pro daný rok (nebo aktuální kalendářní rok):
    - average_time: průměrný platný final_time v roce
    - best_time: nejlepší platný final_time v roce
    - competitions: počet unikátních závodů v roce
    - races: detailní přehled závodů v roce (datum, soutěž, kategorie, časy)

    Pokud `year` není zadán, použije se aktuální kalendářní rok.
    """

    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")

    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)
    if not results:
        target_year = year if year is not None else datetime.now().year
        return {
            "year": target_year,
            "average_time": None,
            "best_time": None,
            "competitions": 0,
            "races": [],
        }

    # Home karta Season má vždy ukazovat aktuální kalendářní rok.
    target_year = year if year is not None else datetime.now().year

    # Filtrování výsledků na daný rok podle data soutěže
    filtered: List[Dict[str, Any]] = []
    comp_ids: Set[ObjectId] = set()
    cat_ids: Set[ObjectId] = set()

    for r in results:
        comp_id = r.get("competition")
        if not comp_id:
            continue
        try:
            comp_oid = comp_id if isinstance(comp_id, ObjectId) else ObjectId(str(comp_id))
        except Exception:
            continue
        comp_doc = await competitions_collection.find_one({"_id": comp_oid}, {"date": 1})
        if not comp_doc or not comp_doc.get("date"):
            continue
        comp_date = comp_doc["date"]
        if comp_date.year != target_year:
            continue
        r_copy = dict(r)
        r_copy["_id"] = r_copy.get("_id", None)
        r_copy["competition_doc"] = comp_doc
        filtered.append(r_copy)
        comp_ids.add(comp_oid)
        if r.get("category"):
            try:
                cat_ids.add(r["category"] if isinstance(r["category"], ObjectId) else ObjectId(str(r["category"])))
            except Exception:
                pass

    if not filtered:
        return {
            "year": target_year,
            "average_time": None,
            "best_time": None,
            "competitions": 0,
            "races": [],
        }

    # Načti soutěže a kategorie do map
    comp_map: Dict[ObjectId, Dict[str, Any]] = {}
    if comp_ids:
        comps = await competitions_collection.find({"_id": {"$in": list(comp_ids)}}).to_list(length=None)
        comp_map = {c["_id"]: c for c in comps}

    cat_map: Dict[ObjectId, Dict[str, Any]] = {}
    if cat_ids:
        cats = await categories_collection.find({"_id": {"$in": list(cat_ids)}}).to_list(length=None)
        cat_map = {c["_id"]: c for c in cats}

    # Výpočty metrik
    valid_times = [r.get("final_time") for r in filtered if r.get("final_time") is not None]
    average_time = sum(valid_times) / len(valid_times) if valid_times else None
    best_time = min(valid_times) if valid_times else None

    competitions_count = len({r.get("competition") for r in filtered if r.get("competition")})

    races = []
    for r in filtered:
        comp_doc = comp_map.get(r.get("competition")) or r.get("competition_doc") or {}
        cat_doc = None
        if r.get("category"):
            cat_doc = cat_map.get(r.get("category"))

        comp_date = comp_doc.get("date")
        races.append({
            "competition_id": str(r.get("competition")) if r.get("competition") else None,
            "competition_name": comp_doc.get("name"),
            "competition_place": comp_doc.get("place"),
            "category": cat_doc.get("name") if cat_doc else None,
            "date": comp_date.strftime("%Y-%m-%d") if comp_date else None,
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
            "times": r.get("times", []),
        })

    # Seřaď závody podle data
    races.sort(key=lambda x: x["date"] or "")

    return {
        "year": target_year,
        "average_time": average_time,
        "best_time": best_time,
        "competitions": competitions_count,
        "races": races,
    }


async def get_athlete_category_stats_service(athlete_id: str) -> AthleteCategoryStatsResponse:
    """Vrátí celkový počet závodů a nejlepší čas pro každou skupinu kategorií.

    Zahrnuje všechny záznamy v DB (validní i nevalidní, bez omezení na okno detekce).
    """
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    # 1) Sestav mapu category_id (str) → category_group
    category_group_map: Dict[str, str] = {}
    async for cat_doc in categories_collection.find({}, projection={"_id": 1, "name": 1}):
        cat_name = cat_doc.get("name") or ""
        category_group_map[str(cat_doc["_id"])] = get_category_group(cat_name)

    # 2) Načti všechny výsledky závodníka (bez jakéhokoliv filtru)
    raw_results = await results_collection.find(
        {"athlete": athlete_oid},
        projection={"_id": 0, "category": 1, "final_time": 1},
    ).to_list(None)

    # 3) Agreguj po skupinách
    totals: Dict[str, int] = {}
    best_times: Dict[str, Optional[float]] = {}

    for r in raw_results:
        cat_oid = r.get("category")
        cg = category_group_map.get(str(cat_oid), str(cat_oid)) if cat_oid is not None else "unknown"
        totals[cg] = totals.get(cg, 0) + 1
        ft = r.get("final_time")
        if ft is not None:
            if best_times.get(cg) is None or ft < best_times[cg]:
                best_times[cg] = ft

    stats = {
        cg: CategoryRaceStats(total_races=totals[cg], best_time=best_times.get(cg))
        for cg in totals
    }
    return AthleteCategoryStatsResponse(stats=stats)


async def get_athlete_per_category_stats_service(athlete_id: str) -> AthletePerCategoryStatsResponse:
    """Vrátí počet závodů a nejlepší čas pro každou konkrétní kategorii z DB.

    Na rozdíl od category-stats nepoužívá groupby, ale vrací statistiky
    per jednotlivá kategorie (např. 'Střední dorostenci', 'Muži' atd.).
    """
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    # 1) Mapa category_id → category_name
    category_name_map: Dict[str, str] = {}
    async for cat_doc in categories_collection.find({}, projection={"_id": 1, "name": 1}):
        category_name_map[str(cat_doc["_id"])] = cat_doc.get("name") or str(cat_doc["_id"])

    # 2) Načti všechny výsledky závodníka
    raw_results = await results_collection.find(
        {"athlete": athlete_oid},
        projection={"_id": 0, "category": 1, "final_time": 1},
    ).to_list(None)

    # 3) Agreguj po konkrétní kategorii
    totals: Dict[str, int] = {}
    best_times: Dict[str, Optional[float]] = {}

    for r in raw_results:
        cat_oid = r.get("category")
        if cat_oid is None:
            continue
        cat_id = str(cat_oid)
        totals[cat_id] = totals.get(cat_id, 0) + 1
        ft = r.get("final_time")
        if ft is not None:
            if best_times.get(cat_id) is None or ft < best_times[cat_id]:
                best_times[cat_id] = ft

    categories = [
        AthletePerCategoryStats(
            category_id=cat_id,
            category_name=category_name_map.get(cat_id, cat_id),
            total_races=totals[cat_id],
            best_time=best_times.get(cat_id),
        )
        for cat_id in totals
    ]
    # Seřadit abecedně podle jména kategorie
    categories.sort(key=lambda c: c.category_name)

    return AthletePerCategoryStatsResponse(categories=categories)


async def get_athlete_profile_service(athlete_id: str) -> AthleteProfile:
    """Vrátí základní profil atleta (jméno, tým, nejlepší čas, počet závodů)."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")

    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)

    times = [r.get("final_time") for r in results if r.get("final_time") is not None]
    best_time = min(times) if times else None

    total_competitions = await get_athlete_competition_count(athlete_oid)

    teams = athlete.get("teams", [])
    team = teams[0] if teams else None

    return AthleteProfile(
        _id=str(athlete["_id"]),
        first_name=athlete.get("first_name", ""),
        last_name=athlete.get("last_name", ""),
        birth_year=athlete.get("birth_year"),
        team=team,
        best_time=best_time,
        total_competitions=total_competitions,
    )


async def get_athlete_performance_history_service(
    athlete_id: str,
    year: Optional[int] = None,
) -> AthletePerformanceHistoryResponse:
    """Vrátí indikátor výkonnosti (trend) pro atleta."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")

    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)
    if not results:
        return AthletePerformanceHistoryResponse()

    # Získej data soutěží pro seřazení podle data
    competition_ids = {r.get("competition") for r in results if r.get("competition")}
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
        if year is not None and comp_date.year != year:
            continue
        indicator_entries.append({
            "competition_date": comp_date,
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
        })

    performance_indicator = calculate_performance_indicator(indicator_entries)

    return AthletePerformanceHistoryResponse(
        performance_indicator=performance_indicator,
    )


async def get_athlete_performance_stability_service(
    athlete_id: str,
    year: Optional[int] = None,
) -> AthletePerformanceStabilityResponse:
    """Vrátí data o stabilitě výkonu atleta + průměrný čas v aktuální sezóně."""
    try:
        athlete_oid = ObjectId(athlete_id)
    except Exception:
        raise ValueError("Invalid athlete_id")

    athlete = await athletes_collection.find_one({"_id": athlete_oid})
    if not athlete:
        raise ValueError("Athlete not found")

    results = await results_collection.find({"athlete": athlete_oid}).to_list(length=None)
    if not results:
        return AthletePerformanceStabilityResponse()

    # Stability data
    competition_ids = {r.get("competition") for r in results if r.get("competition")}
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

    target_year = year if year is not None else datetime.now().year

    indicator_entries = []
    for r in results:
        comp_id = r.get("competition")
        comp_date = competition_dates.get(comp_id) if comp_id else None
        if comp_date is None:
            continue
        if comp_date.year != target_year:
            continue
        indicator_entries.append({
            "competition_date": comp_date,
            "final_time": r.get("final_time"),
            "final_time_status": r.get("final_time_status"),
            "rank": r.get("rank"),
        })

    stability_info = evaluate_performance_stability(indicator_entries)

    # Průměrný čas v cílové sezóně
    year_summary = await get_athlete_year_summary_service(athlete_id, year=target_year)
    average_time_in_year = year_summary.get("average_time") if isinstance(year_summary, dict) else None

    return AthletePerformanceStabilityResponse(
        stability_rating=stability_info["stability_rating"],
        performance_variability=stability_info["performance_variability"],
        average_time_in_year=average_time_in_year,
    )
