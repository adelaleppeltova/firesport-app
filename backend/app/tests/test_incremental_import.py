import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.result import MatchStatus
from app.services import data_import


@pytest.fixture
def import_collections(monkeypatch):
    def collection():
        documents = {}

        def matches(doc, query):
            return all(doc.get(key) == value for key, value in query.items() if key != "name") and (
                "name" not in query or isinstance(query["name"], dict) or doc.get("name") == query["name"]
            )

        def find(query):
            found = [deepcopy(doc) for doc in documents.values() if matches(doc, query)]
            cursor = MagicMock(to_list=AsyncMock(return_value=found))
            cursor.limit.return_value = cursor
            cursor.__aiter__.return_value = found
            return cursor

        async def find_one(query):
            return next((deepcopy(doc) for doc in documents.values() if matches(doc, query)), None)

        async def insert(doc):
            assert doc["_id"] not in documents
            documents[doc["_id"]] = deepcopy(doc)

        return MagicMock(find=find, find_one=AsyncMock(side_effect=find_one),
                         insert_one=AsyncMock(side_effect=insert), documents=documents)

    collections = {name: collection() for name in ("competitions", "categories", "results")}
    for name, mock in collections.items():
        monkeypatch.setattr(data_import, f"{name}_collection", mock)
    return collections


def _race():
    return {
        "source_file": "https://example.test/races/123",
        "competition": {
            "name": "Pohár",
            "date": "2026-08-01",
            "place": "Lhota",
            "categories": [{
                "name": "Muži",
                "discipline": "100m",
                "results": [
                    {"first_name": "JAN", "last_name": "Novák", "birth_year": 2000,
                     "team": "SDH Lhota", "start_number": "17", "final_time": 16.34,
                     "final_status": "valid", "rank": 1},
                    {"first_name": "Petr", "last_name": "Malý", "start_number": "18",
                     "final_status": "missing"},
                ],
            }],
        },
    }


def test_repeat_race_preserves_manual_assignment_and_quality_flag(import_collections):
    from bson import ObjectId

    race = _race()
    with patch.object(data_import, "decide_athlete_match", AsyncMock(return_value={
        "match_status": MatchStatus.unmatched, "match_reason": "no_match", "matched_athlete": None,
    })) as decide:
        first = asyncio.run(data_import.DataImporter().import_from_dict(race))
        assert first["total_imported"] == first["results_unmatched"] == 2
        assert first["athletes_created_new"] == 0
        docs = import_collections["results"].documents
        original = next(iter(docs.values()))
        assert "athlete" not in original
        assert original["imported_athlete"]["first_name"] == "JAN"
        original.update(athlete=ObjectId(), match_status="matched",
                        match_reason="manual_admin_assignment", quality_flag="suspicious")
        snapshot = deepcopy(docs)
        decide.reset_mock()

        second = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert second["competitions_created"] == second["results_created"] == 0
    assert second["results_duplicates_skipped"] == 2
    assert second["errors"] == []
    assert len(import_collections["competitions"].documents) == 1
    assert docs == snapshot
    decide.assert_not_awaited()


def test_corrected_result_is_reported_as_conflict_and_existing_document_is_preserved(import_collections):
    race = _race()
    with patch.object(data_import, "decide_athlete_match", AsyncMock(return_value={
        "match_status": MatchStatus.needs_review, "match_reason": "shared_fscode", "matched_athlete": None,
    })):
        first = asyncio.run(data_import.DataImporter().import_from_dict(race))
    docs = import_collections["results"].documents
    assert first["results_needs_review"] == 2
    assert all("athlete" not in result for result in docs.values())

    snapshot = deepcopy(docs)
    race["competition"]["categories"][0]["results"][0]["final_time"] = 17.00
    with patch.object(data_import, "decide_athlete_match", new_callable=AsyncMock) as decide:
        second = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert second["results_created"] == 0
    assert second["results_duplicates_skipped"] == 1
    assert "Nejednoznačný řádek" in second["errors"][0]
    assert docs == snapshot
    decide.assert_not_awaited()


def test_conflicting_race_source_is_reported_without_creating_another_race(import_collections):
    race = _race()
    race["competition"]["categories"] = []
    first = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert first["competitions_created"] == 1

    race["source_file"] = "https://example.test/races/456"
    second = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert second["competitions_created"] == 0
    assert "Nejednoznačná identita závodu" in second["errors"][0]
    assert len(import_collections["competitions"].documents) == 1


def test_automatic_file_import_reuses_the_incremental_importer(import_collections, monkeypatch, tmp_path):
    import json

    from scripts import load_data

    race_path = tmp_path / "2026" / "lhota"
    race_path.mkdir(parents=True)
    (race_path / "race.json").write_text(json.dumps(_race()), encoding="utf-8")
    monkeypatch.setattr(load_data, "DATA_DIR", tmp_path)

    with patch.object(data_import, "decide_athlete_match", AsyncMock(return_value={
        "match_status": MatchStatus.unmatched, "match_reason": "no_match", "matched_athlete": None,
    })):
        first = asyncio.run(load_data.load_all_json_files())
        second = asyncio.run(load_data.load_all_json_files())

    assert first["results_created"] == 2
    assert second["results_duplicates_skipped"] == 2
    for collection in import_collections.values():
        collection.delete_many.assert_not_called()


def test_identical_rows_within_one_file_are_reported(import_collections):
    race = _race()
    rows = race["competition"]["categories"][0]["results"]
    rows[:] = [rows[0], rows[0]]

    stats = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert stats["results_created"] == stats["results_duplicates_skipped"] == 0
    assert len(stats["errors"]) == 2
    assert not import_collections["results"].documents


def test_import_preserves_original_team_and_stores_numeric_start_number(import_collections):
    race = _race()
    rows = race["competition"]["categories"][0]["results"]
    rows[0].update(team="SDH KAMENEC U POLIČKY", start_number=" 017 ")
    rows[1]["start_number"] = ""
    with patch.object(data_import, "decide_athlete_match", AsyncMock(return_value={
        "match_status": MatchStatus.unmatched, "match_reason": "no_match", "matched_athlete": None,
    })) as match:
        stats = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert stats["errors"] == []
    first, second = import_collections["results"].documents.values()
    assert first["team"] == "Kamenec u Poličky"
    assert first["imported_team"] == "SDH KAMENEC U POLIČKY"
    assert first["start_number"] == 17
    assert second["start_number"] is None
    assert match.await_args_list[0].kwargs["team"] == "Kamenec u Poličky"


@pytest.mark.parametrize("value", ["17A", 17.5, True])
def test_invalid_start_number_is_reported(value):
    with pytest.raises(ValueError, match="Neplatné startovní číslo"):
        data_import.DataImporter._parse_start_number(value)
