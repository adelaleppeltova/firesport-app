from fastapi import APIRouter, HTTPException
from typing import List

from app.models.competition import CompetitionInDB, CompetitionDetail
from app.models.result import ResultInDB
from app.services.competitions import (
    get_competition_detail_service,
    get_competitions_service,
    get_results_for_category_service
)


router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("/{competition_id}/detail", response_model=CompetitionDetail)
async def get_competition_detail(competition_id: str):
    """Vrátí detail soutěže jako CompetitionInDB."""
    try:
        return await get_competition_detail_service(competition_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("", response_model=List[CompetitionInDB])
async def get_competitions():
    """Vrátí seznam všech soutěží."""

    return await get_competitions_service()


@router.get("/{competition_id}/results/{category_id}", response_model=List[ResultInDB])
async def get_results_for_category(competition_id: str, category_id: str):
    """Vrátí výsledky pro danou soutěž a kategorii jako seznam ResultInDB."""

    try:
        return await get_results_for_category_service(competition_id, category_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    

