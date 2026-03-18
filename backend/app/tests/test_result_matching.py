import asyncio
from unittest.mock import AsyncMock, patch

from app.models.result import MatchStatus
from app.services.result_matching import decide_athlete_match


def test_decide_athlete_match_matches_same_name_and_birth_year_with_different_fscode():
    athlete = {"_id": "athlete-1", "birth_year": 1997, "fs_codes": ["11111"]}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1997,
                fscode="22222",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.matched
    assert decision["match_reason"] == "name_plus_birth_year"
    assert decision["matched_athlete"] == athlete


def test_decide_athlete_match_matches_same_name_and_birth_year_with_different_team():
    athlete = {"_id": "athlete-2", "birth_year": 1997, "teams": ["Bukovice"]}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1997,
                fscode="33333",
                team="Olesnice",
            )
        )

    assert decision["match_status"] == MatchStatus.matched
    assert decision["match_reason"] == "name_plus_birth_year"


def test_decide_athlete_match_does_not_match_same_name_with_conflicting_birth_year():
    athlete = {"_id": "athlete-3", "birth_year": 1997}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1998,
                fscode="33333",
                team="Olesnice",
            )
        )

    assert decision["match_status"] == MatchStatus.unmatched
    assert decision["match_reason"] == "name_match_conflicting_birth_year_create_new"
    assert decision["matched_athlete"] is None


def test_decide_athlete_match_same_name_without_birth_year_requires_review():
    athlete = {"_id": "athlete-4", "teams": ["Bukovice"]}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=None,
                fscode="44444",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.needs_review
    assert decision["match_reason"] == "name_only_missing_birth_year"
    assert decision["matched_athlete"] is None


def test_decide_athlete_match_same_name_and_team_without_birth_year_matches_unique_candidate():
    athlete = {"_id": "athlete-4b", "teams": ["Bukovice"]}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=None,
                fscode="44444",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.matched
    assert decision["match_reason"] == "name_plus_team"
    assert decision["matched_athlete"] == athlete


def test_decide_athlete_match_same_name_and_team_without_birth_year_requires_review_when_ambiguous():
    athlete_a = {"_id": "athlete-4c", "teams": ["Bukovice"]}
    athlete_b = {"_id": "athlete-4d", "teams": ["Bukovice"]}
    mocked_find = AsyncMock(return_value=[athlete_a, athlete_b])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=None,
                fscode="44444",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.needs_review
    assert decision["match_reason"] == "multiple_name_plus_team_candidates"
    assert decision["matched_athlete"] is None


def test_decide_athlete_match_keeps_single_athlete_when_multiple_fs_codes_exist():
    athlete = {
        "_id": "athlete-5",
        "birth_year": 1997,
        "fs_codes": ["11111", "22222"],
        "teams": ["Bukovice", "Olesnice"],
    }
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1997,
                fscode="33333",
                team="Lubna",
            )
        )

    assert decision["match_status"] == MatchStatus.matched
    assert decision["match_reason"] == "name_plus_birth_year"
    assert decision["matched_athlete"] == athlete


def test_decide_athlete_match_birth_year_uses_team_when_athlete_birth_year_missing():
    athlete = {"_id": "athlete-5b", "birth_year": None, "teams": ["Bukovice"]}
    mocked_find = AsyncMock(return_value=[athlete])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1997,
                fscode="33333",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.matched
    assert decision["match_reason"] == "name_plus_team"
    assert decision["matched_athlete"] == athlete


def test_decide_athlete_match_multiple_candidates_with_same_name_and_birth_year_require_review():
    athlete_a = {"_id": "athlete-6", "birth_year": 1997, "fs_codes": ["11111"]}
    athlete_b = {"_id": "athlete-7", "birth_year": 1997, "fs_codes": ["22222"]}
    mocked_find = AsyncMock(return_value=[athlete_a, athlete_b])

    with patch("app.services.result_matching._find_athletes", mocked_find):
        decision = asyncio.run(
            decide_athlete_match(
                first_name="Jakub",
                last_name="Smida",
                birth_year=1997,
                fscode="33333",
                team="Bukovice",
            )
        )

    assert decision["match_status"] == MatchStatus.needs_review
    assert decision["match_reason"] == "multiple_name_plus_birth_year_candidates"
    assert decision["matched_athlete"] is None
