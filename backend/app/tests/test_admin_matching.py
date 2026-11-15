import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from app.models.result import MatchStatus
from app.services import admin


def _result(**fields):
    return {
        "_id": ObjectId(),
        "imported_athlete": {"first_name": "Test", "last_name": "Příklad", "birth_year": 2000},
        "team": "Testovací tým",
        "match_status": MatchStatus.unmatched.value,
        **fields,
    }


def test_manual_assignment_updates_only_selected_result_with_audit():
    profile = {"_id": ObjectId()}
    selected = _result()
    with (
        patch.object(admin, "athletes_collection") as athletes,
        patch.object(admin, "results_collection") as results,
    ):
        athletes.find_one = AsyncMock(return_value=profile)
        results.find_one = AsyncMock(return_value=selected)
        results.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        response = asyncio.run(admin.assign_result_to_athlete(
            str(selected["_id"]), str(profile["_id"]), admin_id="admin-id",
        ))
    assert response["auto_reassigned"] == 0
    results.find.assert_not_called()
    results.update_one.assert_awaited_once()
    predicate, change = results.update_one.await_args.args
    assert predicate["athlete"] is None
    assert predicate["_id"] == selected["_id"]
    assert change["$set"]["match_reason"] == "manual_admin_assignment"
    assert change["$push"]["manual_identity_history"]["admin_id"] == "admin-id"


@pytest.mark.parametrize("already_assigned", [True, False])
def test_manual_assignment_rejects_resolved_or_changed_row(already_assigned):
    profile, selected = {"_id": ObjectId()}, _result()
    if already_assigned:
        selected["athlete"] = ObjectId()
    with (
        patch.object(admin, "athletes_collection") as athletes,
        patch.object(admin, "results_collection") as results,
    ):
        athletes.find_one = AsyncMock(return_value=profile)
        results.find_one = AsyncMock(return_value=selected)
        results.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
        with pytest.raises(HTTPException) as exc:
            asyncio.run(admin.assign_result_to_athlete(str(selected["_id"]), str(profile["_id"])))
    assert exc.value.status_code == 409
    assert results.update_one.await_count == int(not already_assigned)


@pytest.mark.parametrize("mode", ["ok", "conflict", "different_group", "same_competition", "unassigned"])
def test_bulk_assigns_only_explicit_rows_and_reports_stale_updates(mode):
    athlete_id = ObjectId()
    one = _result(competition=ObjectId())
    two = _result(competition=one["competition"] if mode == "same_competition" else ObjectId())
    if mode == "different_group":
        two["team"] = "Jiný tým"
    if mode == "unassigned":
        two["match_reason"] = "manual_admin_unassignment"
    decision = {
        "candidates": [{
            "profile": {"_id": athlete_id}, "strong": [],
            "supporting": ["exact_name", "birth_year"], "conflicts": ["fscode"] if mode == "conflict" else [],
        }],
        "match_reason": "insufficient_identity",
    }
    ids = [str(doc["_id"]) for doc in (one, two)]
    with (
        patch.object(admin, "results_collection") as results,
        patch.object(admin, "_review_decision", AsyncMock(return_value=decision)),
    ):
        results.find.return_value.to_list = AsyncMock(return_value=[one, two])
        results.update_one = AsyncMock(side_effect=[MagicMock(modified_count=1), MagicMock(modified_count=0)])
        if mode != "ok":
            with pytest.raises(HTTPException) as exc:
                asyncio.run(admin.assign_result_group(ids, str(athlete_id), admin_id="admin"))
            assert exc.value.status_code == 409
            results.update_one.assert_not_awaited()
        else:
            assert asyncio.run(admin.assign_result_group(ids, str(athlete_id), admin_id="admin")) == {
                "assigned": ids[:1], "skipped": ids[1:],
            }
            assert [str(call.args[0]["_id"]) for call in results.update_one.await_args_list] == ids


