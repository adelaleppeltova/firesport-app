from copy import deepcopy
from datetime import datetime
from unittest.mock import MagicMock

import pymupdf

from bson import ObjectId
import pytest

from app.category_catalog import BY_ID, BY_KEY, CATEGORY_COLLECTION, CATEGORIES, DISCIPLINES, active_results, personal_records
from app.services.category_normalization import resolve_category
from app.services.published_standings import HISTORICAL, TEAM_MEMBER, historical_fields
from app.services.supplemental_standings import compose_standings, standalone_filters
from scripts.migrate_category_catalog import build_plan, fingerprint, validate_standings_references
from scripts.prepare_team_standings import read_total_rows


def official_attempts(time):
    return [{"attempt": 1, "time": time, "status": "valid"},
            {"attempt": 2, "time": None, "status": "invalid"}]


def setup_standings():
    competition, old_team, old_history, member, historical = (ObjectId() for _ in range(5))
    event = {"_id": competition, "name": "MČR dorostu SH ČMS v PS", "place": "Písek",
             "date": datetime(2024, 7, 1)}
    row = {"_id": member, "competition": competition, "category": old_team, "team": "Vědomice",
           "rank": 7, "start_number": "027", "final_time": 18.4, "final_time_status": "valid",
           "times": official_attempts(18.4), "imported_athlete": {"first_name": "Eva", "last_name": "Nová"}}
    archive = {**row, "_id": historical, "category": old_history, "rank": 11}
    original = {
        "results": {member: row, historical: archive},
        "categories": {old_team: {"_id": old_team, "name": "Dorostenky", "discipline": "100m"},
                       old_history: {"_id": old_history, "name": "Dívky - věk: 6 - 8", "discipline": "60m"}},
        "competitions": {competition: event}, "athletes": {}, CATEGORY_COLLECTION: {},
    }
    source = {"source_url": "https://mladez.dh.cz/example.pdf", "source_sha256": "a" * 64}
    evidence = {"version": 1, "team_lists": [{
        "competition": competition, "source_category_key": "dorostenky",
        "totals_source": source, "members_source": source,
        "totals": [{"source_number": 1, "name": "Vědomice", "rank": 4, "total_time": 94.05,
                    "total_status": "valid", "source_page": 1, "source_total": "94,05"}],
        "members": [{"id": member, "row_sha256": fingerprint(row), "team_number": 1, "source_page": 2,
                     "published_attempts": [{"attempt": 1, "time": 18.4, "status": "valid"},
                                            {"attempt": 2, "time": 19.02, "status": "valid"}]}],
    }]}
    return original, evidence


def test_published_team_totals_and_attempts_are_separate_and_integrity_survives_replay():
    snapshot, evidence = setup_standings()
    before = deepcopy(snapshot)
    report, updates = build_plan(snapshot, team_evidence=evidence)
    assert snapshot == before
    assert report["counts"]["historical_60m"] == report["counts"]["team_member_runs"] == 1
    assert report["counts"]["team_standings"] == report["counts"]["team_attempt_discrepancies"] == 1
    assert report["counts"]["unique_result_records"] == 2
    applied = deepcopy(snapshot)
    applied[CATEGORY_COLLECTION] = {category.id: category.document() for category in CATEGORIES}
    for name, docs in updates.items():
        for identifier, fields in docs.items():
            applied[name][identifier].update(fields)
    report2, updates2 = build_plan(applied)
    assert updates2 == {"competitions": {}, "results": {}}
    assert report2["counts"]["team_member_runs"] == 1

    team_row, history_row = applied["results"].values()
    original_row = snapshot["results"][team_row["_id"]]
    assert team_row["rank"] == original_row["rank"] == 7
    assert team_row["times"] == original_row["times"]
    assert team_row["classification_status"] == TEAM_MEMBER
    assert history_row["classification_status"] == HISTORICAL and history_row["category"] is None
    event = next(iter(applied["competitions"].values()))
    view = compose_standings(event, [team_row, history_row])
    assert view.teams[0].rank == 4 and view.teams[0].total_time == 94.05
    assert view.teams[0].members[0].rank == 7
    assert view.teams[0].members[0].times[1].time == 19.02
    assert view.historical[0].results[0].rank == 11 and view.historical[0].min_age == 6

    team_row["team_entry_id"] = ObjectId()
    with pytest.raises(ValueError, match="chybějící družstvo"):
        validate_standings_references(applied["results"], applied["competitions"], BY_ID)


