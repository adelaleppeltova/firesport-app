import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.category_catalog import CATEGORIES
from app.models.result import MatchStatus
from app.services import data_import


@pytest.fixture
def import_collections(monkeypatch):
    def collection():
        documents = {}

        def matches(doc, query):
            for key, value in query.items():
                if key == "$or":
                    if not any(matches(doc, part) for part in value):
                        return False
                    continue
                fields = key.split(".")
                current = doc
                for field in fields[:-1]:
                    current = current.get(field, {})
                actual = current.get(fields[-1])
                if isinstance(value, dict) and "$exists" in value:
                    if (fields[-1] in current) != value["$exists"]:
                        return False
                elif actual != value:
                    return False
            return True

        def find(query):
            found = [deepcopy(doc) for doc in documents.values() if matches(doc, query)]
            cursor = MagicMock(to_list=AsyncMock(return_value=found))
            cursor.limit.return_value = cursor
            cursor.__aiter__.return_value = found
            return cursor

        async def find_one(query, projection=None):
            return next((deepcopy(doc) for doc in documents.values() if matches(doc, query)), None)

        async def insert(doc):
            assert doc["_id"] not in documents
            documents[doc["_id"]] = deepcopy(doc)

        return MagicMock(find=find, find_one=AsyncMock(side_effect=find_one),
                         insert_one=AsyncMock(side_effect=insert), documents=documents)

    collections = {name: collection() for name in ("competitions", "categories", "results", "athletes")}
    collections["categories"].documents.update({category.id: category.document() for category in CATEGORIES})
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
        assert original["imported_athlete"]["first_name"] == "Jan"
        assert original["source_person_name"]["first_name"] == "JAN"
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


def test_import_creates_and_reuses_profile_for_different_team(import_collections, monkeypatch):
    from bson import ObjectId

    from app.services import result_matching

    race = _race()
    del race["competition"]["categories"][0]["results"][1:]
    original_id = ObjectId()
    original = {
        "_id": original_id, "first_name": "Jan", "last_name": "Novák",
        "birth_year": 2000, "teams": ["Bukovice"], "fs_codes": ["12345"],
    }
    profiles = import_collections["athletes"].documents
    profiles[original_id] = original
    race["competition"]["categories"][0]["results"][0]["fscode"] = "12345"

    async def candidates(query, **options):
        return [original] if "first_name" not in query else list(profiles.values())

    monkeypatch.setattr(result_matching, "_find_athletes", candidates)
    monkeypatch.setattr(data_import, "compute_bounds_for_recompute", AsyncMock(return_value={}))
    monkeypatch.setattr(data_import, "compute_quality_flag", AsyncMock(return_value=MagicMock(value="ok")))
    first = asyncio.run(data_import.DataImporter().import_from_dict(race))
    repeat = asyncio.run(data_import.DataImporter().import_from_dict(race))
    race["source_file"] += "4"
    race["competition"]["date"] = "2026-08-02"
    second = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert first["errors"] == repeat["errors"] == second["errors"] == []
    assert first["athletes_created_new"] == first["results_matched"] == 1
    assert first["athletes_existing_matched"] == 0
    assert repeat["results_duplicates_skipped"] == 1
    assert second["athletes_created_new"] == 0 and second["athletes_existing_matched"] == 1
    new_id, = set(profiles) - {original_id}
    assert profiles[new_id]["teams"] == ["Lhota"]
    assert profiles[new_id]["fs_codes"] == [] and profiles[original_id]["fs_codes"] == ["12345"]
    assert {result["athlete"] for result in import_collections["results"].documents.values()} == {new_id}


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


def test_import_refuses_catalog_with_extra_categories(import_collections):
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
    assert "kanonický katalog" in stats["errors"][0]
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


def test_import_uses_shared_categories_and_preserves_historical_and_unsupported_rows(import_collections):
    race = _race()
    categories = race["competition"]["categories"]
    categories[0]["name"] = "MUZI – věk: 19–100"
    categories.append({
        "name": "Ženy", "discipline": "vez",
        "results": [{"first_name": "Jana", "last_name": "Testová", "rank": 3, "final_time": 8.6}],
    })
    categories.append({
        "name": "Mladší žáci a – dívky – od 6 do 8 let", "discipline": "60m",
        "results": [{"first_name": "Jana", "last_name": "Testová", "rank": 7, "birth_year": 2020}],
    })
    before = deepcopy(import_collections["categories"].documents)
    match = AsyncMock(return_value={
        "match_status": MatchStatus.unmatched, "match_reason": "no_match", "matched_athlete": None,
    })
    with patch.object(data_import, "decide_athlete_match", match):
        first = asyncio.run(data_import.DataImporter().import_from_dict(race))
        repeat = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert first["errors"] == repeat["errors"] == []
    assert first["results_created"] == repeat["results_duplicates_skipped"] == 4
    assert first["classification_review_required"] == 1
    assert match.await_count == 2
    imports = list(import_collections["results"].documents.values())
    assert {row["classification_status"] for row in imports} == {"active", "historical", "unsupported"}
    assert len({row["category"] for row in imports if row["classification_status"] == "active"}) == 1
    assert imports[0]["source_category"]["name"] == "MUZI – věk: 19–100"
    assert imports[2]["source_row"]["rank"] == 3
    assert imports[3]["source_category"]["min_age"] == 6
    assert import_collections["categories"].documents == before
    import_collections["categories"].insert_one.assert_not_called()