def test_manual_profile_creation_retains_admin_assignment():
    candidate = _result()
    athlete_id = ObjectId()
    with (
        patch.object(admin, "results_collection") as results,
        patch.object(admin, "athletes_collection") as athletes,
    ):
        results.find_one = AsyncMock(return_value=candidate)
        results.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        athletes.insert_one = AsyncMock(return_value=MagicMock(inserted_id=athlete_id))
        response = asyncio.run(admin.create_athlete_from_result(str(candidate["_id"])))

    assert response["athlete_id"] == str(athlete_id)
    assert athletes.insert_one.await_args.args[0]["birth_year"] == 2000
    assert results.update_one.await_args.args[1]["$set"]["match_reason"] == "manual_admin_create_athlete"
    results.find.assert_not_called()


@pytest.mark.parametrize("state", ["verified", "already_mapped", "other_owner", "automatic"])
def test_external_verification_is_a_separate_admin_action(state):
    athlete_id = ObjectId()
    doc = _result(
        athlete=athlete_id,
        match_reason="name_plus_fscode" if state == "automatic" else "manual_admin_assignment",
        external_identity={"provider": "example.cz", "person_id": "42", "evidence_url": "https://example.cz/p/42"},
    )
    with (
        patch.object(admin, "results_collection") as results,
        patch.object(admin, "athletes_collection") as athletes,
        patch.object(admin, "external_identities") as external,
    ):
        results.find_one = AsyncMock(return_value=doc)
        athletes.find_one = AsyncMock(return_value={"_id": athlete_id})
        external.find_one = AsyncMock(return_value={"athlete_id": athlete_id if state == "already_mapped" else ObjectId()})
        external.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("duplicate") if state in ("already_mapped", "other_owner") else None,
        )

        def verify():
            return asyncio.run(admin.verify_result_external_identity(
                str(doc["_id"]), str(athlete_id), "example.cz", "42", admin_id="admin",
            ))

        if state in ("other_owner", "automatic"):
            with pytest.raises(HTTPException) as exc:
                verify()
            assert exc.value.status_code == 409
        else:
            assert verify() == {"ok": True}
        if state == "automatic":
            external.insert_one.assert_not_awaited()
        else:
            assert external.insert_one.await_args.args[0]["_id"] == "example.cz:42"
        results.update_one.assert_not_called()


def test_review_queue_includes_unresolved_import_with_original_identity_and_reason():
    doc = _result(
        imported_athlete={"first_name": "TEST", "last_name": "Příklad", "birth_year": 2000, "fscode": "12345"},
        match_reason="no_match",
        imported_team="SDH TESTOVACÍ TÝM",
    )
    with patch.object(admin, "results_collection") as results:
        results.find.return_value.sort.return_value.to_list = AsyncMock(return_value=[doc])
        response = asyncio.run(admin.get_review_results())

    assert results.find.call_args.args[0]["match_status"] == {"$in": ["needs_review", "unmatched"]}
    assert response.summary.unmatched == 1
    assert response.items[0].imported_athlete.first_name == "TEST"
    assert response.items[0].imported_athlete.fscode == "12345"
    assert response.items[0].match_reason == "no_match"
    assert response.items[0].team == "SDH TESTOVACÍ TÝM"
    assert response.items[0].group_id


def test_review_candidates_rank_identifier_and_explain_conflicts():
    from app.services import result_matching
    from app.tests.test_result_matching import mock_find

    doc = _result(imported_athlete={
        "first_name": "Test", "last_name": "Příklad", "birth_year": 2000, "fscode": "12345",
    })
    owner, namesake = ObjectId(), ObjectId()
    profiles = [
        {"_id": namesake, "first_name": "Test", "last_name": "Příklad", "birth_year": 2000,
         "teams": ["Testovací tým"]},
        {"_id": owner, "first_name": "Test", "last_name": "Příklad", "birth_year": 2002,
         "fs_codes": ["12345"]},
    ]
    with (
        patch.object(admin.results_collection, "find_one", AsyncMock(return_value=doc)),
        patch.object(result_matching.athletes_collection, "find", side_effect=mock_find(profiles)),
    ):
        response = asyncio.run(admin.get_result_candidates(str(doc["_id"])))
    assert [item.athlete_id for item in response.items] == [str(owner), str(namesake)]
    assert response.items[0].strong == ["fscode"]
    assert response.items[0].conflicts == ["birth_year"]
    assert response.items[1].supporting == ["exact_name", "birth_year", "historical_team"]
