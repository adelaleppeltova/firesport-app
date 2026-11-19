from copy import deepcopy
from datetime import datetime

from bson import ObjectId
import pytest

from app.category_catalog import CATEGORY_COLLECTION, CATEGORIES
from app.services.category_normalization import resolve_category
from scripts.category_identity_evidence import BirthYearEvidence
from scripts.migrate_category_catalog import build_plan, fingerprint
from scripts.review_category_duplicates import matches_published_row


def test_young_b_rules_require_the_exact_race_and_date_and_keep_original_group():
    label = "Mladší žáci B – dívky"
    event = {"date": datetime(2024, 8, 31), "source_url": "https://pozarnisporty.cz/races/369"}
    correct = resolve_category(label, "60m", event, {"birth_year": 2014})
    assert correct.category.key == "60m-girls-9-11"
    assert "stimax-cup-2024-propozice.pdf" in correct.evidence["url"]
    assert resolve_category(label, "60m", event, {"birth_year": 2017}).status == "review"
    for change in (
        {"date": "2024-09-01"}, {"source_url": "https://example.org/races/369"},
        {"source_url": "https://pozarnisporty.cz/races/12345"},
    ):
        assert resolve_category(label, "60m", {**event, **change}, {}).status == "review"
    younger = resolve_category("Mladší žáci A – dívky", "60m", event, {"birth_year": 2017})
    assert younger.status == "review" and younger.reason == "noncanonical_60m_age_range"
    assert younger.evidence["label"] == "Mladší dívky 6–8 let"
    assert resolve_category("Mladší dívky A 6–8 let", "60m", event, {"birth_year": 2017}).status == "review"


def test_oldest_unsplit_group_and_adult_standings_preserve_published_rules():
    event = {"date": "2023-05-13", "source_url": "https://pozarnisporty.cz/races/225"}
    assert resolve_category("Dívky - věk: 11 - 15", "60m", event, {}).category.key == "60m-girls-older"
    assert resolve_category("Dívky - věk: 8 - 11", "60m", event, {}).status == "review"
    legacy = {"name": "Bludovská stovka", "place": "Bludov", "date": "2019-07-27"}
    person = {"first_name": "Eva", "last_name": "Nová", "birth_year": 2002}
    assert resolve_category("Ženy", "100m", legacy, person).category.key == "100m-girls-17-18"
    assert resolve_category("Ženy", "100m", {**legacy, "date": "2019-07-28"}, person).status == "review"
    team_event = {"name": "MČR dorostu SH ČMS v PS", "place": "Písek", "date": "2024-07-01"}
    assert resolve_category("Dorostenky", "100m", team_event, person, team="Lhota").reason == (
        "team_member_result_requires_separate_treatment"
    )


def test_scoped_bzucany_and_chomutov_source_overrides():
    person = {"first_name": "Jan", "last_name": "Nový", "birth_year": 2006}
    event = {"date": "2023-09-30", "source_url": "https://pozarnisporty.cz/races/227"}
    out = resolve_category("Dorost chlapci + muži (nad 17 let)", "100m", event, person)
    assert out.category.key == "100m-boys-17-18" and "clanek_STIMAX" in out.evidence["url"]
    event = {"date": "2023-07-30", "source_url": "https://pozarnisporty.cz/races/196"}
    assert resolve_category("Střední dorost", "100m", event, {}).category.key == "100m-boys-15-16"


