"""Build an offline, source-backed plan for the already recovered result names."""
import argparse
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from bson import json_util

from app.person_names import normalize_person_name
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file

MANUAL = "manual_review"


def clean(value):
    return " ".join((value or "").split())


def make_plan(snapshot, audit, supplemental):
    extra = {item["id"]: item for item in supplemental}
    if len(extra) != len(supplemental):
        raise ValueError("Duplicitní doplňující doklad.")
    rows = {item["id"]: item for item in audit["rows"]}
    if len(rows) != len(audit["rows"]) or not set(extra) <= rows.keys():
        raise ValueError("Audit a doplňující doklady odkazují na různá ID.")
    counters = Counter()
    updates, review = [], []
    for identifier, proof in rows.items():
        row = snapshot["results"].get(identifier)
        person = (row or {}).get("imported_athlete") or {}
        first, last = (person.get(field) for field in ("first_name", "last_name"))
        counters["source_full_name"] += bool(row and clean(row.get("source_full_name")))
        counters["structured_names"] += bool(clean(first) and clean(last))
        source = (row or {}).get("source_name_evidence") or {}
        extra_proof = extra.get(identifier)
        if (not row or clean(row.get("source_full_name")) != clean(proof["source_name"])
                or source.get("url") != proof["source_url"]
                or source.get("locator") != proof["source_locator"]):
            reason = "source_conflict"
        elif row.get("athlete") is not None or clean(first) or clean(last) or source.get("segmentation"):
            reason = "already_structured_or_linked"
        elif extra_proof and (proof["classification"] != MANUAL
                              or any(extra_proof.get(field) != value for field, value in (
                                  ("source_name", row["source_full_name"]), ("team", row.get("team")),
                                  ("birth_year", person.get("birth_year")),
                              ))):
            reason = "supplemental_source_conflict"
        elif not extra_proof and proof["classification"] == MANUAL:
            reason = "ambiguous"
        else:
            selected = extra_proof or proof
            names = selected["field_boundary"]
            first, last = (normalize_person_name(names[field]) for field in ("first_name", "last_name"))
            evidence = selected["corroborating_sources"]
            if (not first or not last or clean(f"{last} {first}") != clean(row["source_full_name"])
                    or not evidence or any(urlsplit(url).scheme != "https" for url in evidence)):
                reason = "unsupported_segmentation"
            else:
                method = selected["classification"]
                updates.append({
                    "id": identifier, "document_sha256": fingerprint(row),
                    "set": {
                        "imported_athlete.first_name": first,
                        "imported_athlete.last_name": last,
                        "source_name_evidence.segmentation": {
                            "method": method, "sources": evidence,
                            **({"source_note": selected["source_note"]} if selected.get("source_note") else {}),
                            **({"local_pdf": selected["local_pdf"]} if selected.get("local_pdf") else {}),
                        },
                    },
                })
                counters[method] += 1
                continue
        review.append({"id": identifier, "reason": reason})
        counters[reason] += 1
    report = {
        "counts": {**counters, "examined": len(rows), "planned_updates": len(updates)},
        "updates": updates, "review": review,
    }
    report["plan_sha256"] = fingerprint(report)
    return report


def conditional_update(collection, original, operation):
    """Update one fully matching row. Caller controls the approved database and plan."""
    changes = operation["set"]
    if (original["_id"] != operation["id"] or fingerprint(original) != operation["document_sha256"]
            or set(changes) != {"imported_athlete.first_name", "imported_athlete.last_name",
                                "source_name_evidence.segmentation"}):
        raise ValueError("Dokument nebo povolený rozsah operace se změnil.")
    return collection.update_one(
        {"_id": original["_id"], "$expr": {"$eq": ["$$ROOT", {"$literal": original}]}},
        {"$set": changes}, upsert=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Vytvořit pouze lokální report.")
    for arg in ("snapshot", "audit", "supplemental", "report"):
        parser.add_argument(f"--{arg}", required=True, type=Path)
    args = parser.parse_args()
    report = make_plan(load_snapshot(args.snapshot), json_util.loads(args.audit.read_text()),
                       json_util.loads(args.supplemental.read_text()))
    with private_file(args.report) as stream:
        stream.write(json_util.dumps(report, indent=2, ensure_ascii=False))
    print(report["counts"], report["plan_sha256"])


if __name__ == "__main__":
    main()
