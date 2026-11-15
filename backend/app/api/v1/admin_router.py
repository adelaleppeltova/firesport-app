from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError

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
    BulkAssignmentRequest,
    ReviewCandidatesResponse,
    VerifyExternalIdentityRequest,
)
from app.models.athlete import AthletesSearch
from app.services.admin import (
    assign_result_group,
    assign_result_to_athlete,
    create_athlete_from_result,
    delete_review_results,
    get_result_candidates,
    get_review_results,
    import_results_from_files,
    merge_athletes_for_admin,
    search_athletes_for_admin,
    search_merge_candidates_for_admin,
    unassign_result_from_athlete,
    verify_result_external_identity,
)

from app.services.external_identity import ExternalIdentitySidecar

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/import", response_model=AdminImportResponse)
async def admin_import_results(
    files: list[UploadFile] = File(...), external_identity_sidecar: str | None = Form(None),
):
    try:
        sidecar = ExternalIdentitySidecar.model_validate_json(external_identity_sidecar) if external_identity_sidecar else None
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Neplatná provenience externích identifikátorů.") from exc
    stats = await import_results_from_files(files, external_sidecar=sidecar)
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
async def admin_assign_athlete(result_id: str, body: AssignAthleteRequest, user=Depends(require_admin)):
    return await assign_result_to_athlete(result_id, body.athlete_id, admin_id=user["id"])


@router.get("/results/{result_id}/candidates", response_model=ReviewCandidatesResponse)
async def admin_result_candidates(result_id: str):
    return await get_result_candidates(result_id)


@router.post("/results/bulk-assign-athlete")
async def admin_bulk_assign(body: BulkAssignmentRequest, user=Depends(require_admin)):
    return await assign_result_group(body.result_ids, body.athlete_id, admin_id=user["id"])


@router.post("/results/{result_id}/verify-external-identity")
async def admin_verify_external_identity(
    result_id: str, body: VerifyExternalIdentityRequest, user=Depends(require_admin),
):
    return await verify_result_external_identity(
        result_id, body.athlete_id, body.provider, body.person_id, admin_id=user["id"],
    )


@router.post(
    "/results/{result_id}/create-athlete",
    response_model=AdminResultAssignmentResponse,
)
async def admin_create_athlete(result_id: str, user=Depends(require_admin)):
    return await create_athlete_from_result(result_id, admin_id=user["id"])


@router.post(
    "/results/{result_id}/unassign-athlete",
    response_model=AdminResultUnassignmentResponse,
)
async def admin_unassign_athlete(result_id: str, user=Depends(require_admin)):
    return await unassign_result_from_athlete(result_id, admin_id=user["id"])


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
