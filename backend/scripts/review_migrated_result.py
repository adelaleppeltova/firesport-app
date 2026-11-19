"""Plan or explicitly apply a single reviewed category/identity correction."""
import argparse
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from bson import ObjectId, json_util
from pymongo import MongoClient

from app.category_catalog import CATEGORY_COLLECTION
from scripts.category_identity_evidence import BirthYearEvidence
from scripts.migrate_category_catalog import (
    classify_legacy_result, fingerprint, load_snapshot, read_database,
    validate_classification,
)


def proposal(db, identifier, proof):
    row = db["results"].get(identifier) or {}
    if row.get("classification_status") != "review" or row.get("duplicate_of") is not None:
        raise ValueError("Řádek musí čekat na individuální kontrolu.")
    source = {key: proof[key] for key in ("source_url", "source_sha256")}
    url = urlsplit(source["source_url"])
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or not re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"])):
        raise ValueError("Chybí platný odkaz a kontrolní otisk dokladu.")
    if proof.get("result_sha256") != fingerprint(row):
        raise ValueError("Podklad neodpovídá verzi kontrolovaného řádku.")
    legacy = (row.get("source_category") or {}).get("legacy_category_id")
    athlete = proof.get("athlete", row.get("athlete"))
    person = dict(row.get("imported_athlete") or {})
    if "birth_year" in proof:
        year = proof["birth_year"]
        if type(year) is not int or not 1900 <= year <= 2100:
            raise ValueError("Neplatný doložený ročník.")
        person["birth_year"] = year
    candidate = {**row, "category": legacy, "athlete": athlete, "imported_athlete": person}
    if athlete is None or not BirthYearEvidence(db).record_identity(candidate):
        raise ValueError("Vazba na profil musí být doložena unikátním FSCode a existujícím ověřeným párováním.")
    decision, _ = classify_legacy_result(candidate, db)
    if decision["classification_status"] != "active" or decision["result_type"] != "individual":
        raise ValueError("Doložené údaje neumožňují bezpečné kanonické zařazení.")
    for peer in db["results"].values():
        if (peer["_id"] == identifier or peer.get("competition") != row["competition"]
                or peer.get("classification_status") == "duplicate"):
            continue
        if ((athlete is not None and peer.get("athlete") == athlete)
                or (row.get("start_number") is not None
                    and str(row["start_number"]) == str(peer.get("start_number")))):
            raise ValueError("Soutěž obsahuje možný překryv s jiným řádkem.")
    decision.update(athlete=athlete, source_category=row["source_category"],
                    manual_category_review={**source, "birth_year": proof.get("birth_year"),
                                            "original_athlete": row.get("athlete")})
    validate_classification({**row, **decision}, db[CATEGORY_COLLECTION])
    return decision


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--result", required=True, type=ObjectId)
    parser.add_argument("--proof", required=True, type=Path)
    parser.add_argument("--database", default="firesport")
    parser.add_argument("--approve")
    args = parser.parse_args()
    db = load_snapshot(args.snapshot)
    proof = json_util.loads(args.proof.read_text())
    updates = proposal(db, args.result, proof)
    digest = fingerprint({"id": args.result, "proof": proof, "updates": updates})
    print(json_util.dumps({"approval_sha256": digest, "updates": updates}, ensure_ascii=False))
    if args.approve:
        if args.approve != digest:
            parser.error("Otisk neschválen.")
        with MongoClient(os.environ["CATEGORY_MIGRATION_WRITE_URI"]) as client:
            database = client[args.database]
            if proposal(read_database(database), args.result, proof) != updates:
                raise RuntimeError("Podklady se změnily.")
            row = db["results"][args.result]
            applied = database.results.update_one(
                {"_id": args.result, "$expr": {"$eq": ["$$ROOT", {"$literal": row}]}},
                {"$set": updates},
            )
            if applied.matched_count != 1:
                raise RuntimeError("Řádek se změnil.")


if __name__ == "__main__":
    main()
