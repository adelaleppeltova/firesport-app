"""Compare a current read-only Mongo snapshot, a prior snapshot and local result JSON."""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

from bson import json_util

from app.extraction.storage import canonical_url
from app.person_names import NAME_FIELDS, missing_name, name_issues
from app.services.category_normalization import label_key, source_discipline
from app.services.result_review import in_review_queue
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file
from scripts.recover_source_names import key


def event_date(event):
    day = event.get("date")
    return day.date().isoformat() if hasattr(day, "date") else day


def event_key(event):
    return event_date(event), label_key(event.get("name")), label_key(event.get("place"))


def web_url(url):
    return canonical_url(url) if isinstance(url, str) and url.startswith(("http://", "https://")) else None


def categories(snapshot, row):
    original = row.get("source_category") or {}
    legacy = snapshot["categories"].get(row.get("legacy_category", row.get("category")), {})
    return original.get("name") or legacy.get("name"), original.get("discipline") or legacy.get("discipline")


def row_scope(name, discipline, row, *, source=False):
    return key(name, source_discipline(discipline) or label_key(discipline), row, source=source)


def database_index(snapshot):
    events = defaultdict(set)
    exact_rows = defaultdict(set)
    performance = defaultdict(set)
    nearby = defaultdict(set)
    for identifier, event in snapshot["competitions"].items():
        events["metadata", event_key(event)].add(identifier)
        if url := web_url(event.get("source_url")):
            events["url", (event_date(event), url)].add(identifier)
    for identifier, row in snapshot["results"].items():
        cid = row.get("competition")
        name, discipline = categories(snapshot, row)
        event = snapshot["competitions"].get(cid, {})
        if url := web_url((row.get("source_category") or {}).get("source_url")):
            events["url", (event_date(event), url)].add(cid)
        raw = row.get("source_row")
        scope = row_scope(name, discipline, row)
        if isinstance(raw, dict):
            exact_rows[cid, scope[0], scope[1], fingerprint(raw)].add(identifier)
        for current in (scope, row_scope(name, discipline, raw, source=True) if isinstance(raw, dict) else scope):
            performance[cid, current].add(identifier)
            if current[2] is not None or current[3] is not None:
                nearby[cid, current[:6]].add(identifier)
    return events, exact_rows, performance, nearby


def compatible(row, published):
    person = row.get("imported_athlete") or {}
    originals = [row.get("source_person_name") or {}, row.get("source_row") or {}]
    for field in (*NAME_FIELDS, "birth_year", "fscode"):
        expected = published.get(field)
        values = [data.get(field) for data in originals if data.get(field) not in (None, "")]
        if not values:
            values = [person.get(field)]
        if expected not in (None, "") and any(
            value not in (None, "") and label_key(str(expected)) != label_key(str(value)) for value in values
        ):
            return False
    names = [record.get("source_full_name") for record in (row, originals[1])]
    return all(not name or not published.get("source_full_name")
               or label_key(name) == label_key(published["source_full_name"]) for name in names)


def source_relationship(snapshot, index, event, url, category, row):
    events, exact_rows, performance, nearby = index
    proven = events["url", (event_date(event), url)] if url else set()
    metadata = event_key(event)
    candidates = proven or (events["metadata", metadata] if all(metadata) else set())
    if not candidates:
        return "event_unlocated", set()
    if len(candidates) != 1:
        return "event_ambiguous", set()
    cid = next(iter(candidates))
    scope = row_scope(category.get("name"), category.get("discipline"), row, source=True)
    exact = exact_rows[cid, scope[0], scope[1], fingerprint(row)]
    if len(exact) == 1:
        return "exact_source_row", exact
    if len(exact) > 1:
        return "ambiguous_rows", exact
    # Require an explicit rank or bib and a second locator beyond event/category.
    strong_locator = (scope[2] is not None or scope[3] is not None) and (
        bool(scope[4]) or scope[5] is not None or scope[2] is not None and scope[3] is not None
    )
    matches = performance[cid, scope] if strong_locator else set()
    compatible_matches = {i for i in matches if compatible(snapshot["results"][i], row)}
    if len(compatible_matches) == 1:
        return "matching_row_locators", compatible_matches
    if compatible_matches:
        return "ambiguous_rows", compatible_matches
    possible = matches or nearby[cid, scope[:6]]
    return ("possible_or_conflicting_rows" if possible else "row_unlocated"), possible


