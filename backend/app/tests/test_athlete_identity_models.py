from app.models.athlete import AthleteInDB
from app.services.athlete_identity import normalize_athlete_document


def test_athlete_model_and_helper_share_identity_normalization_rules():
    raw = {
        "_id": "athlete-1",
        "first_name": "Jan",
        "last_name": "Novak",
        "teams": ["SDH Lhota", "sdh lhota", "  ", None],
        "fs_codes": ["12345", 12345, "  ", None],
    }

    normalized_doc = normalize_athlete_document(raw)
    athlete = AthleteInDB.model_validate(raw)

    assert normalized_doc is not None
    assert normalized_doc["teams"] == ["SDH Lhota"]
    assert normalized_doc["fs_codes"] == ["12345"]
    assert athlete.teams == normalized_doc["teams"]
    assert athlete.fs_codes == normalized_doc["fs_codes"]


def test_athlete_normalization_does_not_backfill_teams_from_legacy_team_field():
    raw = {
        "_id": "athlete-2",
        "first_name": "Jan",
        "last_name": "Novak",
        "team": "SDH Lhota",
    }

    normalized_doc = normalize_athlete_document(raw)
    athlete = AthleteInDB.model_validate(raw)

    assert normalized_doc is not None
    assert "team" not in normalized_doc
    assert normalized_doc["teams"] == []
    assert athlete.teams == []


def test_athlete_normalization_does_not_backfill_fs_codes_from_legacy_fscode_field():
    raw = {
        "_id": "athlete-3",
        "first_name": "Jan",
        "last_name": "Novak",
        "fscode": "12345",
    }

    normalized_doc = normalize_athlete_document(raw)
    athlete = AthleteInDB.model_validate(raw)

    assert normalized_doc is not None
    assert "fscode" not in normalized_doc
    assert normalized_doc["fs_codes"] == []
    assert athlete.fs_codes == []
