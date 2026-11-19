"""Compare an original and fresh dry-run, then back up eligible source-name rows."""
import argparse
from collections import Counter
from hashlib import sha256
from pathlib import Path

from bson import BSON, decode_all, json_util

from app.person_names import NAME_FIELDS, missing_name
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file

FIELDS = {"source_full_name", "source_name_evidence"}


def prepare(snapshot, original, replay):
    current = snapshot["results"]
    replayed = {item["id"]: item for item in replay["updates"]}
    proposals, conflicts, backup = [], [], []
    seen = set()
    for item in original["updates"]:
        identifier = item["id"]
        if identifier in seen:
            raise ValueError(f"Duplicitní ID v původním plánu: {identifier}")
        seen.add(identifier)
        row = current.get(identifier)
        person = (row or {}).get("imported_athlete") or {}
        update = {field: item["set"][field] for field in sorted(FIELDS)}
        if not row:
            reason = "missing_document"
        elif (any(row.get(field) is not None for field in (*FIELDS, "athlete"))
              or not missing_name(person) or any((person.get(field) or "").strip() for field in NAME_FIELDS)):
            reason = "already_edited_or_linked"
        elif fingerprint(row) != item["document_sha256"]:
            reason = "document_changed"
        elif identifier not in replayed or any(
            fingerprint(replayed[identifier]["set"].get(field)) != fingerprint(value)
            for field, value in update.items()
        ) or replayed[identifier]["set"].keys() - (FIELDS | {"match_status", "match_reason"}):
            reason = "source_changed_or_expanded_repair"
        else:
            proposals.append({"id": identifier, "document_sha256": fingerprint(row), "set": update})
            backup.append(row)
            continue
        conflicts.append({"id": identifier, "reason": reason})
    return {
        "target_collection": "results",
        "target_count": len(seen),
        "results_count_before": len(current),
        "updates": proposals,
        "conflicts": conflicts,
        "by_classification": dict(Counter(row.get("classification_status") for row in backup)),
        "fields": sorted(FIELDS),
    }, backup


def write_bundle(output, report, backup):
    output.mkdir(mode=0o700)
    raw = b"".join(BSON.encode(row) for row in backup)
    path = output / "results-before.bson"
    with path.open("xb") as stream:
        path.chmod(0o600)
        stream.write(raw)
    restored = decode_all(path.read_bytes())
    if [(row["_id"], fingerprint(row)) for row in restored] != [
        (item["id"], item["document_sha256"]) for item in report["updates"]
    ]:
        raise ValueError("Zálohu nelze zpětně ověřit proti schváleným vstupům.")
    report["backup_sha256"] = sha256(raw).hexdigest()
    report["plan_sha256"] = fingerprint(report)
    with private_file(output / "approval-plan.json") as stream:
        stream.write(json_util.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ("snapshot", "original", "replay", "output"):
        parser.add_argument(f"--{argument}", required=True, type=Path)
    args = parser.parse_args()
    report, backup = prepare(load_snapshot(args.snapshot), json_util.loads(args.original.read_text()),
                             json_util.loads(args.replay.read_text()))
    write_bundle(args.output, report, backup)
    print({**{key: value for key, value in report.items() if key not in {"updates", "conflicts"}},
           "updates": len(report["updates"]), "conflicts": len(report["conflicts"])})


if __name__ == "__main__":
    main()