def test_stats_and_historical_view_exclude_duplicate_copies_and_other_result_types():
    individual_category = BY_KEY["100m-women"]
    event = ObjectId()
    individual = {"_id": ObjectId(), "competition": event, "classification_status": "active",
                  "result_type": "individual", "discipline": "100m", "category": individual_category.id,
                  "final_time": 17.1, "final_time_status": "valid"}
    duplicate = {**individual, "_id": ObjectId(), "duplicate_of": individual["_id"], "final_time": 9.3}
    wrong_role = {**individual, "_id": ObjectId(), "result_type": TEAM_MEMBER, "final_time": 10.5}
    assert personal_records([individual, duplicate, wrong_role]) == {"100m": 17.1, "60m": None}
    assert active_results(discipline="100m", individual=True)["duplicate_of"] is None
    assert standalone_filters()["duplicate_of"] is None
    history = {"_id": ObjectId(), "competition": event, "classification_status": HISTORICAL,
               "discipline": "60m", "category": None, "historical_age_range": [8, 11],
               "source_category": {"name": "Dívky 8–11", "legacy_category_id": ObjectId()},
               "rank": 9, "final_time": 3540, "final_time_status": "valid",
               "times": [{"attempt": 1, "time": None, "status": "invalid"}]}
    archived = {**history, "_id": ObjectId(), "duplicate_of": history["_id"]}
    visible = compose_standings({"_id": event}, [history, archived]).historical[0].results
    assert len(visible) == 1
    assert visible[0].final_time is None and visible[0].final_time_unverified
    assert history["final_time"] == 3540


def test_historical_ranges_need_exact_source_evidence_and_individual_row_proof_does_not_create_identity():
    assert historical_fields("60m", "noncanonical_60m_age_range", {"min_age": 7, "max_age": 11}) == {}
    source = {"classification_evidence": [{"kind": "organizer_category", "label": "Chlapci 6–8 let"}]}
    assert historical_fields("60m", "noncanonical_60m_age_range", source)["historical_age_range"] == [6, 8]
    assert len(CATEGORIES) == 26 and set(DISCIPLINES) == {"100m", "60m"}

    event = {"date": "2024-01-01"}
    person = {"birth_year": 2008, "first_name": "", "last_name": ""}
    assert resolve_category("Dorost dívky", "100m", event, person).category is None
    proven = resolve_category("Dorost dívky", "100m", event, person, verified_individual_row=True)
    assert proven.category.key == "100m-girls-15-16"
    assert person["first_name"] == person["last_name"] == ""


def test_total_pdf_columns_keep_source_ties_and_reject_truncation():
    page = MagicMock()
    page.rotation_matrix = pymupdf.Matrix(1, 1)
    words = [(100, 100, 101, 101, "st.č."), (200, 100, 201, 101, "SDH"),
             (290, 100, 291, 101, "Pokus"), (600, 100, 601, 101, "Suma"),
             (700, 100, 701, 101, "Poř.")]
    for index in range(1, 16):
        y = 120 + 35 * index
        position = 8 if index == 9 else index
        name = [] if index == 15 else [(130, y, 135, y + 6, f"Klub{index}")]
        words.extend([(108, y, 116, y + 6, str(index)), *name,
                      (625, y, 655, y + 6, "DNF" if index == 15 else "94,05"),
                      (705, y, 717, y + 6, str(position))])
    page.get_text.return_value = words
    rows = read_total_rows([page])
    assert rows[7]["rank"] == rows[8]["rank"] == 8
    assert rows[-1]["name"] is rows[-1]["total_time"] is None
    page.get_text.return_value = words[:-3]
    with pytest.raises(ValueError, match="Nekompletní"):
        read_total_rows([page])


def test_supplemental_personal_records_require_verified_provenance():
    athlete, competition, team = ObjectId(), ObjectId(), ObjectId()
    historical = {
        "classification_status": "historical", "result_type": "individual", "discipline": "60m",
        "historical_age_range": [6, 8], "athlete": athlete, "competition": competition,
        "final_time": 12.4, "final_time_status": "valid", "times": [{"status": "valid", "time": 12.4}],
        "record_evidence": {"athlete": athlete, "competition": competition, "time": 12.4,
                            "source_url": "https://example.test/list"},
    }
    member = {
        **historical, "classification_status": "team_member", "result_type": "team_member",
        "discipline": "100m", "category": BY_KEY["100m-boys-team"].id, "team_entry_id": team,
        "final_time": 17.5, "published_attempts": [{"status": "valid", "time": 17.5}],
        "member_evidence": {"source_sha256": "a" * 64},
        "record_evidence": {**historical["record_evidence"], "time": 17.5},
    }
    assert personal_records([historical, member]) == {"100m": None, "60m": 12.4}
    member["record_evidence"].update(rules_url="https://example.test/rules", rules_sha256="b" * 64)
    assert personal_records([historical, member]) == {"100m": 17.5, "60m": 12.4}
    assert personal_records([
        {**historical, "athlete": ObjectId()}, {**member, "duplicate_of": ObjectId()},
        {**historical, "final_time_status": "invalid"}, {**historical, "classification_status": "review"},
        {**member, "published_attempts": []},
    ]) == {"100m": None, "60m": None}
