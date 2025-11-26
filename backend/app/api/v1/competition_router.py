

from fastapi import APIRouter
from typing import List
from app.services.competitions import (
    get_competition_detail_service,
    get_competitions_service,
    get_results_for_category_service
)


router = APIRouter(prefix="/competitions", tags=["competitions"])

@router.get("/{id}/detail")
async def get_competition_detail(id: str):
    result = await get_competition_detail_service(id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Competition not found")
    return result

from app.models.competition import CompetitionInDB

@router.get("", response_model=List[CompetitionInDB])
async def get_competitions():
    return await get_competitions_service()


@router.get("/{competition_id}/results/{category_id}")
async def get_results_for_category(competition_id: str, category_id: str):
    return await get_results_for_category_service(competition_id, category_id)


    

