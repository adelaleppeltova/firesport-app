"""Prepare source-backed name repairs entirely offline from a read-only snapshot."""
import argparse
import ast
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re

from bson import json_util

from app.extraction.html import parse_html
from app.extraction.storage import canonical_url, source_id
from app.person_names import missing_name
from app.services.category_normalization import label_key
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file

WARNING = re.compile(r"^(.+?) / .+ / rank (\d+)\.?\s*: ambiguous name segmentation: (.+)$")
REGION = re.compile(
    r"\s+\((?:Praha|Středočeský|Jihočeský|Plzeňský|Karlovarský|Ústecký|Liberecký|"
    r"Královéhradecký|Pardubický|Vysočina|Jihomoravský|Olomoucký|Zlínský|Moravskoslezský|)\)$"
)


def key(category, discipline, row, *, source=False):
    start = row.get("start_number")
    number = str(int(start)) if str(start).isdigit() else start
    return (
        label_key(category), discipline, row.get("rank"), number,
        label_key(re.sub(r"\bSDH\b", "", row.get("team") or "", flags=re.I)),
        row.get("final_time"), row.get("final_status" if source else "final_time_status"),
        tuple((a.get("try" if source else "attempt"), a.get("time"), a.get("status"), a.get("invalid_reason"))
              for a in row.get("times") or []),
    )


def warnings_by_rank(document):
    result = defaultdict(set)
    for warning in document.get("warnings") or []:
        if match := WARNING.fullmatch(warning):
            try:
                name = ast.literal_eval(match[3])
            except (ValueError, SyntaxError):
                continue
            if isinstance(name, str) and name.strip():
                result[label_key(match[1]), int(match[2])].add(name.strip())
    return result


def load_sources(root, diagnostics, urls):
    indexed = defaultdict(list)
    for path in sorted(root.rglob("*.json")) + sorted(diagnostics.glob("*/pending.json")):
        try:
            payload = json.loads(path.read_text())
        except (ValueError, UnicodeError):
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("source_file"), str):
            continue
        url = canonical_url(payload["source_file"])
        if url in urls:
            indexed[url].append((path, payload, "json"))
    for url in sorted(urls):
        path = diagnostics / source_id(url) / "source.html"
        if not path.is_file():
            continue
        try:
            competition, _, warnings, _ = parse_html(path.read_bytes(), url)
        except ValueError:
            continue
        indexed[url].append((path, {"competition": competition, "warnings": warnings}, "html"))
    return indexed


def inspect_source(scope, competition_date, original_year, source):
    path, payload, kind = source
    event = payload.get("competition") or {}
    if event.get("date") != competition_date:
        return None
    candidates = [
        (category, current) for category in event.get("categories", []) for current in category.get("results", [])
        if key(category.get("name"), category.get("discipline"), current, source=True) == scope
    ]
    if len(candidates) != 1:
        return None
    category, current = candidates[0]
    if original_year is not None and current.get("birth_year") not in (None, original_year):
        return None
    full = current.get("source_full_name")
    complete = not missing_name(current)
    if not full and complete:
        full = f"{current['first_name']} {current['last_name']}"
    if not full and current.get("rank") is not None:
        names = warnings_by_rank(payload)[label_key(category.get("name")), current["rank"]]
        rank_count = sum(row.get("rank") == current["rank"] for row in category["results"])
        bib = scope[3]
        suffix = re.compile(rf"\s+\(0*{re.escape(bib)}\)$") if bib and str(bib).isdigit() else None
        if rank_count != 1:
            names = {name for name in names if suffix and suffix.search(name)}
        if len(names) == 1:
            original_warning_name = next(iter(names))
            without_bib = suffix.sub("", original_warning_name) if suffix else original_warning_name
            full = REGION.sub("", without_bib)
            kind = "warning"
    if not full or not full.strip():
        return None
    return {
        **({"warning_source_text": original_warning_name} if kind == "warning" else {}),
        "name": full, "kind": kind, "path": str(path), "sha256": sha256(path.read_bytes()).hexdigest(),
        "structured": {field: current[field] for field in ("first_name", "last_name")} if complete else None,
    }


def plan(db, root, diagnostics):
    urls = set()
    rows = []
    duplicate_scope = defaultdict(int)
    for row in db["results"].values():
        event = db["competitions"].get(row.get("competition"), {})
        category = row.get("source_category") or {}
        locator = category.get("source_url") or event.get("source_url")
        url = canonical_url(locator) if locator else None
        scope = key(category.get("name"), category.get("discipline"), row)
        duplicate_scope[row.get("competition"), url, scope] += 1
        if missing_name(row.get("imported_athlete") or {}) and not row.get("source_full_name"):
            rows.append((row, event, url, scope))
            if url:
                urls.add(url)
    sources = load_sources(root, diagnostics, urls)
    details, changes = [], []
    for row, event, url, scope in rows:
        date = event.get("date")
        date = date.date().isoformat() if hasattr(date, "date") else date
        person = row.get("imported_athlete") or {}
        matched = []
        if duplicate_scope[row.get("competition"), url, scope] == 1:
            for source in sources.get(url, []):
                if evidence := inspect_source(scope, date, person.get("birth_year"), source):
                    matched.append(evidence)
        spellings = {" ".join(item["name"].split()) for item in matched}
        structured = {(item["structured"]["first_name"], item["structured"]["last_name"])
                      for item in matched if item["structured"]}
        resolved = len(spellings) == 1 and len(structured) <= 1
        detail = {"id": row["_id"], "source_url": url, "locator": scope, "evidence": matched,
                  "available_sources": [str(item[0]) for item in sources.get(url, [])],
                  "profile_link_verified": False, "structured": bool(structured) and resolved}
        details.append(detail)
        if not resolved:
            continue
        preferred = next((item for item in matched if item["kind"] == "html"), matched[0])
        updates = {"source_full_name": preferred["name"],
                   "source_name_evidence": {"url": url, "locator": scope, **preferred}}
        if not row.get("athlete"):
            updates.update(match_status="needs_review", match_reason="name_segmentation_review")
            if structured:
                first, last = next(iter(structured))
                if all(not person.get(field) or person[field] == val for field, val in
                       (("first_name", first), ("last_name", last))):
                    updates["imported_athlete"] = {**person, "first_name": first, "last_name": last}
                    updates["match_reason"] = "source_name_restored_identity_unverified"
        changes.append({"id": row["_id"], "document_sha256": fingerprint(row), "set": updates})
    return {"counts": {
        "examined": len(rows), "source_name_recoverable": len(changes),
        "structured_recoverable": sum(item["structured"] for item in details),
        "source_only": sum("imported_athlete" not in item["set"] for item in changes),
        "without_source_name": len(rows) - len(changes), "manual_review": len(rows),
        "planned_updates": len(changes),
    }, "rows": details, "updates": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Pouze lokální report (výchozí režim).")
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--diagnostics", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = plan(load_snapshot(args.snapshot), args.source_root, args.diagnostics)
    with private_file(args.report) as stream:
        stream.write(json_util.dumps(report, ensure_ascii=False, indent=2))
    print(report["counts"])


if __name__ == "__main__":
    main()