def test_birth_year_requires_strong_identity_and_independent_source():
    profile, older, newer, witness, current = (ObjectId() for _ in range(5))
    person = {"first_name": "Jan", "last_name": "Nový"}
    target = {"_id": current, "athlete": profile, "match_status": "matched",
              "match_reason": "manual_admin_assignment", "competition": older, "imported_athlete": person}
    source = {**target, "_id": witness, "match_reason": "name_plus_fscode", "competition": newer,
              "imported_athlete": {**person, "fscode": "0234", "birth_year": 2006}}
    db = {"athletes": {profile: {**person, "birth_year": 2006, "fs_codes": ["0234"]}},
          "results": {current: target, witness: source}}
    assert BirthYearEvidence(db).for_result(target)["source_result_ids"] == [witness]
    assert BirthYearEvidence(db).for_result({**target, "match_reason": "name_plus_team"}) is None
    assert BirthYearEvidence(db).for_result({**target, "competition": newer}) is None
    wrong_year = deepcopy(db)
    wrong_year["athletes"][profile]["birth_year"] = 2007
    assert BirthYearEvidence(wrong_year).for_result(target) is None
    shared = deepcopy(db)
    shared["athletes"][ObjectId()] = {"fs_codes": ["0234"]}
    assert BirthYearEvidence(shared).for_result(target) is None


def test_pdf_evidence_requires_exact_bib_rank_name_and_times():
    identity = {"name": ("jana", "nová"), "start_number": "011", "rank": 2, "final_time": 17.2,
                "final_time_status": "valid", "times": [(1, 17.2, "valid", None), (2, None, "invalid", None)]}
    assert matches_published_row(identity, "2 11 Jana Nová Lhota 17,20 NP 17,20", rank_first=True)
    assert matches_published_row(identity, "11 1234 Nová Jana Lhota 17,20 998,00 17,20 2.", rank_first=False)
    assert not matches_published_row(identity, "2 11 Jana Nová Lhota 17,20 19,20 17,20", rank_first=True)
    assert not matches_published_row(identity, "3 11 Jana Nová Lhota 17,20 NP 17,20", rank_first=True)


def test_approved_duplicate_is_archived_without_changing_original_data_and_can_be_replayed():
    event, canonical_label, legacy_label, keeper, copy = (ObjectId() for _ in range(5))
    raw = {"_id": keeper, "competition": event, "category": canonical_label, "start_number": "11",
           "rank": 2, "final_time": 17.2, "final_time_status": "valid",
           "imported_athlete": {"first_name": "Jana", "last_name": "Nová"}, "times": []}
    repeated = {**raw, "_id": copy, "category": legacy_label}
    snapshot = {
        "results": {keeper: raw, copy: repeated},
        "categories": {
            canonical_label: {"_id": canonical_label, "discipline": "100m", "name": "Ženy"},
            legacy_label: {"_id": legacy_label, "discipline": "100m", "name": "Ženy - věk: 19 - 100"},
        },
        "competitions": {event: {"_id": event, "date": datetime(2024, 1, 1)}},
        "athletes": {}, CATEGORY_COLLECTION: {},
    }
    proof = {"version": 1, "duplicates": [{
        "keep": keeper, "copy": copy, "keep_sha256": fingerprint(raw), "copy_sha256": fingerprint(repeated),
        "source_url": "https://example.org/results.pdf", "source_sha256": "a" * 64, "source_page": 1, "text_line": 2,
    }]}
    before = build_plan(snapshot)[0]
    assert before["counts"]["duplicate_clusters"] == 1
    after, changes = build_plan(snapshot, proof)
    assert after["counts"]["results_before"] == after["counts"]["results_after"] == 2
    assert after["counts"]["active"] == after["counts"]["confirmed_duplicate_clusters"] == 1
    assert after["counts"]["archived_duplicate_results"] == 1
    assert changes["results"][copy]["duplicate_of"] == keeper
    for field in ("rank", "times", "final_time", "imported_athlete"):
        assert field not in changes["results"][copy]
    applied = deepcopy(snapshot)
    applied[CATEGORY_COLLECTION] = {category.id: category.document() for category in CATEGORIES}
    for identifier, fields in changes["results"].items():
        applied["results"][identifier].update(fields)
    reapplied, updates = build_plan(applied)
    assert not updates["results"]
    assert reapplied["counts"]["confirmed_duplicate_clusters"] == 1
    tampered = deepcopy(snapshot)
    tampered["results"][copy]["district"] = "Jiný okres"
    with pytest.raises(ValueError, match="neodpovídají snímku"):
        build_plan(tampered, proof)
