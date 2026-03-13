from typing import List, Optional, Literal
from fastapi import APIRouter, Query, HTTPException, Depends
from app.models.athlete import AthleteInDB, AthletesSearch, AthletesPage, AthleteOverview, PerformanceByYear, PerformanceInYear, AthleteCategoryStatsResponse
from app.models.models import AthleteDetailPage
from app.dependencies import get_current_user
from bson import ObjectId
from datetime import datetime


import logging
  

from app.services.athletes import (
    get_athlete_year_summary_service,
    search_athletes_service,
    get_athlete_overview_service,
    get_athlete_detail_service,
    list_athletes_service,
    get_athlete_performance_by_year_service,
    get_athlete_category_stats_service,
)


router = APIRouter(prefix="/athletes", tags=["athletes"])

logger = logging.getLogger("firesport.overview")

@router.get("/", response_model=AthletesPage)
async def list_athletes(
    q: Optional[str] = Query(None, description="Hledaný výraz (jméno, rok, sbor)"),
    page: int = Query(1, ge=1, description="Číslo stránky"),
    page_size: int = Query(25, ge=1, le=100, description="Počet záznamů na stránku"),
    anomaly_status: Optional[Literal["processed"]] = Query(
        None,
        description="Volitelný filtr dle stavu anomálií. Podporováno: 'processed'.",
    ),
    run_id: Optional[str] = Query(
        None,
        description="Volitelné run_id v anomaly_runs pro filtr anomaly_status.",
    ),
):
    return await list_athletes_service(
        search=q,
        page=page,
        page_size=page_size,
        anomaly_status=anomaly_status,
        run_id=run_id,
    )

@router.get("/search", response_model=AthletesSearch)
async def search_athletes(q: str):
    """Vyhledá atlety podle jména, příjmení nebo FS kódu"""
    return await search_athletes_service(q)

@router.get("/{athlete_id}/overview", response_model=AthleteOverview)
async def get_athlete_overview(athlete_id: str, user=Depends(get_current_user)):
    """Vrátí přehled výkonů atleta."""
    try:
        return await get_athlete_overview_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{athlete_id}/detail", response_model=AthleteDetailPage)
async def get_athlete_detail(athlete_id: str):
    """Vrátí detail atleta včetně výkonů jako AthleteDetail."""
    try:
        return await get_athlete_detail_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{athlete_id}/performance-by-year", response_model=PerformanceByYear)
async def get_athlete_performance_by_year(athlete_id: str, user=Depends(get_current_user)):
    """Vrátí data vývoje výkonu atleta po jednotlivých sezónách pro graf."""
    try:
        return await get_athlete_performance_by_year_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
@router.get("/{athlete_id}/performance-in-year", response_model=PerformanceInYear)
async def get_athlete_performance_in_year(athlete_id: str, user=Depends(get_current_user)):
    """Vrátí data vývoje výkonu atleta po jednotlivých sezónách pro graf."""
    try:
        return await get_athlete_year_summary_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{athlete_id}/category-stats", response_model=AthleteCategoryStatsResponse)
async def get_athlete_category_stats(athlete_id: str):
    """Vrátí celkový počet závodů a nejlepší čas pro každou skupinu kategorií.

    Zahrnuje všechny záznamy v DB (validní i nevalidní), bez omezení na okno detekce.
    """
    try:
        return await get_athlete_category_stats_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))