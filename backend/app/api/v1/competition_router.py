from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

from app.models.competition import CompetitionInDB, CompetitionDetail, CompetitionsPage
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

@router.get("", response_model=CompetitionsPage)
async def get_competitions(
    q: Optional[str] = Query(None, description="Hledaný výraz (název, místo, liga)"),
    page: int = Query(1, ge=1, description="Číslo stránky"),
    page_size: int = Query(25, ge=1, le=100, description="Počet záznamů na stránku"),
    sort_key: str = Query("date", description="Klíč řazení (date, name, place)"),
    sort_dir: str = Query("desc", description="Směr řazení (asc, desc)"),
):
    """Vrátí stránkovaný seznam soutěží."""
    return await get_competitions_service(
        search=q, page=page, page_size=page_size,
        sort_key=sort_key, sort_dir=sort_dir,
    )


@router.get("/{competition_id}/results/{category_id}", response_model=List[ResultInDB])
async def get_results_for_category(competition_id: str, category_id: str):
    """Vrátí výsledky pro danou soutěž a kategorii jako seznam ResultInDB."""

    try:
        return await get_results_for_category_service(competition_id, category_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    

