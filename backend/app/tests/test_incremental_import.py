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
        original["manual_identity_history"] = [{
            "reason": original["match_reason"], "athlete_id": original["athlete"], "admin_id": "offline-admin",
        }]
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


def test_verified_lists_keep_two_performances_with_same_start_number(import_collections):
    race = _race()
    first = race["competition"]["categories"][0]
    second = deepcopy(first)
    second["results"][0].update(first_name="Michal", last_name="Nový")
    second["results"] = second["results"][:1]
    race["competition"]["categories"].append(second)
    blocked = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert blocked["competitions_created"] == 0
    assert "výsledkové listiny" in blocked["errors"][0]

    blocks = {0: "hzs", 1: "sdh"}
    match = AsyncMock(return_value={
        "match_status": MatchStatus.needs_review, "match_reason": "insufficient_identity", "matched_athlete": None,
    })
    with patch.object(data_import, "decide_athlete_match", match):
        first_run = asyncio.run(data_import.DataImporter().import_from_dict(race, verified_blocks=blocks))
        second_run = asyncio.run(data_import.DataImporter().import_from_dict(race, verified_blocks=blocks))
    assert first_run["results_created"] == second_run["results_duplicates_skipped"] == 3
    docs = import_collections["results"].documents.values()
    assert {r["result_list_id"] for r in docs} == {"hzs", "sdh"}
    assert all("athlete" not in row for row in docs)


def test_ambiguous_missing_discipline_never_updates_existing_category(import_collections):
    from bson import ObjectId

    categories = import_collections["categories"]
    for discipline in ("100m", "vez"):
        identifier = ObjectId()
        categories.documents[identifier] = {"_id": identifier, "name": "Muži", "discipline": discipline}
    original = deepcopy(categories.documents)
    race = _race()
    race["competition"]["categories"][0].pop("discipline")
    stats = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert stats["results_created"] == 0
    assert "Nejednoznačná kategorie" in stats["errors"][0]
    categories.update_one.assert_not_called()
    assert categories.documents == original


def test_start_number_without_identity_cannot_confirm_duplicate():
    from bson import ObjectId

    imp = data_import.DataImporter()
    comp, cat = map(str, [ObjectId(), ObjectId()])
    row = imp.build_result_row({"start_number": 8, "rank": 1, "final_time": 11}, cat, comp)
    assert imp.assess_result(row, [{**row, "_id": ObjectId()}])[0] == "review"


def test_penalty_reason_and_district_are_not_silently_overwritten():
    from bson import ObjectId

    imp = data_import.DataImporter()
    comp, cat = map(str, [ObjectId(), ObjectId()])
    raw = {"start_number": 8, "rank": 1, "first_name": "Jan", "last_name": "Novák",
           "district": "Okres A", "times": [{"try": 1, "status": "invalid", "invalid_reason": "A"}]}
    row = imp.build_result_row(raw, cat, comp)
    old = {**row, "_id": ObjectId()}
    assert imp.assess_result({**row, "district": "Okres B"}, [old])[0] == "review"
    changed = imp.build_result_row({**raw, "times": [{"try": 1, "status": "invalid", "invalid_reason": "B"}]}, cat, comp)
    assert imp.assess_result(changed, [old])[0] == "review"


def test_same_name_two_people_with_independent_discriminators():
    from bson import ObjectId

    imp = data_import.DataImporter()
    comp, cat = map(str, [ObjectId(), ObjectId()])
    raw = {"start_number": 8, "rank": 1, "first_name": "Jan", "last_name": "Novák", "birth_year": 2000}
    row = imp.build_result_row(raw, cat, comp)
    other = imp.build_result_row({**raw, "start_number": 9, "birth_year": 1995}, cat, comp)
    assert imp.assess_result(row, [{**other, "_id": ObjectId()}]) == ("insert", [])


def test_external_sidecar_preserves_duplicate_logic_and_source_observation(import_collections):
    from app.services.external_identity import ExternalIdentitySidecar, payload_digest

    race = _race()
    sidecar = ExternalIdentitySidecar(
        payload_sha256=payload_digest(race),
        categories={0: {0: {"provider": "example.test", "person_id": "17",
                             "evidence_url": "https://example.test/person/17"}}},
    )
    match = AsyncMock(return_value={
        "match_status": MatchStatus.needs_review, "match_reason": "unverified_external_id", "matched_athlete": None,
    })
    with patch.object(data_import, "decide_athlete_match", match):
        rejected = asyncio.run(data_import.DataImporter().import_from_dict(
            {**race, "source_file": "https://example.test/races/456"}, external_sidecar=sidecar,
        ))
        assert rejected["errors"] and rejected["competitions_created"] == 0
        stats = asyncio.run(data_import.DataImporter().import_from_dict(race, external_sidecar=sidecar))
        assert stats["results_created"] == 2 and not stats["errors"]
        assert match.await_args_list[0].kwargs["external_identity"].key == "example.test:17"
        assert match.await_args_list[1].kwargs["external_identity"] is None
        first, second = import_collections["results"].documents.values()
        assert first["external_identity"]["person_id"] == "17"
        assert first["imported_athlete"]["fscode"] is None
        assert "external_identity" not in second
        match.reset_mock()
        repeated = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert repeated["results_duplicates_skipped"] == 2
    match.assert_not_awaited()
