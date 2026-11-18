"""Regression coverage for name quarantine and comparable finish times."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId

from app.api.v1.athlete_anomalies_router import comparable_scores
from app.extraction.youth_pdf import parse_result
from app.extraction.youth_pdf_tables import SourceRow
from app.ml.anomaly_config import category_performance_group
from app.models.result import FinalResult, TimeAttempt
from app.result_values import (
    invalid_name_fields,
    select_performance_series,
    valid_final_time,
)
from app.services import data_import
from app.services.performance_indicator import calculate_performance_indicator
from app.services.performance_stability_service import evaluate_performance_stability
from scripts.audit_result_names import audit_result_names
from scripts.fix_final_times import inspect_times


@pytest.mark.parametrize(
    "invalid", [None, "", "  ", "-", "DNS", "neznámý", "NESTARTUJE", "001", "J4n"]
)
def test_incomplete_or_invalid_name_never_reaches_matching_or_mongo(
    monkeypatch, invalid
):
    # Mocks without read/write methods: even attempting DB access fails this regression.
    for collection in (
        "competitions_collection",
        "categories_collection",
        "results_collection",
    ):
        blocked = Mock()
        monkeypatch.setattr(data_import, collection, blocked)
    match = AsyncMock()
    monkeypatch.setattr(data_import, "decide_athlete_match", match)
    importer = data_import.DataImporter()
    create_race = AsyncMock(wraps=importer._import_competition)
    monkeypatch.setattr(importer, "_import_competition", create_race)

    stats = asyncio.run(
        importer.import_from_dict(
            {
                "competition": {
                    "categories": [
                        {
                            "name": "První",
                            "results": [
                                {"first_name": "Émilie", "last_name": "D’Ávila"}
                            ],
                        },
                        {
                            "name": "Druhá",
                            "results": [
                                {
                                    "first_name": "Jan",
                                    "last_name": invalid,
                                    "fscode": "1234",
                                },
                                {"first_name": invalid, "last_name": "Novák"},
                            ],
                        },
                    ]
                }
            }
        )
    )
    assert (
        stats["competitions_created"]
        == stats["categories_created"]
        == stats["results_created"]
        == 0
    )
    assert len(stats["errors"]) == 2
    assert "last_name" in stats["errors"][0] and "first_name" in stats["errors"][1]
    create_race.assert_not_awaited()
    match.assert_not_awaited()
    for collection in (
        "competitions_collection",
        "categories_collection",
        "results_collection",
    ):
        assert not getattr(data_import, collection).mock_calls

    asyncio.run(
        importer._import_result({"first_name": "Jan", "fscode": "1234"}, "", "")
    )
    assert len(stats["errors"]) == 3
    match.assert_not_awaited()


@pytest.mark.parametrize(
    ("cells", "verified", "time", "status", "provenance", "cause"),
    [
        (
            {"first": "20,32", "second": "19,38"},
            True,
            19.38,
            "valid",
            "derived_from_attempts",
            None,
        ),
        (
            {"first": "18,30 (NP)", "second": "19,21"},
            True,
            19.21,
            "valid",
            "derived_from_attempts",
            None,
        ),
        (
            {"first": "19,38", "second": "NP"},
            False,
            None,
            "missing",
            None,
            "best_attempt_rule_unverified",
        ),
        ({"final": "21,62"}, True, 21.62, "valid", "published", None),
        (
            {"final": "21,62", "second": "20,10"},
            True,
            21.62,
            "valid",
            "published",
            None,
        ),
        (
            {"final": "DQ", "second": "20,10"},
            True,
            None,
            "invalid",
            None,
            "published_invalid",
        ),
        (
            {"first": "NP", "second": "DNS"},
            True,
            None,
            "invalid",
            None,
            "all_attempts_invalid",
        ),
        ({}, True, None, "missing", None, "insufficient_published_attempts"),
        (
            {"first": "DNS"},
            True,
            None,
            "missing",
            None,
            "insufficient_published_attempts",
        ),
    ],
)
def test_finish_time_cases(cells, verified, time, status, provenance, cause):
    name = {"name": "Van der Veen Anna"}
    location = {"page": 2, "table": 1, "row": 1}
    notices = []
    row, reason = parse_result(
        SourceRow("Dorky", {**name, **cells}, True, (1, 1, 4, 4)),
        location,
        notices,
        best_attempt_rule="Ověřené pravidlo závodu" if verified else None,
    )
    assert reason is None
    assert row["last_name"] == "Van der Veen"
    assert (row["final_time"], row["final_status"], row.get("final_time_source")) == (
        time,
        status,
        provenance,
    )
    assert location.get("final_time_reason") == cause
    if cells.get("final") and cells.get("second") == "20,10":
        assert "final_time_conflict" in location
        assert list(
            inspect_times({"competition": {"categories": [{"results": [row]}]}})
        )[0]["conflict"]


def test_import_preflight_checks_claims_of_time_derivation():
    row = {
        "first_name": "Anna",
        "last_name": "Nováková",
        "final_status": "valid",
        "final_time": 18.0,
        "final_time_source": "derived_from_attempts",
        "times": [{"try": 1, "time": 18.0, "status": "valid"}],
    }
    doc = {"categories": [{"name": "Dorky", "discipline": "100m", "results": [row]}]}
    assert data_import.DataImporter.preflight_results(doc) == []
    for updated in ({"final_time": 17.0}, {"final_status": "missing"}):
        doc["categories"][0]["results"] = [dict(row, **updated)]
        assert len(data_import.DataImporter.preflight_results(doc)) == 1
    doc["categories"][0].update(discipline="100mPHP", results=[row])
    assert len(data_import.DataImporter.preflight_results(doc)) == 1


def test_stats_disagree_only_with_explicit_invalid_or_mixed_data():
    race_date = datetime(2026, 6, 13)
    rows = [
        {"category": "a", "final_time": 18.2, "final_time_status": "valid"},
        {"category": "a", "final_time": "19,0"},  # legacy numeric result
        {"category": "a", "final_time": 1, "final_time_status": "missing"},
        {"category": "a", "final_time": 2, "final_time_status": "invalid"},
        {"category": "a", "final_time": 998, "final_time_status": "valid"},
        {"category": "a", "final_time": float("nan"), "final_time_status": "valid"},
        {"category": "b", "final_time": 9.2, "final_time_status": "valid"},
        {"category": "c", "final_time": 12.0, "final_time_status": "valid"},
    ]
    categories = {
        "a": {"_id": "a", "name": "Mladší dorostenky", "discipline": "100m"},
        "b": {"_id": "b", "name": "Mladší dorostenky", "discipline": "60m"},
        "c": {"_id": "c", "name": "Mladší dorostenky"},
    }
    selected, discipline, legacy = select_performance_series(rows, categories)
    assert (discipline, legacy) == ("100m", None)
    assert [valid_final_time(row) for row in selected] == [
        18.2,
        19.0,
        None,
        None,
        None,
        None,
    ]
    assert select_performance_series(rows, categories, "60m")[0] == [rows[-2]]
    assert select_performance_series([rows[-1]], categories) == ([rows[-1]], None, "c")
    entries = [dict(row, competition_date=race_date) for row in selected]
    assert evaluate_performance_stability(entries)["n_used"] == 2
    assert len(calculate_performance_indicator(entries).recent_results) == 2
    assert len({category_performance_group(cat) for cat in categories.values()}) == 3


def test_api_models_preserve_provenance_and_status_with_legacy_fallback():
    assert FinalResult.model_validate({"final_time": 19.0}).final_time_status == "valid"
    assert (
        FinalResult.model_validate(
            {"final_time": 19.0, "final_time_status": "missing"}
        ).final_time
        is None
    )
    assert (
        FinalResult.model_validate({"final_time_status": "invalid"}).final_time_status
        == "invalid"
    )
    assert FinalResult.model_validate({}).final_time_status == "missing"
    assert TimeAttempt.model_validate({"time": 999, "status": "invalid"}).time is None
    assert (
        FinalResult.model_validate(
            {
                "final_time": 19.0,
                "final_time_status": "valid",
                "final_time_source": "derived_from_attempts",
            }
        ).final_time_source
        == "derived_from_attempts"
    )


def test_saved_anomalies_with_mixed_or_invalid_times_do_not_feed_stats():
    rows = {
        number: {"final_time": number, "final_time_status": "valid"}
        for number in (10, 18, 19, 20)
    }
    rows[20]["final_time_status"] = "missing"
    scores = [
        {"result_id": 10, "category_group": "old", "final_time": 10},
        {"result_id": 18, "category_group": "old", "final_time": 18},
        {"result_id": 19, "category_group": "zena", "final_time": 19},
        {"result_id": 20, "category_group": "stale", "final_time": 20},
    ]
    groups = {10: "60m:zena", 18: "zena", 19: "zena", 20: "zena"}
    selected, group = comparable_scores(scores, rows, groups, "zena")
    assert group == "zena" and [score["result_id"] for score in selected] == [19]
    assert comparable_scores(scores, rows, groups, "old")[0] == []


class ReadCursor:
    def __init__(self, rows):
        self.rows = iter(rows)

    def batch_size(self, _size):
        return self

    def __iter__(self):
        return self.rows

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def test_mongo_audit_uses_projection_and_tracks_related_references():
    athlete = ObjectId()
    result_id = ObjectId()
    db = {
        "athletes": Mock(spec=["find"]),
        "results": Mock(spec=["find"]),
    }
    db["athletes"].find.return_value = [
        {"_id": athlete, "first_name": "Áda", "last_name": "Černá"}
    ]
    db["results"].find.return_value = ReadCursor(
        [
            {
                "_id": result_id,
                "athlete": str(athlete),
                "imported_athlete": {"first_name": None, "last_name": "Černá"},
            },
            {
                "_id": ObjectId(),
                "athlete": athlete,
            },  # legitimate legacy row linked to a complete profile
            {
                "_id": ObjectId(),
                "imported_athlete": {"first_name": "Eva", "last_name": ""},
            },
        ]
    )
    report = audit_result_names(db, batch_size=2)
    assert report["scanned_results"] == 3
    assert report["affected_results"] == 2
    assert report["linked_athletes"] == {str(athlete): 2}
    assert report["results"][0]["result_id"] == str(result_id)
    assert report["results"][0]["invalid_fields"] == {
        "imported_athlete": ["first_name"]
    }
    assert report["results"][1]["athlete_link"] == "unlinked"
    assert invalid_name_fields({"first_name": "Émilie", "last_name": "D’Ávila"}) == ()


def test_athlete_profile_compares_only_selected_discipline(monkeypatch):
    from app.services import athletes

    athlete_id, hundred, sixty = ObjectId(), ObjectId(), ObjectId()
    rows = [
        {"category": hundred, "final_time_status": "valid", "final_time": 18.2},
        {"category": hundred, "final_time_status": "invalid", "final_time": 2.1},
        {"category": hundred, "final_time_status": "missing", "final_time": 3.4},
        {"category": sixty, "final_time_status": "valid", "final_time": 9.2},
    ]
    categories = [
        {"_id": hundred, "discipline": "100m"},
        {"_id": sixty, "discipline": "60m"},
    ]
    monkeypatch.setattr(
        athletes,
        "athletes_collection",
        Mock(
            find_one=AsyncMock(
                return_value={
                    "_id": athlete_id,
                    "first_name": "Jan",
                    "last_name": "Novák",
                }
            )
        ),
    )
    monkeypatch.setattr(
        athletes,
        "results_collection",
        Mock(
            find=Mock(return_value=Mock(to_list=AsyncMock(return_value=rows))),
        ),
    )
    monkeypatch.setattr(
        athletes,
        "categories_collection",
        Mock(
            find=Mock(return_value=Mock(to_list=AsyncMock(return_value=categories))),
        ),
    )
    monkeypatch.setattr(
        athletes, "get_athlete_competition_count", AsyncMock(return_value=2)
    )
    profile = asyncio.run(athletes.get_athlete_profile_service(str(athlete_id)))
    assert profile.best_time == 18.2
    sixty_profile = asyncio.run(
        athletes.get_athlete_profile_service(str(athlete_id), discipline="60m")
    )
    assert sixty_profile.best_time == 9.2