def test_import_name_quality_preserves_source_and_reimport_identity(import_collections):
    race = _race()
    rows = race["competition"]["categories"][0]["results"]
    rows[0].update(first_name="  petr ", last_name="JUŘINA")
    rows[1].update(first_name=None, last_name="  ", final_time=17, final_status="valid")
    with patch.object(data_import, "decide_athlete_match", wraps=data_import.decide_athlete_match):
        with patch("app.services.result_matching._find_athletes", AsyncMock(return_value=[])):
            first = asyncio.run(data_import.DataImporter().import_from_dict(race))
            again = asyncio.run(data_import.DataImporter().import_from_dict(race))

    assert first["errors"] == again["errors"] == []
    assert again["results_duplicates_skipped"] == 2
    named, incomplete = import_collections["results"].documents.values()
    assert named["imported_athlete"]["last_name"] == "Juřina"
    assert named["source_person_name"] == {"first_name": "  petr ", "last_name": "JUŘINA"}
    assert named["source_row"]["last_name"] == "JUŘINA"
    assert named["match_status"] == "unmatched"
    assert incomplete["source_person_name"] == {"first_name": None, "last_name": "  "}
    assert incomplete["match_status"] == "needs_review" and incomplete["match_reason"] == "missing_name"
    assert incomplete["final_time"] == 17 and "athlete" not in incomplete


def test_import_retains_unsegmented_full_name_without_matching_or_duplicating(import_collections):
    race = _race()
    rows = race["competition"]["categories"][0]["results"]
    del rows[1:]
    rows[0].update(first_name=None, last_name=None, source_full_name="Souček  Stanislav Gabriel")
    with patch.object(data_import, "decide_athlete_match", new_callable=AsyncMock) as match:
        first = asyncio.run(data_import.DataImporter().import_from_dict(race))
        again = asyncio.run(data_import.DataImporter().import_from_dict(race))
        match.assert_not_awaited()

    assert first["errors"] == again["errors"] == []
    assert again["results_duplicates_skipped"] == 1
    result, = import_collections["results"].documents.values()
    assert result["source_full_name"] == "Souček  Stanislav Gabriel"
    assert result["match_status"] == "needs_review"
    assert result["match_reason"] == "name_segmentation_review"
    assert "athlete" not in result


def test_reimport_backfills_only_source_name_of_exact_legacy_result(import_collections):
    race = _race()
    rows = race["competition"]["categories"][0]["results"]
    del rows[1:]
    rows[0].update(first_name=None, last_name=None)
    first = asyncio.run(data_import.DataImporter().import_from_dict(race))
    original = next(iter(import_collections["results"].documents.values())).copy()

    async def update(filter_, update):
        stored = import_collections["results"].documents[filter_["_id"]]
        assert filter_["source_full_name"] == filter_["source_row.source_full_name"] == {"$exists": False}
        assert "source_full_name" not in stored and "source_full_name" not in (stored.get("source_row") or {})
        assert all(stored.get(field) == value for field, value in filter_.items()
                   if field not in {"source_full_name", "source_row.source_full_name"})
        stored.update(update["$set"])

    import_collections["results"].update_one = AsyncMock(side_effect=update)
    rows[0]["source_full_name"] = "Souček Stanislav Gabriel"
    second = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert first["errors"] == second["errors"] == []
    assert second["results_duplicates_skipped"] == 1
    saved, = import_collections["results"].documents.values()
    assert saved == {**original, "source_full_name": "Souček Stanislav Gabriel"}

    rows[0]["source_full_name"] = "Jiné Jméno"
    third = asyncio.run(data_import.DataImporter().import_from_dict(race))
    assert third["errors"] and third["total_imported"] == 0
    assert saved["source_full_name"] == "Souček Stanislav Gabriel"


def test_reparsed_full_name_does_not_duplicate_an_unranked_stored_result():
    from bson import ObjectId
    from app.services.data_import import DataImporter

    importer = DataImporter()
    race, category = str(ObjectId()), str(ObjectId())
    source = {"source_full_name": "Nováková  Anna Marie", "final_time": 16.0, "final_status": "valid"}
    pending = importer.build_result_row(source, category, race)
    pending.update(_id=ObjectId(), source_category={"key": "zeny", "discipline": "100m"})
    parsed = importer.build_result_row({**source, "first_name": "Anna Marie", "last_name": "Nováková"}, category, race)
    parsed["source_category"] = pending["source_category"]
    assert importer.assess_result(parsed, [pending]) == ("review", [pending["_id"]])
