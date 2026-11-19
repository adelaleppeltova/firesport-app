"""Inventory local result files and locate their rows in the database snapshot."""

from collections import Counter, defaultdict
from datetime import date, datetime
from hashlib import sha256
import json
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from app.category_catalog import BY_ID
from app.extraction.validation import SCHEMA_PATH, validate
from app.services.category_normalization import label_key, source_discipline
from app.services.data_import import DataImporter


def reject_constant(value):
    raise ValueError(f"Neplatná číselná hodnota {value}")


def source_url(value):
    if not value or not isinstance(value, str):
        return None
    parts = urlsplit(value)
    return parts._replace(fragment="").geturl() if parts.scheme in ("https", "http") and parts.netloc else None


def exact_metadata(race):
    day = race.get("date")
    if isinstance(day, datetime):
        day = day.date().isoformat()
    return label_key(race.get("name")), label_key(race.get("place")), day


def identity_key(row, *, legacy=False):
    identity = DataImporter._row_identity(row)
    return (identity["name"], identity["birth_year"], identity["team"], identity["start_number"],
            identity["rank"], identity["final_time"], identity["final_time_status"],
            tuple(identity["times"]), None if legacy else identity["fscode"])


def audit_sources(root, snapshot):
    importer = DataImporter()
    urls, metadata, dates = (defaultdict(set) for _ in range(3))
    by_scope, by_performance, raw_rows = (defaultdict(set) for _ in range(3))
    competitions = snapshot["competitions"]
    rows = snapshot["results"]
    for cid, race in competitions.items():
        if url := source_url(race.get("source_url")):
            urls[url].add(cid)
        key = exact_metadata(race)
        metadata[key].add(cid)
        dates[key[2]].add(cid)
    for rid, row in rows.items():
        cid = row["competition"]
        group = row.get("source_category") or {}
        if url := source_url(group.get("source_url")):
            urls[url].add(cid)
        try:
            performance = identity_key(row, legacy=True)
        except (TypeError, ValueError, KeyError):
            continue
        canon = BY_ID.get(row.get("category"))
        names = {label_key(group.get("name"))}
        if canon is not None:
            names.add(label_key(canon.name))
        disciplines = {source_discipline(group.get("discipline")), row.get("discipline")}
        for name in names:
            for discipline in disciplines:
                by_scope[cid, name, discipline, performance].add(rid)
        by_performance[cid, performance].add(rid)
        if isinstance(row.get("source_row"), dict):
            signature = json.dumps(row["source_row"], sort_keys=True, ensure_ascii=False)
            raw_rows[cid, signature].add(rid)

    paths = sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".json")
    if not paths:
        raise ValueError(f"Nenalezeny žádné JSON soubory v {root}.")
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()), format_checker=FormatChecker())
    hashes, entries = {}, []
    counts = Counter()
    uncovered = []
    for path in paths:
        name = path.relative_to(root).as_posix()
        payload = path.read_bytes()
        hashes[name] = sha256(payload).hexdigest()
        item = {"path": name}
        entries.append(item)
        try:
            document = json.loads(payload.decode("utf-8-sig"), parse_constant=reject_constant)
            race = document["competition"]
            categories = race["categories"]
            if not isinstance(categories, list) or any(not isinstance(cat["results"], list) for cat in categories):
                raise ValueError("Neplatná struktura výsledkových listin.")
        except (KeyError, TypeError, ValueError) as exc:
            item["file_error"] = str(exc)
            counts["unreadable_json"] += 1
            continue
        warnings = document.get("warnings") or []
        if warnings:
            item["source_warnings"] = warnings
            counts["source_warnings"] += len(warnings)
        errors = list(validator.iter_errors(document))
        if errors:
            item["schema_errors"] = [{"field": "/" + "/".join(map(str, err.absolute_path)),
                                      "rule": err.validator} for err in errors]
            counts["files_with_schema_deviations"] += 1
        else:
            try:
                validate(document)
            except ValueError as exc:
                item["content_error"] = str(exc)
                counts["files_with_content_errors"] += 1
        key = exact_metadata(race)
        exact_ids = metadata.get(key, set())
        url_ids = urls.get(source_url(document.get("source_file")), set())
        same_day = dates.get(key[2], set())
        event_ids = exact_ids & url_ids or exact_ids or (url_ids & same_day)
        if not event_ids:
            # Same-day candidates can identify legacy aliases by an identical published row.
            event_ids = same_day
        item["event_candidates"] = sorted(event_ids)
        counts["rows"] += sum(len(cat["results"]) for cat in categories)
        found = Counter()
        for ci, cat in enumerate(categories, 1):
            label = label_key(cat.get("name"))
            discipline = source_discipline(cat.get("discipline"))
            for ri, raw in enumerate(cat["results"], 1):
                position = {"path": name, "category": ci, "row": ri}
                try:
                    row = importer.build_result_row(raw, None, None)
                    performance = identity_key(row, legacy=True)
                except (TypeError, AttributeError, ValueError, KeyError) as exc:
                    uncovered.append({**position, "reason": "invalid_source_row", "error": str(exc)})
                    found["invalid_source_row"] += 1
                    continue
                signature = json.dumps(raw, sort_keys=True, ensure_ascii=False)
                candidates = set().union(*(raw_rows[cid, signature] for cid in event_ids))
                if not candidates:
                    for cid in event_ids:
                        candidates.update(by_scope[cid, label, discipline, performance])
                        if not discipline:
                            candidates.update(by_scope[cid, label, None, performance])
                relation = "represented"
                if not candidates:
                    for cid in exact_ids or (url_ids & same_day):
                        candidates.update(by_performance[cid, performance])
                    relation = "matching_performance_other_list"
                preferred = {i for i in candidates if rows[i].get("duplicate_of") is None}
                candidates = preferred or candidates
                if len(candidates) == 1:
                    found[relation] += 1
                    continue
                reason = "ambiguous_source_row" if candidates else "source_row_needs_comparison"
                found[reason] += 1
                uncovered.append({**position, "reason": reason, "candidates": sorted(candidates)})
        item["counts"] = dict(found)
        counts.update(found)
        if not exact_ids and not url_ids & same_day and event_ids and found["represented"] == 0:
            item["event_issue"] = "no_confirmed_event_reference"
        try:
            complete_metadata = bool(key[0] and key[1]) and date.fromisoformat(key[2]).isoformat() == key[2]
        except (ValueError, TypeError):
            complete_metadata = False
        if not complete_metadata:
            item["event_issue"] = "incomplete_race_metadata"
    return {"counts": {"json_files": len(paths), **counts}, "hashes": hashes,
            "files": entries, "unresolved_rows": uncovered}
