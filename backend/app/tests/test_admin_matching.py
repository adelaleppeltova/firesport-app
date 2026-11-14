import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

from app.models.result import MatchStatus
from app.services import admin


def _result(**fields):
    return {
        "_id": ObjectId(),
        "imported_athlete": {"first_name": "Jan", "last_name": "Novák", "birth_year": 2000},
        "team": "Lhota",
        "match_status": MatchStatus.unmatched.value,
        **fields,
    }


def test_manual_assignment_guarded_rematch_preserves_concurrent_admin_decision():
    profile = {"_id": ObjectId(), "first_name": "Jan", "last_name": "Novák"}
    selected = _result()
    pending = _result()
    reconsidered = _result()
    with (
        patch.object(admin, "athletes_collection") as athletes,
        patch.object(admin, "results_collection") as results,
        patch.object(admin, "decide_athlete_match", new_callable=AsyncMock) as decide,
    ):
        athletes.find_one = AsyncMock(return_value=profile)
        results.find_one = AsyncMock(return_value=selected)
        results.find.return_value.__aiter__.return_value = [pending, reconsidered]
        results.update_one = AsyncMock(side_effect=[
            MagicMock(modified_count=1),
            MagicMock(modified_count=1),
            MagicMock(modified_count=0),  # Admin assigned or unassigned after cursor read.
        ])
        decide.return_value = {
            "match_status": MatchStatus.matched,
            "matched_athlete": profile,
            "match_reason": "name_plus_birth_year",
        }

        response = asyncio.run(admin.assign_result_to_athlete(str(selected["_id"]), str(profile["_id"])))

    assert response["auto_reassigned"] == 1
    manual, auto, _ = [call.args for call in results.update_one.await_args_list]
    assert manual[1]["$set"]["match_reason"] == "manual_admin_assignment"
    assert auto[0]["athlete"] is None
    assert auto[0]["match_status"] == {"$in": ["needs_review", "unmatched"]}
    assert auto[0]["match_reason"] == {"$not": {"$regex": "^manual_admin_"}}
    assert auto[1]["$set"]["athlete"] == profile["_id"]
    athletes.update_one.assert_not_called()


def test_rematch_requires_same_strong_identity_as_import():
    profile = {"_id": ObjectId(), "first_name": "Jan", "last_name": "Novák", "teams": ["Lhota"]}
    pending = _result(imported_athlete={"first_name": "Jan", "last_name": "Novák"})
    with (
        patch.object(admin, "results_collection") as results,
        patch("app.services.result_matching._find_athletes", AsyncMock(return_value=[profile])),
    ):
        results.find.return_value.__aiter__.return_value = [pending]
        assert asyncio.run(admin._rematch_review_results(profile)) == 0
    results.update_one.assert_not_called()


def test_manual_profile_creation_retains_admin_assignment():
    candidate = _result()
    athlete_id = ObjectId()
    with (
        patch.object(admin, "results_collection") as results,
        patch.object(admin, "athletes_collection") as athletes,
    ):
        results.find_one = AsyncMock(return_value=candidate)
        results.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        results.find.return_value.__aiter__.return_value = []
        athletes.insert_one = AsyncMock(return_value=MagicMock(inserted_id=athlete_id))
        response = asyncio.run(admin.create_athlete_from_result(str(candidate["_id"])))

    assert response["athlete_id"] == str(athlete_id)
    assert athletes.insert_one.await_args.args[0]["birth_year"] == 2000
    assert results.update_one.await_args.args[1]["$set"]["match_reason"] == "manual_admin_create_athlete"
    assert results.find.call_args.args[0]["athlete"] is None


def test_review_queue_includes_unresolved_import_with_original_identity_and_reason():
    doc = _result(
        imported_athlete={"first_name": "JAN", "last_name": "Novák", "birth_year": 2000, "fscode": "12345"},
        match_reason="no_match",
    )
    with patch.object(admin, "results_collection") as results:
        results.find.return_value.sort.return_value.to_list = AsyncMock(return_value=[doc])
        response = asyncio.run(admin.get_review_results())

    assert results.find.call_args.args[0]["match_status"] == {"$in": ["needs_review", "unmatched"]}
    assert response.summary.unmatched == 1
    assert response.items[0].imported_athlete.first_name == "JAN"
    assert response.items[0].imported_athlete.fscode == "12345"
    assert response.items[0].match_reason == "no_match"
