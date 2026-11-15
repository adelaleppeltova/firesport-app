import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
from fastapi import HTTPException

from pymongo.errors import OperationFailure

from app.services import athlete_merge


def test_merge_athletes_moves_results_and_unifies_identity():
    source_id = ObjectId()
    target_id = ObjectId()

    source = {
      "_id": source_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": 1997,
      "fs_codes": ["11111"],
      "teams": ["Bukovice"],
      "is_active": True,
    }
    target = {
      "_id": target_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": 1997,
      "fs_codes": ["22222"],
      "teams": ["Olesnice"],
      "is_active": True,
    }

    with (
        patch("app.services.athlete_merge.athletes_collection") as mock_athletes,
        patch("app.services.athlete_merge.results_collection") as mock_results,
        patch("app.services.athlete_merge.users_collection") as mock_users,
        patch.object(athlete_merge, "anomaly_scores_collection") as scores,
        patch.object(athlete_merge, "external_identities") as external,
    ):
        mock_athletes.find_one = AsyncMock(side_effect=[source, target])
        mock_athletes.update_one = AsyncMock(return_value=MagicMock())
        mock_results.update_many = AsyncMock(return_value=MagicMock(modified_count=4))
        mock_users.update_many = AsyncMock(return_value=MagicMock())
        mock_athletes.update_many = AsyncMock()
        scores.update_many = AsyncMock()
        external.update_many = AsyncMock()

        response = asyncio.run(
            athlete_merge._merge(source_id, target_id, session="transaction")
        )

    assert response["ok"] is True
    assert response["moved_results"] == 4
    for collection, key, value in (
        (mock_users, "athlete_id", str(source_id)),
        (scores, "athlete_id", source_id),
        (external, "athlete_id", source_id),
        (mock_athletes, "merged_into_athlete_id", str(source_id)),
    ):
        call = collection.update_many.await_args
        assert call.args[0] == {key: value}
        assert call.args[1]["$set"][key] == (str(target_id) if isinstance(value, str) else target_id)
        assert call.kwargs == {"session": "transaction"}
    predicate, update = mock_results.update_many.await_args.args
    assert predicate == {"athlete": source_id}
    assert update["$set"]["athlete"] == target_id
    assert set(update["$set"]) == {"athlete", "updated_at"}

    target_update = mock_athletes.update_one.await_args_list[0]
    assert target_update.args[0] == {"_id": target_id}
    assert target_update.args[1]["$set"]["birth_year"] == 1997
    assert target_update.args[1]["$set"]["fs_codes"] == ["11111", "22222"]
    assert target_update.args[1]["$set"]["teams"] == ["Bukovice", "Olesnice"]

    source_update = mock_athletes.update_one.await_args_list[1]
    assert source_update.args[0] == {"_id": source_id}
    assert source_update.args[1]["$set"]["is_active"] is False
    assert source_update.args[1]["$set"]["merged_into_athlete_id"] == str(target_id)


def test_merge_athletes_keeps_existing_birth_year_when_source_missing_it():
    source_id = ObjectId()
    target_id = ObjectId()

    source = {
      "_id": source_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": None,
      "fs_codes": ["11111"],
      "teams": ["Bukovice"],
      "is_active": True,
    }
    target = {
      "_id": target_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": 1997,
      "fs_codes": ["22222"],
      "teams": ["Olesnice"],
      "is_active": True,
    }

    with (
        patch("app.services.athlete_merge.athletes_collection") as mock_athletes,
        patch("app.services.athlete_merge.results_collection") as mock_results,
        patch("app.services.athlete_merge.users_collection") as mock_users,
        patch.object(athlete_merge, "anomaly_scores_collection") as scores,
        patch.object(athlete_merge, "external_identities") as external,
    ):
        mock_athletes.find_one = AsyncMock(side_effect=[source, target])
        mock_athletes.update_one = AsyncMock(return_value=MagicMock())
        mock_results.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
        mock_users.update_many = AsyncMock(return_value=MagicMock())
        mock_athletes.update_many = AsyncMock()
        scores.update_many = AsyncMock()
        external.update_many = AsyncMock()

        asyncio.run(athlete_merge._merge(source_id, target_id, session="transaction"))

    target_update = mock_athletes.update_one.await_args_list[0]
    assert target_update.args[1]["$set"]["birth_year"] == 1997


def test_merge_athletes_rejects_conflicting_birth_year():
    source_id = ObjectId()
    target_id = ObjectId()

    source = {
      "_id": source_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": 1997,
      "fs_codes": ["11111"],
      "teams": ["Bukovice"],
      "is_active": True,
    }
    target = {
      "_id": target_id,
      "first_name": "Jakub",
      "last_name": "Smida",
      "birth_year": 1998,
      "fs_codes": ["22222"],
      "teams": ["Olesnice"],
      "is_active": True,
    }

    with (
        patch("app.services.athlete_merge.athletes_collection") as mock_athletes,
        patch("app.services.athlete_merge.results_collection") as mock_results,
        patch("app.services.athlete_merge.users_collection") as mock_users,
        patch.object(athlete_merge, "anomaly_scores_collection") as scores,
        patch.object(athlete_merge, "external_identities") as external,
    ):
        mock_athletes.find_one = AsyncMock(side_effect=[source, target])
        mock_athletes.update_one = AsyncMock(return_value=MagicMock())
        mock_results.update_many = AsyncMock(return_value=MagicMock(modified_count=0))
        mock_users.update_many = AsyncMock(return_value=MagicMock())
        mock_athletes.update_many = AsyncMock()
        scores.update_many = AsyncMock()
        external.update_many = AsyncMock()

        try:
            asyncio.run(athlete_merge._merge(source_id, target_id, session="transaction"))
            assert False, "Expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 409

    mock_results.update_many.assert_not_awaited()
    mock_athletes.update_one.assert_not_awaited()
    mock_users.update_many.assert_not_awaited()
    scores.update_many.assert_not_awaited()
    external.update_many.assert_not_awaited()


def test_merge_fails_closed_without_transaction_support():
    session = MagicMock(with_transaction=AsyncMock(side_effect=OperationFailure("standalone", code=20)))
    session.__aenter__.return_value = session
    with patch.object(athlete_merge, "db") as database, patch.object(athlete_merge, "_merge") as merge:
        database.client.start_session = AsyncMock(return_value=session)
        try:
            asyncio.run(athlete_merge.merge_athletes_service(str(ObjectId()), str(ObjectId())))
            assert False, "Expected HTTPException"
        except HTTPException as exc:
            assert exc.status_code == 503
    merge.assert_not_called()
