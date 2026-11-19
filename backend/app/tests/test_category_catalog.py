import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock, patch

from bson import ObjectId
import pytest

from app.api.v1.result_router import get_catalog
from app.category_catalog import (
    BY_ID, BY_KEY, CATEGORY_COLLECTION, CATEGORIES, DISCIPLINES, active_results, personal_records,
)
from app.extraction.metadata import category_discipline
from app.services.category_normalization import competition_age, resolve_category
from scripts import migrate_category_catalog as migration


def person(year=None):
    return {"first_name": "Jana", "last_name": "Testová", "birth_year": year}


def resolve(name, discipline, birth_year=None, year=2026, **kwargs):
    return resolve_category(name, discipline, {"name": "Okresní kolo", "date": f"{year}-06-01"},
                            person(birth_year), **kwargs)


def test_catalog_is_a_fixed_32_category_whitelist():
    assert set(DISCIPLINES) == {"100m", "60m"}
    assert len(BY_ID) == len(BY_KEY) == len(CATEGORIES) == 32
    assert Counter((c.discipline, c.type, c.age_system) for c in CATEGORIES) == {
        ("100m", "individual", "age_group"): 8, ("100m", "individual", "general"): 4, ("100m", "team", "age_group"): 2,
        ("60m", "individual", "age_group"): 14, ("60m", "individual", "general"): 4,
    }
    for discipline, kind, intervals in (
        ("100m", "individual", {(13, 14), (13, 16), (15, 16), (17, 18), (17, 100), (19, 100)}),
        ("100m", "team", {(13, 18)}),
        ("60m", "individual", {(0, 5), (3, 7), (5, 6), (6, 10), (10, 15), (7, 8), (9, 11), (12, 13), (14, 15)}),
    ):
        for gender in ("male", "female"):
            assert {(c.min_age, c.max_age) for c in CATEGORIES
                    if (c.discipline, c.type, c.gender) == (discipline, kind, gender)} == intervals


@pytest.mark.parametrize(("label", "key"), [
    ("Muži a starší dorostenci", "100m-men-17-100"),
    ("Ženy a starší dorostenky", "100m-women-17-100"),
])
def test_published_combined_group_keeps_its_own_category(label, key):
    assert resolve(label, "100m", None).category.key == key
    assert resolve(label + " – věk: 17–100 let", "100m", 2009).category.key == key
    assert resolve(label, "100m", 2010).reason == "outside_canonical_age_range"


@pytest.mark.parametrize(("age", "key"), [
    (13, "100m-boys-13-14"), (14, "100m-boys-13-14"), (15, "100m-boys-15-16"),
    (16, "100m-boys-15-16"), (17, "100m-boys-17-18"), (18, "100m-boys-17-18"), (19, "100m-men"),
])
def test_combined_100m_follows_competition_year(age, key):
    decision = resolve("Dorost chlapci + muži", "100m", 2026 - age)
    assert decision.category.key == key
    assert decision.per_result


def test_chomutov_official_combined_list_has_one_category_regardless_of_birth_year():
    event = {"date": "2026-09-19", "source_url": "https://pozarnisporty.cz/races/1034"}
    name = "10) Dorost dívky + ženy – 17 – 100 let"
    for year in (None, 2008, 2000):
        result = resolve_category(name, "100m", event, person(year))
        assert result.category.key == "100m-women-17-100"
        assert not result.per_result


def test_explicit_preparatory_5_6_group_keeps_separate_category():
    for year in (None, 2020, 2021):
        assert resolve("Přípravka dívky 5-6", "60m", year).category.key == "60m-girls-preparatory-5-6"
    assert resolve("Přípravka dívky 5-6", "60m", 2022).status == "review"


@pytest.mark.parametrize(("name", "age", "key"), [
    ("MLADŠÍ dívky", 10, "60m-girls-younger"),
    ("STARŠÍ ZÁCI – dívky", 10, "60m-girls-older"),
    ("chlapci - mladší", 10, "60m-boys-younger"),
    ("Starší chlapci", 10, "60m-boys-older"),
    ("Mladší chlapci 7–8 let", 8, "60m-boys-7-8"),
    ("Mladší žáci b – chlapci – od 9 do 11 let", 9, "60m-boys-9-11"),
    ("Mladší dívky b (9 - 11 let)", 11, "60m-girls-9-11"),
    ("Starší žáci a – dívky – 12 a 13 let", 12, "60m-girls-12-13"),
    ("Starší žáci a – dívky – 12 a 13 let", 13, "60m-girls-12-13"),
    ("Starší žáci b – dívky – 14 a 15 let", 14, "60m-girls-14-15"),
    ("Starší žáci b – dívky – 14 a 15 let", 15, "60m-girls-14-15"),
])
def test_60m_follows_the_published_category(name, age, key):
    assert resolve(name, "60m", 2026 - age).category.key == key


