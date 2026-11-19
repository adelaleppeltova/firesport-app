"""Plan source-backed repairs for missing names without connecting to MongoDB."""

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
from pathlib import Path

from bson import json_util

from app.extraction.html import parse_html
from app.extraction.storage import canonical_url, source_id
from app.person_names import NAME_FIELDS, missing_name, normalize_person_name
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file
from scripts.recover_source_names import key


def clean(value):
    return " ".join((value or "").split())


def pair(row):
    return tuple(normalize_person_name(row.get(field)) for field in NAME_FIELDS)


def provenance_key(text, year, team):
    text = normalize_person_name(text).casefold()
    team = normalize_person_name(team).casefold()
    return (text, year, team) if text and type(year) is int and any(c.isalpha() for c in team) else None


def source_url(snapshot, row):
    event = snapshot["competitions"].get(row.get("competition"), {})
    url = (row.get("source_category") or {}).get("source_url") or event.get("source_url")
    return canonical_url(url) if isinstance(url, str) and url.startswith("https://") else None


def original_index(source_dir, urls):
    originals = {}
    for url in sorted(urls - {None}):
        path = source_dir / source_id(url) / "source.html"
        if not path.is_file():
            originals[url] = {"error": "source_unavailable"}
            continue
        raw = path.read_bytes()
        evidence = {"url": url, "path": str(path), "sha256": sha256(raw).hexdigest()}
        refs = {}
        try:
            race, _, _, _ = parse_html(raw, url, observe_name=lambda row, ref: refs.update({id(row): ref}))
        except ValueError as exc:
            originals[url] = {"error": "source_layout_unresolved", "detail": str(exc), "evidence": evidence}
            continue
        results = defaultdict(list)
        for category in race["categories"]:
            for entry in category["results"]:
                scope = key(category["name"], category["discipline"], entry, source=True)
                results[scope].append((entry, refs.get(id(entry))))
        originals[url] = {"results": results, "date": race["date"], "evidence": evidence}
    return originals


def supporting_names(snapshot, supplemental):
    support = defaultdict(list)
    for row in snapshot["results"].values():
        person = row.get("imported_athlete") or {}
        prior = (row.get("source_name_evidence") or {}).get("segmentation")
        identity = provenance_key(row.get("source_full_name"), person.get("birth_year"), row.get("team"))
        if prior and identity and all(pair(person)):
            support[identity].append((pair(person), {"result_id": row["_id"], **prior}))
    for item in supplemental:
        identity = provenance_key(item["source_name"], item["birth_year"], item["team"])
        names = pair(item)
        if not identity or not all(names) or not item["url"].startswith("https://"):
            raise ValueError("Neúplný doplňující doklad jména.")
        if "file" in item and sha256(Path(item["file"]).read_bytes()).hexdigest() != item.get("sha256"):
            raise ValueError("Doplňující výsledková listina se změnila.")
        if normalize_person_name(f"{names[1]} {names[0]}").casefold() != identity[0]:
            raise ValueError("Doplňující doklad mění znění jména.")
        support[identity].append((names, item))
    return support


def original_match(source, scope, day):
    if source.get("date") not in (None, day):
        return None
    rows = source.get("results", {})
    candidates = rows.get(scope, ())
    if not candidates and scope[1] is not None:
        # Older official lists omit discipline. Category, team, rank, bib and all times still agree.
        candidates = rows.get((scope[0], None, *scope[2:]), ())
    return candidates[0] if len(candidates) == 1 else None


def event_day(snapshot, row):
    event = snapshot["competitions"].get(row.get("competition"), {})
    date = event.get("date")
    return date.date().isoformat() if hasattr(date, "date") else date


