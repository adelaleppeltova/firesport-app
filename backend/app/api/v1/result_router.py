from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.category_catalog import CATEGORIES, DISCIPLINES, Discipline
from app.models.category import CategoryInDB
from app.models.result import ResultInDB
from app.services.results import (
    get_result_detail_service,
    list_results_service,
)

router = APIRouter(prefix="/results", tags=["results"])


@router.get("", response_model=List[ResultInDB])
async def list_results(
    athlete_id: Optional[str] = Query(None, description="Filtrovat podle atleta"),
    competition_id: Optional[str] = Query(None, description="Filtrovat podle soutěže"),
    category_id: Optional[str] = Query(None, description="Filtrovat podle kategorie"),
    discipline: Optional[Discipline] = Query(None),
    limit: int = Query(1000, ge=1, le=10_000),
):
    """
    Vrátí seznam výsledků (volitelně filtrováno podle atleta, soutěže nebo kategorie).
    """
    try:
        return await list_results_service(
            athlete_id=athlete_id,
            competition_id=competition_id,
            category_id=category_id,
            limit=limit,
            discipline=discipline,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/catalog")
async def get_catalog(discipline: Optional[Discipline] = Query(None)):
    return {
        "disciplines": DISCIPLINES,
        "categories": [
            CategoryInDB.model_validate({**category.document(), "_id": str(category.id)})
            for category in CATEGORIES if discipline is None or category.discipline == discipline
        ],
    }


@router.get("/{result_id}", response_model=ResultInDB)
async def get_result_detail(result_id: str):
    """
    Vrátí detail jednoho výsledku podle jeho ID.
    """
    try:
        return await get_result_detail_service(result_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
