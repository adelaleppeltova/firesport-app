from typing import List
from fastapi import APIRouter, Query, HTTPException, Depends
from app.models.athlete import AthleteInDB, AthletesSearch, AthleteOverview, AthleteDetail
from app.dependencies import get_current_user
from bson import ObjectId
from datetime import datetime


import logging
  

from app.services.athletes import (
    search_athletes_service,
    get_athlete_overview_service,
    get_athlete_detail_service,
    list_athletes_service
)


router = APIRouter(prefix="/athletes", tags=["athletes"])

logger = logging.getLogger("firesport.overview")

@router.get("/", response_model=List[AthleteInDB])
async def list_athletes():
    return await list_athletes_service()

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

@router.get("/{athlete_id}/detail", response_model=AthleteDetail)
async def get_athlete_detail(athlete_id: str):
    """Vrátí detail atleta včetně výkonů jako AthleteDetail."""
    try:
        return await get_athlete_detail_service(athlete_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))