import json
from pathlib import Path

from app.extraction.html import parse_html
from app.extraction.storage import source_id
from scripts.audit_result_times import audit, html_source_check


def test_audit_compares_stored_time_against_archived_official_row(tmp_path):
    url = "https://pozarnisporty.cz/races/1034"
    raw = (Path(__file__).parent / "fixtures/extraction/race-1034.html").read_bytes()
    archive = tmp_path / "snapshots" / source_id(url)
    archive.mkdir(parents=True)
    (archive / "source.html").write_bytes(raw)
    competition, _, _, _ = parse_html(raw, url)
    category, row = next(
        (category, row)
        for category in competition["categories"] if category["discipline"] == "100m"
        for row in category["results"] if (
            row["final_status"] == "valid" and row["first_name"] and row["last_name"]
        )
    )
    published_time = row["final_time"]
    row["final_time"] = 120
    competition["categories"] = [{**category, "results": [row]}]
    data = tmp_path / "data"
    data.mkdir()
    path = data / "race.json"
    contents = json.dumps({"source_file": url, "competition": competition})
    path.write_text(contents, encoding="utf-8")

    report = audit(data, check_source=html_source_check(archive.parent))

    assert report["source_summary"] == {"differs": 1}
    [candidate] = report["candidates"]
    assert candidate["review_status"] == "needs_review"
    assert candidate["final_time"] == 120
    assert candidate["source_check"]["final_time"] == published_time
    assert candidate["source_check"]["provenance"] == "archived_html"
    assert path.read_text(encoding="utf-8") == contents
