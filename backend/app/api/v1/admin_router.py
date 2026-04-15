from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile

from app.dependencies import require_admin
from app.models.admin import (
    AssignAthleteRequest,
    AdminDeleteReviewResponse,
    AdminImportResponse,
    AdminResultAssignmentResponse,
    AdminResultUnassignmentResponse,
    AdminReviewResponse,
    AthleteMergeCandidatesResponse,
    AthleteMergeResponse,
)
from app.models.athlete import AthletesSearch
from app.services.admin import (
    assign_result_to_athlete,
    create_athlete_from_result,
    delete_review_results,
    get_review_results,
    import_results_from_files,
    merge_athletes_for_admin,
    search_athletes_for_admin,
    search_merge_candidates_for_admin,
    unassign_result_from_athlete,
)

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/import", response_model=AdminImportResponse)
async def admin_import_results(files: list[UploadFile] = File(...)):
    stats = await import_results_from_files(files)
    return {
        "success": True,
        "message": "Import dokončen",
        "data": stats,
    }


@router.get("/import/review", response_model=AdminReviewResponse)
async def admin_import_review():
    return await get_review_results()


@router.delete("/import/review", response_model=AdminDeleteReviewResponse)
async def admin_delete_import_review():
    return await delete_review_results()


@router.post(
    "/results/{result_id}/assign-athlete",
    response_model=AdminResultAssignmentResponse,
)
async def admin_assign_athlete(result_id: str, body: AssignAthleteRequest):
    return await assign_result_to_athlete(result_id, body.athlete_id)


@router.post(
    "/results/{result_id}/create-athlete",
    response_model=AdminResultAssignmentResponse,
)
async def admin_create_athlete(result_id: str):
    return await create_athlete_from_result(result_id)


@router.post(
    "/results/{result_id}/unassign-athlete",
    response_model=AdminResultUnassignmentResponse,
)
async def admin_unassign_athlete(result_id: str):
    return await unassign_result_from_athlete(result_id)


@router.get("/athletes/search", response_model=AthletesSearch)
async def admin_search_athletes(q: str):
    return await search_athletes_for_admin(q)


@router.get("/athletes/merge-candidates", response_model=AthleteMergeCandidatesResponse)
async def admin_search_merge_candidates(athlete_id: str, q: Optional[str] = None):
    return await search_merge_candidates_for_admin(athlete_id=athlete_id, q=q)


@router.post(
    "/athletes/{source_athlete_id}/merge-into/{target_athlete_id}",
    response_model=AthleteMergeResponse,
)
async def admin_merge_athletes(source_athlete_id: str, target_athlete_id: str):
    return await merge_athletes_for_admin(source_athlete_id, target_athlete_id)
