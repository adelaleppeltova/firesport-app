"""Plan conservative name repairs from a read-only BSON Extended JSON snapshot."""
import argparse
from collections import Counter, defaultdict
from pathlib import Path
import unicodedata

from bson import json_util

from app.category_catalog import valid_time
from app.person_names import NAME_FIELDS, missing_name, name_issues, normalize_person_name
from app.services.category_normalization import label_key
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file


def source_key(url, category, person, rank, team, time):
    return (url, label_key(category), person.get("birth_year"), rank, label_key(team), time)


def read_source_rows(root):
    rows = defaultdict(list)
    for path in sorted(root.rglob("*.json")):
        try:
            contents = json_util.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeError):
            continue
        if not isinstance(contents, dict):
            continue
        url = contents.get("source_file")
        competition = contents.get("competition")
        if not isinstance(competition, dict) or not isinstance(url, str) or not url.startswith("https://"):
            continue
        for category in competition.get("categories") or []:
            for row in category.get("results") or []:
                key = source_key(url, category.get("name"), row, row.get("rank"), row.get("team"), row.get("final_time"))
                rows[key].append((str(path), row))
    return rows


def normalized_pair(person):
    return tuple(normalize_person_name(person.get(field)).casefold() for field in NAME_FIELDS)


def accentless(value):
    return "".join(char for char in unicodedata.normalize("NFD", value) if not unicodedata.combining(char))


def summary(db, source_rows):
    output = {}
    for collection in ("athletes", "results"):
        counts = Counter()
        issues = []
        proposals = []
        for identifier, row in db[collection].items():
            person = row if collection == "athletes" else row.get("imported_athlete") or {}
            flags = name_issues(person)
            for field in NAME_FIELDS:
                raw = person.get(field)
                if raw == "":
                    counts[f"empty_{field}"] += 1
                elif isinstance(raw, str) and not raw.strip():
                    counts[f"whitespace_only_{field}"] += 1
                elif isinstance(raw, str):
                    cleaned = " ".join(raw.split())
                    if cleaned[0].islower():
                        counts[f"lowercase_initial_{field}"] += 1
                    if cleaned.isupper() and sum(character.isupper() for character in cleaned) > 1:
                        counts[f"uppercase_{field}"] += 1
                    if raw != cleaned:
                        counts[f"spacing_{field}"] += 1
            profile = db["athletes"].get(row.get("athlete"))
            if collection == "results" and profile:
                imported, linked = normalized_pair(person), normalized_pair(profile)
                if all(imported) and all(linked) and imported != linked:
                    if imported == linked[::-1]:
                        flags.append("possible_reversed_linked_names")
                    elif tuple(map(accentless, imported)) == tuple(map(accentless, linked)):
                        flags.append("diacritics_differ_from_linked_profile")
            event = db["competitions"].get(row.get("competition")) or {}
            source = row.get("source_category") or {}
            url = source.get("source_url") or event.get("source_url")
            key = source_key(url, source.get("name"), person, row.get("rank"), row.get("team"), row.get("final_time"))
            matches = source_rows.get(key, []) if collection == "results" else []
            if len(matches) == 1:
                _, original = matches[0]
                if missing_name(person) and not missing_name(original):
                    flags.append("source_named_database_incomplete")
                normalized = normalized_pair(person)
                source_names = normalized_pair(original)
                if all(normalized) and normalized != source_names and normalized == source_names[::-1]:
                    flags.append("possible_reversed_names")
            if not flags:
                continue
            incomplete = missing_name(person)
            counts.update(flags)
            counts["documents_with_issues"] += 1
            if incomplete:
                counts["documents_with_missing_component"] += 1
                if row.get("athlete"):
                    counts["incomplete_linked_results"] += 1
                if row.get("result_type") == "individual" and valid_time(row) is not None:
                    counts["unnamed_valid_individual_results"] += 1
            needs_review = any(not flag.startswith("format_") for flag in flags)
            detail = {
                "id": identifier, "flags": flags, "source_url": url,
                "original": {f: person.get(f) for f in NAME_FIELDS},
            }
            if collection == "results":
                detail.update(category=source.get("name"), competition=row.get("competition"),
                              team=row.get("team"), rank=row.get("rank"), time=row.get("final_time"),
                              birth_year=person.get("birth_year"), status=row.get("classification_status"),
                              match_status=row.get("match_status"), result_type=row.get("result_type"))
            if needs_review:
                counts["manual_review"] += 1
            else:
                counts["automatically_repairable"] += 1
                proposals.append({**detail, "document_sha256": fingerprint(row),
                                  "display_name": {f: normalize_person_name(person.get(f)) for f in NAME_FIELDS}})
            issues.append(detail)
        output[collection] = {"documents": len(db[collection]), "counts": dict(counts),
                              "issues": issues, "proposals": proposals}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = summary(load_snapshot(args.snapshot), read_source_rows(args.source_root))
    with private_file(args.report) as stream:
        stream.write(json_util.dumps(report, indent=2, ensure_ascii=False))
    print({k: {"documents": v["documents"], **v["counts"]} for k, v in report.items()})


if __name__ == "__main__":
    main()
