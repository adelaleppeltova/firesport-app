"""Corroborate individual start rows from saved organizer pages without profile lookups."""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

from bson import json_util
from bs4 import BeautifulSoup

from app.extraction.html import parse_html
from app.services.category_normalization import label_key
from app.services.category_source_rules import event_identity
from app.services.data_import import DataImporter
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file


def performance_key(identity):
    return (
        identity["start_number"], identity["rank"], identity["team"], identity["final_time"],
        identity["final_time_status"], tuple(attempt[:3] for attempt in identity["times"]),
    )


def verify_rows(db, baseline, folder):
    by_event = defaultdict(list)
    importer = DataImporter()
    for entry in baseline["manual_review"]:
        row = db["results"][entry["id"]]
        person = row.get("imported_athlete") or {}
        if row.get("athlete") or not row.get("start_number") or row.get("rank") is None:
            continue
        if (entry["reason"] == "unverified_team_or_progression"
                or entry["reason"] == "missing_verified_individual_or_birth_year" and type(person.get("birth_year")) is int):
            by_event[row["competition"]].append(row)
    proofs = []
    for event, rows in by_event.items():
        original = db["competitions"][event]
        url = original.get("source_url")
        if not url:
            continue
        source_id = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
        if not source_id.isdecimal():
            continue
        page = folder / f"{source_id}.html"
        if not page.exists():
            continue
        raw = page.read_bytes()
        document = BeautifulSoup(raw, "html.parser")
        if (not document.find(string=lambda string: string and "Singles - results" in string)
                or document.find(string=lambda string: string and "Teams - results" in string)):
            continue
        published, _, _, _ = parse_html(raw, url)
        if event_identity(original)[0] != published["date"]:
            continue
        digest = sha256(raw).hexdigest()
        for row in rows:
            key = performance_key(importer._row_identity(row))
            candidates = []
            for category in published["categories"]:
                for source_row in category["results"]:
                    if source_row.get("start_number") is None or str(source_row["start_number"]) != key[0]:
                        continue
                    record = importer.build_result_row(source_row, str(row["category"]), str(event))
                    if performance_key(importer._row_identity(record)) == key:
                        candidates.append(category["name"])
            legacy_name = db["categories"][row["category"]]["name"]
            if len(candidates) == 1 and label_key(candidates[0]) == label_key(legacy_name):
                proofs.append({"id": row["_id"], "row_sha256": fingerprint(row), "source_url": url,
                               "source_sha256": digest, "source_category": candidates[0]})
    return {"version": 1, "individual_rows": sorted(proofs, key=lambda proof: str(proof["id"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("snapshot", "baseline", "html-dir", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    args = parser.parse_args()
    result = verify_rows(load_snapshot(args.snapshot),
                         json_util.loads(args.baseline.read_text(encoding="utf-8")), args.html_dir)
    with private_file(args.output) as handle:
        handle.write(json_util.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Ověřených individuálních řádků: {len(result['individual_rows'])}.")


if __name__ == "__main__":
    main()
