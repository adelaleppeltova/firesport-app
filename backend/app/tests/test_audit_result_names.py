from datetime import datetime

from bson import ObjectId

from app.extraction.storage import source_id
from scripts.audit_result_names import make_plan


URL = "https://pozarnisporty.cz/races/123"


def test_dry_run_only_fills_proven_name_parts_and_preserves_originals_and_links(tmp_path):
    directory = tmp_path / source_id(URL)
    directory.mkdir()
    (directory / "source.html").write_text("""
        <div data-race-date="2026-04-01"></div>
        <table data-discipline="100m"><caption>Ženy</caption>
          <tr><th>Pořadí</th><th>Příjmení a jméno</th><th>Team</th><th>Výsledný čas</th></tr>
          <tr><td>1</td><td>Nováková  Anna Marie</td><td>Lhota</td><td>16,00</td></tr>
          <tr><td>2</td><td>Svobodová Eva Marie</td><td>Lhota</td><td>17,00</td></tr>
        </table>
    """)
    cid, repaired, ambiguous = ObjectId(), ObjectId(), ObjectId()
    original = {
        "competition": cid, "source_category": {"name": "Ženy", "discipline": "100m"},
        "team": "Lhota", "classification_status": "active", "result_type": "individual",
        "times": [{"attempt": i, "time": None, "status": "missing"} for i in (1, 2)],
        "match_status": "unmatched", "final_time_status": "valid",
        "imported_athlete": {"first_name": None, "last_name": "", "birth_year": 2000},
    }
    snapshot = {
        "results": {
            repaired: {**original, "_id": repaired, "rank": 1, "final_time": 16.0,
                       "source_full_name": "Nováková  Anna Marie", "athlete": ObjectId()},
            ambiguous: {**original, "_id": ambiguous, "rank": 2, "final_time": 17.0},
        },
        "athletes": {},
        "competitions": {cid: {"source_url": URL, "date": datetime(2026, 4, 1)}},
    }
    proof = {"source_name": "Nováková Anna Marie", "first_name": "Anna Marie", "last_name": "Nováková",
             "birth_year": 2000, "team": "Lhota", "url": "https://example.com/results.pdf"}
    report = make_plan(snapshot, tmp_path, [proof])
    assert report["counts"]["repairable"] == report["counts"]["to_review"] == 1
    repairs = {item["id"]: item for item in report["updates"]}
    assert repairs[repaired]["set"] == {
        "imported_athlete.first_name": "Anna Marie", "imported_athlete.last_name": "Nováková",
    }
    assert repairs[repaired]["previous"]["imported_athlete.first_name"] == {"present": True, "value": None}
    assert ambiguous not in repairs
    assert repairs[repaired]["evidence"]["published_name"] == "Nováková  Anna Marie"
    assert repairs[repaired]["reason"] == "corroborated_name_fields"
    assert snapshot["results"][repaired]["imported_athlete"]["first_name"] is None
    assert report == make_plan(snapshot, tmp_path, [proof])


def test_verified_pdf_requires_same_source_row_and_does_not_replace_raw_names(tmp_path):
    from hashlib import sha256

    from scripts.migrate_category_catalog import fingerprint

    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    cid, identifier = ObjectId(), ObjectId()
    row = {"_id": identifier, "competition": cid, "source_row": {"rank": 8},
           "source_category": {"name": "Ženy", "discipline": "100m"},
           "start_number": 39, "source_full_name": "Nováková  Anna Ř",
           "source_person_name": {"first_name": None}, "imported_athlete": {"last_name": "Nováková"}}
    proof = {"id": identifier, "url": URL, "file": str(pdf), "sha256": sha256(pdf.read_bytes()).hexdigest(),
             "category_key": "zeny", "page": 2, "bib": 39, "source_row_sha256": fingerprint(row["source_row"]),
             "stored_source_full_name": row["source_full_name"], "published_name": "Nováková Anna",
             "first_name": "Anna", "last_name": "Nováková", "note": "Samostatná buňka jména vedle sloupce OSH."}
    snapshot = {"results": {identifier: row}, "athletes": {}, "competitions": {cid: {"source_url": URL}}}

    plan = make_plan(snapshot, tmp_path, verified_results=[proof])
    update, = plan["updates"]
    assert update["set"] == {"imported_athlete.first_name": "Anna"}
    assert update["previous"]["imported_athlete.first_name"] == {"present": False, "value": None}
    assert row["source_full_name"] == "Nováková  Anna Ř"
    assert row["source_person_name"] == {"first_name": None}

    row["source_row"]["rank"] = 9
    plan = make_plan(snapshot, tmp_path, verified_results=[proof])
    assert plan["updates"] == []
    assert plan["rows"][0]["reason"] == "verified_pdf_locator_conflict"
