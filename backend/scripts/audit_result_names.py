"""Inspect result identity and athlete references using only MongoDB reads."""

import argparse
import json
import os
from collections import Counter
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.result_values import NAME_FIELDS, invalid_name_fields

RESULT_PROJECTION = dict.fromkeys(
    (
        "_id",
        "competition",
        "category",
        "start_number",
        "rank",
        "athlete",
        "match_status",
        "imported_athlete.first_name",
        "imported_athlete.last_name",
        *NAME_FIELDS,
    ),
    1,
)


def athlete_id(reference):
    if isinstance(reference, ObjectId):
        return reference
    if isinstance(reference, str) and ObjectId.is_valid(reference):
        return ObjectId(reference)
    return None


def audit_result_names(db, *, batch_size=500):
    """Inspect all rows, joining each batch against projected athlete identities."""
    affected = []
    links = Counter()
    reasons = Counter()
    scanned = 0
    with (
        db["results"]
        .find({}, projection=RESULT_PROJECTION)
        .batch_size(batch_size) as results
    ):
        while batch := list(islice(results, batch_size)):
            ids = {
                oid
                for row in batch
                if (oid := athlete_id(row.get("athlete"))) is not None
            }
            athletes = (
                {
                    athlete["_id"]: athlete
                    for athlete in db["athletes"].find(
                        {"_id": {"$in": list(ids)}},
                        projection=dict.fromkeys(NAME_FIELDS, 1),
                    )
                }
                if ids
                else {}
            )
            scanned += len(batch)
            for row in batch:
                reference = row.get("athlete")
                oid = athlete_id(reference)
                linked = athletes.get(oid)
                if oid is not None:
                    links[oid] += 1
                fields = {}
                if "imported_athlete" in row:
                    if names := invalid_name_fields(row["imported_athlete"]):
                        fields["imported_athlete"] = list(names)
                elif any(field in row for field in NAME_FIELDS):
                    if names := invalid_name_fields(row):
                        fields["legacy_result"] = list(names)
                elif not linked:
                    fields["no_stored_identity"] = list(NAME_FIELDS)
                if linked and (names := invalid_name_fields(linked)):
                    fields["linked_athlete"] = list(names)
                if not fields:
                    continue
                reasons.update(fields.keys())
                link = (
                    "unlinked"
                    if reference is None
                    else "invalid_reference"
                    if oid is None
                    else "missing_athlete"
                    if linked is None
                    else "linked"
                )
                affected.append(
                    {
                        "result_id": str(row["_id"]),
                        "competition_id": str(row["competition"])
                        if row.get("competition")
                        else None,
                        "category_id": str(row["category"])
                        if row.get("category")
                        else None,
                        "start_number": row.get("start_number"),
                        "rank": row.get("rank"),
                        "match_status": row.get("match_status"),
                        "athlete_id": str(oid) if oid is not None else None,
                        "athlete_link": link,
                        "invalid_fields": fields,
                    }
                )
    linked_ids = {
        item["athlete_id"] for item in affected if item["athlete_link"] == "linked"
    }
    return {
        "scanned_results": scanned,
        "affected_results": len(affected),
        "reasons": dict(reasons),
        "linked_athletes": {name: links[ObjectId(name)] for name in sorted(linked_ids)},
        "results": affected,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    uri = os.getenv("AUDIT_MONGO_URL")
    if not uri:
        parser.error("Set AUDIT_MONGO_URL to a MongoDB connection with read access.")
    try:
        with MongoClient(
            uri, serverSelectionTimeoutMS=5000, appname="firesport-read-only-name-audit"
        ) as client:
            report = audit_result_names(client[args.database])
    except PyMongoError as exc:
        parser.exit(1, f"MongoDB audit failed ({type(exc).__name__}).\n")
    report["database"] = args.database
    report["generated_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
        stream.write("\n")
    print(
        f"{report['affected_results']} / {report['scanned_results']} výsledků vyžaduje ověření."
    )


if __name__ == "__main__":
    main()
