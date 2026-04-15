from app.models.admin import (
    AdminDeleteReviewResponse,
    AdminImportResponse,
    AdminResultAssignmentResponse,
    AdminResultUnassignmentResponse,
    DataImportResponse,
)
from app.models.result import MatchStatus
from app.models.user import (
    AthletePairingResponse,
    AuthenticatedUserOut,
    CurrentUserResponse,
)


def test_user_response_models_accept_current_payload_shapes():
    auth_me = AuthenticatedUserOut.model_validate(
        {
            "id": "user-1",
            "email": "user@example.com",
            "role": "user",
            "is_active": True,
            "athlete_id": "athlete-1",
        }
    )
    me = CurrentUserResponse.model_validate(
        {
            "user_id": "user-1",
            "email": "user@example.com",
            "role": "admin",
            "athlete_id": None,
        }
    )
    pairing = AthletePairingResponse.model_validate(
        {"ok": True, "athlete_id": "athlete-1"}
    )

    assert auth_me.role == "user"
    assert me.role == "admin"
    assert pairing.athlete_id == "athlete-1"


def test_import_response_models_accept_current_payload_shapes():
    data_import = DataImportResponse.model_validate(
        {
            "success": True,
            "message": "Import dokoncen",
            "data": {
                "total_imported": 3,
                "review_required": 1,
                "athletes_created_new": 1,
                "athletes_existing_matched": 1,
                "categories_created": 1,
                "competitions_created": 1,
                "results_created": 3,
                "results_matched": 2,
                "results_needs_review": 1,
                "results_unmatched": 0,
                "errors": [],
            },
        }
    )
    admin_import = AdminImportResponse.model_validate(
        {
            "success": True,
            "message": "Import dokoncen",
            "data": {
                "files_processed": 2,
                "total_imported": 6,
                "review_required": 2,
                "athletes_created_new": 1,
                "athletes_existing_matched": 3,
                "categories_created": 2,
                "competitions_created": 2,
                "results_created": 6,
                "results_matched": 4,
                "results_needs_review": 1,
                "results_unmatched": 1,
                "errors": ["warn"],
            },
        }
    )

    assert data_import.data.total_imported == 3
    assert admin_import.data.files_processed == 2


def test_admin_action_response_models_accept_current_payload_shapes():
    assignment = AdminResultAssignmentResponse.model_validate(
        {
            "ok": True,
            "result_id": "result-1",
            "athlete_id": "athlete-1",
            "auto_reassigned": 2,
        }
    )
    unassignment = AdminResultUnassignmentResponse.model_validate(
        {
            "ok": True,
            "result_id": "result-1",
            "match_status": MatchStatus.needs_review.value,
        }
    )
    delete_review = AdminDeleteReviewResponse.model_validate(
        {"ok": True, "deleted_count": 5}
    )

    assert assignment.auto_reassigned == 2
    assert unassignment.match_status == MatchStatus.needs_review
    assert delete_review.deleted_count == 5
