import json
from datetime import datetime

from bson import ObjectId

from app.category_catalog import BY_KEY
from scripts.compare_result_name_audits import compare_snapshots, compare_sources


def test_source_row_can_remain_incomplete_after_a_database_repair(tmp_path):
    cid, rid = ObjectId(), ObjectId()
    url = "https://example.org/results.html"
    published = {"first_name": None, "last_name": None, "source_full_name": "Nováková  Jana",
                 "rank": 1, "start_number": 15, "team": "Lhota", "final_time": 16.5, "final_status": "valid"}
    event = {"date": "2026-04-01", "name": "Stovky", "place": "Lhota"}
    payload = {"source_file": url, "competition": {**event, "categories": [
        {"name": "Ženy", "discipline": "100m", "results": [published]}
    ]}}
    (tmp_path / "stovky.json").write_text(json.dumps(payload), encoding="utf-8")
    row = {"_id": rid, "competition": cid, "category": BY_KEY["100m-women"].id,
           "source_category": {"name": "Ženy", "discipline": "100m"},
           "source_row": published, "classification_status": "active", "discipline": "100m",
           "result_type": "individual", "match_status": "needs_review",
           "imported_athlete": {"first_name": "", "last_name": ""}}
    previous = {"results": {rid: row}, "categories": {},
                "competitions": {cid: {**event, "date": datetime(2026, 4, 1), "source_url": url}}}
    repaired = {**row, "imported_athlete": {"first_name": "Jana", "last_name": "Nováková"}}
    current = {**previous, "results": {rid: repaired}}

    comparison = compare_snapshots(previous, current)
    assert comparison["previously_missing_now_complete"] == 1
    assert comparison["previous"]["admin_missing_name"] == 1
    assert comparison["current"].get("admin_missing_name", 0) == 0
    sources = compare_sources(current, tmp_path)
    assert sources["counts"]["exact_source_row"] == sources["counts"]["confirmed_complete"] == 1
    detail, = sources["rows"]
    assert detail["source_full_name"] == "Nováková  Jana"
    assert detail["source_person_name"] == {"first_name": None, "last_name": None}
    assert detail["imported_athlete"] == repaired["imported_athlete"]

    other = ObjectId()
    current["results"][other] = {**row, "_id": other}
    assert compare_sources(current, tmp_path)["counts"]["ambiguous_rows"] == 1
