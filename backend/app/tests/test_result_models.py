from datetime import datetime

from app.models.category import CategoryInDB
from app.models.competition import CompetitionInDB
from app.models.result import ResultAthleteDetail, ResultInDB


def test_result_athlete_detail_accepts_missing_team_and_attempt_number():
    payload = {
        "competition": {
            "_id": "competition-1",
            "name": "MCR",
            "place": "Trebic",
            "date": datetime(2025, 8, 1),
            "league": ["MCR"],
        },
        "category": {
            "_id": "category-1",
            "name": "Zeny",
            "discipline": "100m",
        },
        "date": datetime(2025, 8, 1),
        "team": None,
        "times": [
            {"attempt": None, "time": None, "status": "invalid"},
            {"attempt": 2, "time": 16.42, "status": "valid"},
        ],
        "final_time": 16.42,
        "final_time_status": "valid",
        "rank": 1,
    }

    result = ResultAthleteDetail.model_validate(payload)

    assert result.team is None
    assert result.times[0].attempt is None
    assert result.times[1].attempt == 2


def test_result_in_db_accepts_attempt_without_number():
    payload = {
        "_id": "result-1",
        "athlete": None,
        "competition": CompetitionInDB(
            _id="competition-1",
            name="MCR",
            place="Trebic",
            date=datetime(2025, 8, 1),
            league=["MCR"],
        ),
        "category": CategoryInDB(
            _id="category-1",
            name="Zeny",
            discipline="100m",
        ),
        "date": datetime(2025, 8, 1),
        "team": None,
        "imported_athlete": {
            "first_name": "Eva",
            "last_name": "Nova",
            "birth_year": 2001,
            "fscode": "12345",
        },
        "match_status": "matched",
        "match_reason": None,
        "start_number": 7,
        "times": [
            {"attempt": None, "time": None, "status": "invalid"},
        ],
        "final_time": None,
        "final_time_status": "invalid",
        "rank": None,
        "quality_flag": "ok",
    }

    result = ResultInDB.model_validate(payload)

    assert result.id == "result-1"
    assert result.times[0].attempt is None