def compare_sources(snapshot, root):
    index = database_index(snapshot)
    details, skipped = [], []
    counts = Counter()
    matched_ids = set()
    for path in sorted(root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            skipped.append(str(path))
            continue
        event = payload.get("competition") if isinstance(payload, dict) else None
        if not isinstance(event, dict) or not isinstance(event.get("categories"), list):
            counts["non_result_files"] += 1
            continue
        counts["files"] += 1
        url = web_url(payload.get("source_file"))
        for group_index, category in enumerate(event["categories"], 1):
            for row_index, row in enumerate(category.get("results") or [], 1):
                if not missing_name(row):
                    continue
                relationship, ids = source_relationship(snapshot, index, event, url, category, row)
                counts[relationship] += 1
                detail = {"path": str(path), "source_url": url, "category": category.get("name"),
                          "category_index": group_index, "row": row_index, "rank": row.get("rank"),
                          "source_person_name": {field: row[field] for field in NAME_FIELDS if field in row},
                          "source_full_name": row.get("source_full_name"), "relationship": relationship,
                          "database_candidates": sorted(ids, key=str)}
                if relationship in {"exact_source_row", "matching_row_locators"}:
                    identifier = next(iter(ids))
                    matched_ids.add(identifier)
                    stored = snapshot["results"][identifier]
                    person = stored.get("imported_athlete") or {}
                    complete = not missing_name(person)
                    counts["confirmed_complete" if complete else "confirmed_incomplete"] += 1
                    if not complete and in_review_queue(stored):
                        counts["confirmed_missing_in_admin"] += 1
                    detail.update(imported_athlete={field: person.get(field) for field in NAME_FIELDS},
                                  database_missing_name=not complete, in_admin_queue=in_review_queue(stored),
                                  classification=stored.get("classification_status"))
                details.append(detail)
    counts["source_rows_with_missing_name"] = len(details)
    counts["confirmed_unique_database_results"] = len(matched_ids)
    return {"counts": dict(counts), "unreadable_files": skipped, "rows": details}


def count_database(rows):
    total = Counter()
    missing_by_classification = Counter()
    for row in rows:
        total["results"] += 1
        person = row.get("imported_athlete") or {}
        in_admin = in_review_queue(row)
        if in_admin:
            total["admin_queue"] += 1
            total["admin_name_issues"] += bool(name_issues(person))
        if missing_name(person):
            missing_by_classification[row.get("classification_status") or "(unset)"] += 1
            total["missing_name"] += 1
            total["missing_name_excluding_teams"] += row.get("result_type") != "team"
            total["admin_missing_name"] += in_admin
            total["linked_missing_name"] += row.get("athlete") is not None
    return {**total, "missing_by_classification": dict(missing_by_classification)}


def compare_snapshots(previous, current):
    old, new = previous["results"], current["results"]
    added = new.keys() - old.keys()
    missing_old = {i for i, r in old.items() if missing_name(r.get("imported_athlete") or {})}
    missing_new = {i for i, r in new.items() if missing_name(r.get("imported_athlete") or {})}
    groups = defaultdict(list)
    for identifier in sorted(added, key=str):
        groups[new[identifier].get("competition")].append(new[identifier])
    events = []
    for identifier, rows in groups.items():
        event = current["competitions"].get(identifier, {})
        events.append({"competition_id": identifier, "name": event.get("name"),
                       "url": event.get("source_url"), "first_created_at": min(
                           (r["created_at"] for r in rows if r.get("created_at")), default=None),
                       **count_database(rows)})
    return {"previous": count_database(old.values()), "current": count_database(new.values()),
            "added": len(added), "removed": len(old.keys() - new.keys()),
            "previously_complete_now_missing": len((missing_new & old.keys()) - missing_old),
            "previously_missing_now_complete": len((missing_old & new.keys()) - missing_new),
            "added_by_competition": sorted(events, key=lambda e: str(e["first_created_at"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("previous", "snapshot", "source-root", "report"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    args = parser.parse_args()
    previous, current = map(load_snapshot, (args.previous, args.snapshot))
    report = {"database": compare_snapshots(previous, current), "sources": compare_sources(current, args.source_root)}
    with private_file(args.report) as stream:
        stream.write(json_util.dumps(report, indent=2, ensure_ascii=False))
    print({**report["database"], "sources": report["sources"]["counts"]})


if __name__ == "__main__":
    main()
