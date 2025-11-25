from typing import Dict, List
from fastapi import APIRouter, Query, HTTPException, Depends
from app.models.athlete import AthleteInDB
from app.dependencies import get_current_user
from bson import ObjectId
from datetime import datetime


import logging
  

from app.services.athletes import (
    get_athlete_competition_count,
    get_athlete_best_time_in_year,
    get_competitions_in_year,
    get_athlete_average_time_in_year,
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

@router.get("/search", response_model=dict)
async def search_athletes(q: str = Query(..., min_length=2)):
    """Vyhledá atlety podle jména, příjmení nebo FS kódu"""
    return await search_athletes_service(q)

@router.get("/{athlete_id}/overview")
async def get_athlete_overview(athlete_id: str, user=Depends(get_current_user)):
    """Vrátí přehled výkonů atleta (poslední aktivita, statistiky)"""
    return await get_athlete_overview_service(athlete_id)

@router.get("/{athlete_id}/detail")
async def get_athlete_detail(athlete_id: str):
    return await get_athlete_detail_service(athlete_id)



    