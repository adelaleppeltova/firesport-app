import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

from app.models.result import MatchStatus
from app.services.admin import assign_result_to_athlete


def test_manual_assignment_reassigns_matching_review_results():
    result_id = ObjectId()
    selected_athlete_id = ObjectId()
    rematched_result_id = ObjectId()

    selected_result = {
        "_id": result_id,
        "imported_athlete": {
            "first_name": "Jan",
            "last_name": "Novak",
            "birth_year": None,
            "fscode": None,
        },
        "team": None,
    }
    review_result = {
        "_id": rematched_result_id,
        "imported_athlete": {
            "first_name": "Jan",
            "last_name": "Novak",
            "birth_year": 2002,
            "fscode": "12345",
        },
        "team": "SDH Lhota",
        "match_status": MatchStatus.needs_review.value,
    }

    find_one_side_effect = [
        {"_id": selected_athlete_id, "first_name": "Jan", "last_name": "Novak", "teams": []},
        selected_result,
        {"_id": selected_athlete_id, "first_name": "Jan", "last_name": "Novak", "teams": []},
    ]

    with (
        patch("app.services.admin.athletes_collection") as mock_athletes,
        patch("app.services.admin.results_collection") as mock_results,
        patch(
            "app.services.admin.decide_athlete_match",
            AsyncMock(
                return_value={
                    "match_status": MatchStatus.matched,
                    "match_reason": "name_plus_birth_year",
                    "matched_athlete": {"_id": selected_athlete_id},
                }
            ),
        ),
    ):
        mock_athletes.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_athletes.update_one = AsyncMock(return_value=MagicMock())
        mock_results.find_one = AsyncMock(side_effect=find_one_side_effect[:2])
        mock_results.update_one = AsyncMock(return_value=MagicMock())
        mock_results.find.return_value.to_list = AsyncMock(return_value=[review_result])

        response = asyncio.run(
            assign_result_to_athlete(str(result_id), str(selected_athlete_id))
        )

    assert response["ok"] is True
    assert response["auto_reassigned"] == 1
    assert mock_results.update_one.await_count >= 2


def test_auto_reassigned_name_plus_team_enriches_missing_fscode_only():
    result_id = ObjectId()
    selected_athlete_id = ObjectId()
    rematched_result_id = ObjectId()
    rematched_athlete_id = ObjectId()

    selected_result = {
        "_id": result_id,
        "imported_athlete": {
            "first_name": "Jan",
            "last_name": "Novak",
            "birth_year": 2001,
            "fscode": "12345",
        },
        "team": "SDH Lhota",
    }
    review_result = {
        "_id": rematched_result_id,
        "imported_athlete": {
            "first_name": "Petr",
            "last_name": "Maly",
            "birth_year": 2002,
            "fscode": "54321",
        },
        "team": "SDH Lhota",
        "match_status": MatchStatus.needs_review.value,
    }

    find_one_side_effect = [
        {"_id": selected_athlete_id, "first_name": "Jan", "last_name": "Novak", "teams": []},
        selected_result,
        {"_id": selected_athlete_id, "first_name": "Jan", "last_name": "Novak", "teams": []},
    ]

    rematched_athlete = {
        "_id": rematched_athlete_id,
        "first_name": "Petr",
        "last_name": "Maly",
        "teams": ["SDH Lhota"],
        "fs_codes": [],
        "fscode": None,
        "birth_year": 2002,
    }

    with (
        patch("app.services.admin.athletes_collection") as mock_athletes,
        patch("app.services.admin.results_collection") as mock_results,
        patch(
            "app.services.admin.decide_athlete_match",
            AsyncMock(
                side_effect=[
                    {
                        "match_status": MatchStatus.matched,
                        "match_reason": "name_plus_birth_year",
                        "matched_athlete": rematched_athlete,
                    }
                ]
            ),
        ),
    ):
        mock_athletes.find_one = AsyncMock(side_effect=find_one_side_effect)
        mock_athletes.update_one = AsyncMock(return_value=MagicMock())
        mock_results.find_one = AsyncMock(side_effect=find_one_side_effect[:2])
        mock_results.update_one = AsyncMock(return_value=MagicMock())
        mock_results.find.return_value.to_list = AsyncMock(return_value=[review_result])

        response = asyncio.run(
            assign_result_to_athlete(str(result_id), str(selected_athlete_id))
        )

    assert response["auto_reassigned"] == 1
    rematch_enrichment_call = mock_athletes.update_one.await_args_list[0]
    assert rematch_enrichment_call.args[0] == {"_id": rematched_athlete_id}
    assert rematch_enrichment_call.args[1]["$set"]["fscode"] == "54321"
    assert rematch_enrichment_call.args[1]["$addToSet"]["fs_codes"] == "54321"
    assert "updated_at" in rematch_enrichment_call.args[1]["$set"]
    assert rematch_enrichment_call.args[1]["$addToSet"]["teams"] == "SDH Lhota"
