from datetime import datetime

from bson import ObjectId

from app.category_catalog import BY_KEY
from scripts.reconcile_athletes import build_plan, expected_state


def athlete(first="Jan", last="Novák", year=2000, codes=()):
    return {
        "_id": ObjectId(), "first_name": first, "last_name": last,
        "birth_year": year, "fs_codes": list(codes),
    }


def result(first="Jan", last="Novák", year=2000, code=None, **fields):
    return {
        "_id": ObjectId(), "competition": ObjectId(), "category": BY_KEY["100m-men"].id,
        "discipline": "100m", "date": datetime(2024, 6, 1), "result_type": "individual",
        "classification_status": "active", "match_status": "unmatched", "final_time": 16.53,
        "imported_athlete": {
            "first_name": first, "last_name": last, "birth_year": year, "fscode": code,
        },
        **fields,
    }


def state(rows=(), athletes=()):
    return {
        "results": {row["_id"]: row for row in rows},
        "athletes": {row["_id"]: row for row in athletes}, "competitions": {},
    }


def linked(plan):
    return {operation["_id"]: operation["set"]["athlete"]
            for operation in plan["updates"] if "athlete" in operation["set"]}


def reasons(plan):
    return {item["_id"]: item["reason"] for item in plan["review"]}


def test_exact_identity_links_to_existing_profile_and_preserves_previous_assignments():
    jan = athlete(codes=[4721])
    year = result()
    code = result(year=None, code="4721")
    original = result(last="Noák", athlete=jan["_id"], match_status="matched",
                      match_reason="manual_admin_assignment")
    plan = build_plan(state([year, code, original], [jan]))
    assert linked(plan) == {year["_id"]: jan["_id"], code["_id"]: jan["_id"]}
    assert {item["result_id"] for item in plan["issues"]} == {original["_id"]}
    assert plan["creates"] == []


def test_new_profile_groups_confirmed_year_but_cannot_absorb_weak_rows():
    first, second, faint = result(), result(), result(year=None)
    singleton = result(first="Tomáš", last="Králík", year=None)
    data = state([first, second, faint, singleton])
    plan = build_plan(data)
    assignments = linked(plan)
    assert len(plan["creates"]) == 2
    assert assignments[first["_id"]] == assignments[second["_id"]]
    assert assignments[singleton["_id"]] != assignments[first["_id"]]
    assert reasons(plan) == {faint["_id"]: "insufficient_identity"}
    after = expected_state(data, plan, datetime(2026, 11, 19))
    assert after["results"][first["_id"]]["final_time"] == first["final_time"]
    repeated = build_plan(after)
    assert repeated["creates"] == repeated["updates"] == []


def test_homonyms_and_nonmatching_codes_do_not_create_or_merge_profiles():
    first, second = result(year=1999), result(year=2000)
    jan = athlete(year=2002)
    plan = build_plan(state([first, second], [jan]))
    assert plan["creates"] == []
    assert set(reasons(plan).values()) == {"conflicting_birth_year"}
    plan = build_plan(state([first, second]))
    assert plan["creates"] == []
    assert set(reasons(plan).values()) == {"conflicting_source_identity"}
    code_only, year_only = result(year=None, code="4721"), result()
    plan = build_plan(state([code_only, year_only]))
    assert plan["creates"] == []
    assert set(reasons(plan).values()) == {"conflicting_source_identity"}


def test_shared_codes_and_same_list_never_create_duplicate_assignments():
    jan = athlete(codes=["4721"])
    duplicate = athlete(last="Liška", year=2001, codes=["4721"])
    code = result(code=4721)
    plan = build_plan(state([code], [jan, duplicate]))
    assert reasons(plan)[code["_id"]] == "shared_fscode"
    first = result()
    second = result(competition=first["competition"], start_number=22)
    plan = build_plan(state([first, second], [jan]))
    assert not linked(plan) and set(reasons(plan).values()) == {"same_result_list_conflict"}
    plan = build_plan(state([first, second]))
    assert not plan["creates"] and set(reasons(plan).values()) == {"same_result_list_conflict"}


def test_near_name_manual_unassignment_and_archival_rows_go_untouched():
    near = athlete(last="Novotná")
    typo = result(last="Novtná")
    manual = result(match_reason="manual_admin_unassignment")
    archived = result(classification_status="historical")
    plan = build_plan(state([typo, manual, archived], [near]))
    assert reasons(plan) == {
        typo["_id"]: "possible_name_variant", manual["_id"]: "manual_admin_unassignment",
    }
    assert [item["_id"] for item in plan["updates"]] == [typo["_id"]]


def test_name_year_match_checks_all_codes_reported_for_that_identity():
    jan = athlete()
    first, second = result(code="4721"), result(code="4722")
    plan = build_plan(state([first, second], [jan]))
    assert not linked(plan)
    assert set(reasons(plan).values()) == {"unrecognized_fscode"}


def test_new_profile_does_not_weaken_typo_check_on_a_second_run():
    jan = result(year=2000, team="Sbor A")
    similar = result(last="Novek", year=None, team="Sbor B")
    unclear = result(year=2000, team="Sbor B")
    data = state([jan, similar, unclear], [athlete(last="Novek", year=None)])
    plan = build_plan(data)
    assert set(linked(plan)) == {jan["_id"]}
    assert reasons(plan)[unclear["_id"]] == "possible_name_variant"
    after = expected_state(data, plan, datetime(2026, 11, 19))
    assert build_plan(after)["updates"] == []


def test_audit_counts_unreadable_files_and_compares_each_result(tmp_path):
    import json

    from app.services.data_import import DataImporter
    from scripts.audit_reconciliation_sources import audit_sources

    folder = tmp_path / "2024" / "zavod"
    folder.mkdir(parents=True)
    (folder / "empty.json").touch()
    raw = {
        "first_name": "Jan", "last_name": "Novák", "birth_year": 2000, "rank": 1,
        "start_number": 14, "final_time": 16.53, "final_status": "valid", "times": [],
    }
    competition = {"_id": ObjectId(), "name": "Závod", "place": "Brno", "date": datetime(2024, 6, 1)}
    payload = {
        "competition": {
            "name": "Závod", "place": "Brno", "date": "2024-06-01",
            "categories": [{"name": "Muži", "discipline": "100m", "results": [raw, {**raw, "rank": 2}]}],
        },
    }
    (folder / "zavod.json").write_text(json.dumps(payload), encoding="utf-8")
    row = DataImporter().build_result_row(raw, str(BY_KEY["100m-men"].id), str(competition["_id"]))
    row.update(_id=ObjectId(), discipline="100m")
    data = state([row])
    data["competitions"][competition["_id"]] = competition
    report = audit_sources(tmp_path, data)
    assert report["counts"]["unreadable_json"] == 1
    assert report["counts"]["rows"] == 2
    assert report["counts"]["represented"] == 1
    assert report["unresolved_rows"] == [{
        "path": "2024/zavod/zavod.json", "category": 1, "row": 2,
        "reason": "source_row_needs_comparison", "candidates": [],
    }]