def test_year_boundary_and_insufficient_evidence():
    assert competition_age(datetime(2026, 1, 1), 2018) == 8
    assert competition_age("2027-12-31", 2018) == 9
    assert resolve("Mladší dívky 7–8 let", "60m", 2018, year=2026).category
    assert resolve("Mladší dívky 9–11 let", "60m", 2018, year=2027).category
    for name, discipline, age in (
        ("Mladší dívky 6–8 let", "60m", 6),
        ("Mladší dívky 6–8 let", "60m", 8),
        ("Mladší dívky 7–8 let", "60m", 6),
        ("Dívky - věk: 11 - 15", "60m", 13),
        ("Mladší žáci B – chlapci", "60m", 10),
        ("Dorostenci", "100m", None),
        ("Střední dorost", "100m", 16),
    ):
        assert resolve(name, discipline, 2026 - age if age else None).status == "review"
    assert resolve("Ženy", "vez").status == "unsupported"
    assert resolve("Ženy", None).status == "review"
    assert category_discipline("Muži", "800m", "100 m s překážkami") is None


def test_team_and_hzs_require_source_evidence():
    assert resolve("Dorostenci", "100m", 2009).category.key == "100m-boys-17-18"
    assert resolve("Dorostenci - družstvo", "100m", 2009).status == "review"
    team = "Lhota"
    event = {"name": "Krajské kolo"}
    assert resolve_category("Dorostenci", "100m", event, {}, team=team).status == "review"
    assert resolve_category("Dorostenci", "100m", event, {}, team=team, team_table=True).category.type == "team"
    assert resolve_category("Dorostenci - družstvo", "100m", event, {}, team=team).category.type == "team"
    assert resolve_category("Dorostenci - družstvo", "100m", {"name": "STIMAX"}, {}, team=team).status == "review"
    assert resolve("Muži HZS", "100m", 2000).status == "review"
    assert resolve_category("MUŽI HZS", "100m", {"name": "MČR v PS"}, person()).affiliation == "HZS"


def result(key, time, status="valid", classification="active"):
    category = BY_KEY[key]
    return {"category": category.id, "discipline": category.discipline, "result_type": category.type,
            "classification_status": classification, "final_time_status": status, "final_time": time}


def test_personal_records_use_official_valid_individual_times_and_cross_age_groups():
    records = personal_records([
        result("100m-men", 16.85), result("100m-boys-17-18", 17), result("100m-boys-team", 10),
        result("60m-girls-younger", 13.9), result("60m-girls-12-13", 12.43),
        result("60m-girls-14-15", 12.5), result("60m-girls-14-15", 11, "invalid"),
        result("60m-girls-14-15", 10, classification="review"), result("100m-men", float("inf")),
        result("100m-women", 998),
    ])
    assert records == {"100m": 16.85, "60m": 12.43}
    offered = asyncio.run(get_catalog("60m"))
    assert len(offered["categories"]) == 18
    assert {cat.discipline for cat in offered["categories"]} == {"60m"}
    assert len(active_results(discipline="100m", individual=True)["category"]["$in"]) == 12


def fixture_snapshot():
    category, tower, unknown, competition, athlete = (ObjectId() for _ in range(5))
    docs = {name: {} for name in migration.READ_COLLECTIONS}
    docs["categories"] = {
        category: {"_id": category, "name": "Muži a starší dorostenci", "discipline": "100m"},
        tower: {"_id": tower, "name": "Muži", "discipline": "vez"},
        unknown: {"_id": unknown, "name": "Mladší dívky 6–8 let", "discipline": "60m"},
    }
    docs["competitions"][competition] = {"_id": competition, "name": "Pohár", "categories": [category, tower],
                                         "date": datetime(2026, 6, 1)}
    docs["athletes"][athlete] = {"_id": athlete, **person(2008)}
    for cat_id, birth in [(category, 2008), (category, None), (tower, 2000), (unknown, 2020)]:
        identifier = ObjectId()
        docs["results"][identifier] = {
            "_id": identifier, "category": cat_id, "competition": competition, "athlete": athlete,
            "imported_athlete": person(birth), "start_number": "44", "rank": 15, "team": "Lhota",
            "times": [{"attempt": 1, "time": 19.55, "status": "valid"}],
            "final_time": 19.56, "final_time_status": "valid",
        }
    return docs