def make_plan(snapshot, source_dir, supplemental=()):
    rows = snapshot["results"]
    targets = {
        identifier: row for identifier, row in rows.items()
        if missing_name(row.get("imported_athlete") or {}) and row.get("result_type") != "team"
    }
    urls = {identifier: source_url(snapshot, row) for identifier, row in targets.items()}
    originals = original_index(source_dir, set(urls.values()))
    support = supporting_names(snapshot, supplemental)
    links = defaultdict(list)
    located = {}
    matching_database_rows = Counter()
    for identifier, row in targets.items():
        url = urls[identifier]
        source = originals.get(url, {"error": "source_url_missing"})
        category = row.get("source_category") or {}
        scope = key(category.get("name"), category.get("discipline"), row)
        match = original_match(source, scope, event_day(snapshot, row))
        located[identifier] = (source, scope, match)
        if match:
            matching_database_rows[url, id(match[0])] += 1
            published, ref = match
            person = row.get("imported_athlete") or {}
            identity = provenance_key(published.get("source_full_name"), person.get("birth_year"), published.get("team"))
            if ref and identity and support.get(identity):
                links[ref].append((identity[:2], support[identity], url))
    updates, details = [], []
    counts = Counter()
    for identifier, row in targets.items():
        person = row.get("imported_athlete") or {}
        source, scope, match = located[identifier]
        old_name = row.get("source_full_name")
        detail = {"id": identifier, "source_url": urls[identifier], "locator": scope, "source_name": old_name,
                  "birth_year": person.get("birth_year"), "team": row.get("team"),
                  "classification": row.get("classification_status"), "before": {f: person.get(f) for f in NAME_FIELDS}}
        if source.get("evidence"):
            detail["original"] = source["evidence"]
        if match is None:
            reason = source.get("error", "original_row_unverified")
            detail["original_error"] = source.get("detail")
            alternatives = []
            for candidate_scope, entries in source.get("results", {}).items():
                if (candidate_scope == scope or candidate_scope[0] == scope[0]
                        and scope[2] is not None and scope[3] is not None and candidate_scope[2:6] == scope[2:6]):
                    alternatives.extend(
                        {"locator": candidate_scope, "source_name": entry.get("source_full_name")}
                        for entry, _ in entries
                    )
            if alternatives:
                detail["original_candidates"] = alternatives
        elif matching_database_rows[urls[identifier], id(match[0])] != 1:
            reason = "database_row_ambiguous"
        else:
            published, ref = match
            raw = published.get("source_full_name")
            detail["published_name"] = raw
            names = pair(published)
            identity = provenance_key(raw, person.get("birth_year"), row.get("team"))
            corroborations = list(support.get(identity, ()))
            # An organizer's original participant link can carry proof across lists with an empty club.
            # The original full text and stored birth year must still agree.
            if identity is None and ref and raw and person.get("birth_year"):
                label = normalize_person_name(raw).casefold(), person["birth_year"]
                corroborations.extend(
                    (parts, {**proof, "same_organizer_occurrence": url})
                    for linked_label, linked_proof, url in links[ref] if linked_label == label
                    for parts, proof in linked_proof
                )
            choices = {parts for parts, _ in corroborations}
            if all(names):
                choices.add(names)
            detail["supporting"] = [proof for _, proof in corroborations]
            if not raw:
                reason = "name_unpublished"
            elif old_name and clean(raw) != clean(old_name):
                reason = "source_text_conflict"
            elif published.get("birth_year") not in (None, person.get("birth_year")) and person.get("birth_year") is not None:
                reason = "source_year_conflict"
            elif len(choices) != 1:
                reason = "segmentation_conflict" if choices else "ambiguous_segmentation"
            else:
                names = next(iter(choices))
                if any(value and value != candidate for value, candidate in zip(pair(person), names)):
                    reason = "stored_name_conflict"
                else:
                    reason = "repairable"
                    detail["after"] = dict(zip(NAME_FIELDS, names, strict=True))
        change = {}
        if reason == "repairable":
            for field, value in detail["after"].items():
                if not normalize_person_name(person.get(field)):
                    change[f"imported_athlete.{field}"] = value
        raw = detail.get("published_name")
        if raw and not old_name and reason != "source_year_conflict":
            change["source_full_name"] = raw
        manual = (row.get("match_reason") or "").startswith("manual_admin_")
        if row.get("athlete") is None and not manual and row.get("match_status") != "matched":
            status = "needs_review"
            match_reason = (
                "source_name_restored_identity_unverified" if reason == "repairable"
                else "name_segmentation_review" if old_name or raw else "missing_name"
            )
            for field, value in (("match_status", status), ("match_reason", match_reason)):
                if row.get(field) != value:
                    change[field] = value
        if change:
            updates.append({"id": identifier, "document_sha256": fingerprint(row), "set": change,
                            "previous": {
                                field: {"present": field.rsplit(".", 1)[-1] in owner,
                                        "value": owner.get(field.rsplit(".", 1)[-1])}
                                for field in change
                                for owner in (person if field.startswith("imported_athlete.") else row,)
                            }})
        detail["reason"] = reason
        details.append(detail)
        counts[reason] += 1
    unchanged = len(rows) - len(updates)
    report = {
        "counts": {
            "results": len(rows), "profiles": len(snapshot["athletes"]),
            "profiles_with_missing_name": sum(missing_name(p) for p in snapshot["athletes"].values()),
            "incomplete_individual_or_unclassified": len(targets),
            "literal_null_names": {
                field: sum(field in person and person[field] is None
                           for row in targets.values() for person in (row.get("imported_athlete") or {},))
                for field in NAME_FIELDS
            },
            "nameless_team_totals": sum(r.get("result_type") == "team" and missing_name(r.get("imported_athlete") or {})
                                        for r in rows.values()),
            "repairable": counts["repairable"], "to_review": len(targets) - counts["repairable"],
            "original_rows_verified": sum("published_name" in detail for detail in details),
            "source_text_to_add": sum("source_full_name" in op["set"] for op in updates),
            "updates": len(updates), "unchanged": unchanged, "outcomes": dict(counts),
            "original_urls": len(originals), "originals_parsed": sum("results" in item for item in originals.values()),
        },
        "rows": details, "updates": updates,
    }
    report["plan_sha256"] = fingerprint(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("snapshot", "sources", "report"):
        parser.add_argument(f"--{argument}", type=Path, required=True)
    parser.add_argument("--supporting", type=Path)
    args = parser.parse_args()
    supplemental = json_util.loads(args.supporting.read_text(encoding="utf-8")) if args.supporting else ()
    plan = make_plan(load_snapshot(args.snapshot), args.sources, supplemental)
    with private_file(args.report) as report:
        report.write(json_util.dumps(plan, ensure_ascii=False, indent=2))
    print(plan["counts"], plan["plan_sha256"])


if __name__ == "__main__":
    main()