def test_dry_run_only_reads_and_migration_preserves_official_result_and_references():
    snapshot = fixture_snapshot()
    before = deepcopy(snapshot)
    db = MagicMock()
    db.list_collection_names.return_value = migration.INPUT_COLLECTIONS
    collections = {name: MagicMock() for name in migration.INPUT_COLLECTIONS}
    db.__getitem__.side_effect = collections.__getitem__
    for name, collection in collections.items():
        collection.find.return_value.sort.return_value = list(snapshot[name].values())
    report, changes = migration.build_plan(migration.read_database(db))
    assert [call[0] for call in db.method_calls] == ["list_collection_names"]
    for collection in collections.values():
        assert [call[0] for call in collection.method_calls] == ["find"]
        collection.find.return_value.sort.assert_called_once_with("_id", 1)
    assert snapshot == before
    assert report["counts"]["active"] == 2
    assert report["counts"]["review"] == 0
    assert report["counts"]["historical_60m"] == 1
    assert report["counts"]["unsupported_by_discipline"] == {"vez": 1}
    assert report["counts"]["reference_issues"] == 0
    assert report["counts"]["results_before"] == report["counts"]["results_after"] == 4
    assert report["plan_sha256"] == migration.build_plan(snapshot)[0]["plan_sha256"]

    applied = deepcopy(snapshot)
    applied[CATEGORY_COLLECTION] = {c.id: c.document() for c in CATEGORIES}
    for name, pending in changes.items():
        for identifier, fields in pending.items():
            applied[name][identifier].update(fields)
    assert migration.build_plan(applied)[1] == {"results": {}, "competitions": {}}
    migration.assert_compatible_snapshot(applied, snapshot, changes)
    for identifier, row in applied["results"].items():
        migration.validate_classification(row, applied[CATEGORY_COLLECTION])
        original = snapshot["results"][identifier]
        assert (row["rank"], row["final_time"], row["times"]) == (
            original["rank"], original["final_time"], original["times"])
        assert row["source_category"]["legacy_category_id"] == original["category"]
    with patch.object(migration, "read_database", return_value=applied), patch.object(migration, "install_catalog"):
        migration.apply_plan(db, snapshot, changes)
    assert all(not collection.update_one.called for collection in collections.values())


def test_migration_detects_changed_data_and_duplicate_candidates():
    snapshot = fixture_snapshot()
    row = next(iter(snapshot["results"].values()))
    duplicate = {**row, "_id": ObjectId()}
    snapshot["results"][duplicate["_id"]] = duplicate
    report, updates = migration.build_plan(snapshot)
    assert report["counts"]["duplicate_clusters"] == 1
    assert updates["results"][row["_id"]]["classification_reason"] == "possible_duplicate_official_row"
    actual = deepcopy(snapshot)
    actual["results"][row["_id"]]["rank"] = 99
    with pytest.raises(ValueError, match="změnil"):
        migration.assert_compatible_snapshot(actual, snapshot, updates)


def test_anomaly_recompute_only_reuses_runs_from_current_catalog():
    from datetime import timezone

    from app.category_catalog import CATALOG_VERSION
    from app.services.anomaly_service import recompute_yearly_batch

    db = MagicMock()
    runs = db["anomaly_runs"]
    runs.find.return_value.__aiter__.return_value = []
    date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    asyncio.run(recompute_yearly_batch(db, date_min=date, date_max=date))
    assert runs.find.call_args.args[0]["catalog_version"] == CATALOG_VERSION


def test_personal_record_requires_identity_for_incomplete_imported_names():
    nameless = {**result("100m-men", 15), "athlete": ObjectId(),
                "imported_athlete": {"first_name": "", "last_name": " "}}
    assert personal_records([nameless])["100m"] is None
    assert personal_records([{**nameless, "match_reason": "manual_admin_assignment"}])["100m"] == 15


def test_preparatory_3_to_7_requires_an_explicit_label_or_documented_race():
    event = {"date": "2025-07-26", "source_url": "https://pozarnisporty.cz/races/695"}
    five_year_old = person(2020)
    grouped = resolve_category("přípravka dívky", "60m", event, five_year_old)
    assert grouped.category == BY_KEY["60m-girls-preparatory-3-7"]
    assert grouped.evidence["url"] == "https://pozarnisporty.cz/races/695"
    assert resolve_category("Přípravka chlapci 3–7 let", "60m", event, person(2018)).category == (
        BY_KEY["60m-boys-preparatory-3-7"]
    )
    assert resolve_category("přípravka dívky", "60m", event, person(2017)).reason == "outside_canonical_age_range"
    different_date = {**event, "date": "2025-07-27"}
    assert resolve_category("přípravka dívky", "60m", different_date, five_year_old).category == (
        BY_KEY["60m-girls-preparatory"]
    )


def test_beloves_2022_uses_one_published_individual_group_for_ages_13_to_16():
    event = {"name": "Běloveský kilo", "place": "Náchod - Hamra", "date": "2022-06-05"}
    grouped = resolve_category("Dorostenci", "100m", event, person(None))
    assert grouped.category == BY_KEY["100m-boys-13-16"]
    assert "310/Belovesky" in grouped.evidence["url"]
    assert resolve_category("Dorostenky", "100m", event, person(2006)).category == BY_KEY["100m-girls-13-16"]
    assert resolve_category("Dorostenky", "100m", event, person(2005)).reason == "outside_canonical_age_range"
    previous_event = {**event, "date": "2019-06-02"}
    assert resolve_category("Dorostenci", "100m", previous_event, person(None)).category is None
