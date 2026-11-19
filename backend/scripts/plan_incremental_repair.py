"""Plan the November 14 repair from private audit files and a read-only Mongo export."""

import argparse
import csv
import hashlib
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from bson import json_util

from app.services.data_import import DataImporter, _import_id

MCR = "data/2026/mcr/komplet.json"
CHOMUTOV_ARCHIVED = "data/results/a7bb4dd25257b4f5.json"
CHOMUTOV_PRIMARY = "data/2026/chomutov-stimax/komplet.json"
CHOMUTOV_URL = "https://pozarnisporty.cz/races/1034"
MCR_LISTS = {1: "mcr-2026-hzs-100m", 2: "mcr-2026-sdh-muzi-100m"}
METADATA = {
    "data/2018/moravsky-beroun/komplet.json": {
        "place": "Moravský Beroun", "date": None,
        "evidence": ["https://hasici.mbsporty.cz/novinky/1857",
                     "https://www.dolnistudenky.cz/pool/obec/files/zpravodaj_ds_09-2018_-_verze_4.pdf"],
        "note": "Obecní zpráva uvádí polovinu srpna, v rozporu s 2018-07 ve vstupu; přesný den nedoložen.",
    },
    "data/2026/bludov/komplet.json": {
        "place": "Bludov", "date": "2026-07-25", "discipline": "100m",
        "evidence": ["https://stovky.cz/bludov/bludov.htm",
                     "https://sport.dh.cz/images/Dokumenty/sport/pozarni-sport/CP/2026/Pravidla_CP_2026.pdf"],
    },
    "data/2026/jablonec/komplet-dorost.json": {
        "place": "Sportovní atletická hala Střelnice, Jablonec nad Nisou",
        "date": "2026-03-28", "discipline": "100m",
        "evidence": ["https://mladez.dh.cz/index.php/sportovni-cinnost/poharove-souteze-a-memorialy/1580-jablonecka-hala-dorostu-2026-vysledky-souteze"],
    },
    "data/2026/moravsky-beroun/komplet.json": {
        "place": "Hasičské cvičiště Mlékárna, Moravský Beroun", "date": "2026-07-05",
        "discipline": "100m",
        "evidence": ["https://hasici.mbsporty.cz/novinky", "https://kshmsk.cz/category/souteze/dorost/moravskoslezsky_pohar_dorostu/"],
    },
}
CUP_EVIDENCE = "https://sport.dh.cz/index.php/pozarni-sport/cesky-pohar-100-m/788-cesky-pohar-2025-pravidla"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def fingerprint(document):
    return digest_bytes(json_util.dumps(document, sort_keys=True).encode())


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=";"))


def key(record):
    return record["soubor"], int(record["index_kategorie_1"]), int(record["index_řádku_1"])


def load_snapshot(path):
    collections = defaultdict(dict)
    with path.open() as handle:
        for line in handle:
            name, doc = json_util.loads(line)
            identifier = doc.get("_id", doc.get("collection"))
            require(identifier not in collections[name], "Duplicitní záznam ve snímku")
            collections[name][identifier] = doc
    counts = {name: item["count"] for name, item in collections["count"].items()}
    for name in ("results", "competitions", "categories", "athletes"):
        require(counts.get(name) == len(collections[name]), f"Neúplný snímek {name}")
    return collections, counts


def build_plan(root, audit, snapshot_path):
    importer = DataImporter()
    db, counts = load_snapshot(snapshot_path)
    scopes = defaultdict(list)
    for doc in db["results"].values():
        scopes[str(doc["competition"]), str(doc["category"])].append(doc)
    by_id = {str(identifier): doc for identifier, doc in db["results"].items()}

    files = {}
    source_urls = {}
    source_hashes = {}
    for item in read_csv(audit / "soubory.csv"):
        name = item["soubor"]
        raw = (root / name).read_bytes()
        require(digest_bytes(raw) == item["sha256"], f"Vstup se změnil: {name}")
        source_hashes[name] = item["sha256"]
        if int(item["zdrojové_řádky"]):
            payload = json.loads(raw)
            files[name] = payload["competition"]
            source_urls[name] = payload.get("source_file")
    conflict_rows = {key(r): r for r in read_csv(audit / "konflikty.csv")}
    other_rows = {key(r): r for r in read_csv(audit / "ostatni-problematicke-radky.csv")}
    ledger = {}
    with (audit / "audit-ledger.ndjson").open() as handle:
        for line in handle:
            item = json.loads(line)
            locator = item["soubor"], item["kategorie"], item["radek"]
            require(locator not in ledger, "Duplicitní řádek v auditním přehledu")
            ledger[locator] = item
    actual_keys = {
        (path, ci, ri) for path, race in files.items()
        for ci, category in enumerate(race["categories"], 1)
        for ri in range(1, len(category["results"]) + 1)
    }
    require(set(ledger) == actual_keys and len(ledger) == 27248, "Nesouhlasí zdrojové řádky")
    require(len(conflict_rows) == 514 and all(ledger[k]["stav"] == "conflict" for k in conflict_rows),
            "Nesouhlasí historické konflikty")

    def source(locator):
        path, ci, ri = locator
        return files[path]["categories"][ci - 1]["results"][ri - 1]

    def scope_of(doc):
        return str(doc["competition"]), str(doc["category"])

    def assess(locator, original_candidates):
        comp, cat = scope_of(original_candidates[0])
        block = MCR_LISTS.get(locator[1]) if locator[0] == MCR else None
        row = importer.build_result_row(source(locator), cat, comp, block_id=block)
        decision, ids = importer.assess_result(row, scopes[comp, cat])
        return row, decision, ids

    inserted_origins = {
        item["ids"][0]: locator for locator, item in ledger.items() if item["stav"] == "inserted"
    }

    def same_chomutov_source(locator, original, row):
        # This cross-file evidence confirms a performance only. It supplies no athlete link.
        origin = inserted_origins.get(str(original["_id"]))
        if locator[0] != CHOMUTOV_ARCHIVED or not origin or origin[0] != CHOMUTOV_PRIMARY:
            return False
        if {source_urls[path] for path in (origin[0], locator[0])} != {CHOMUTOV_URL}:
            return False
        current = importer._row_identity(row)
        previous = importer._row_identity(original)
        if (any(current["name"]) or not all(previous["name"]) or current["start_number"] is None
                or current["rank"] is None or current["final_time"] is None):
            return False
        if any(current[field] != previous[field] for field in current if field not in ("name", "birth_year")):
            return False
        scope = scopes[scope_of(original)]
        return sum(importer._parse_start_number(doc.get("start_number")) == row["start_number"]
                   for doc in scope) == 1

    # Match every stored MČR men's row to its exact audited source coordinate.
    # The overlay models a separately approved metadata patch, never a database write.
    updates = []
    mcr_scope = None
    for locator, item in ledger.items():
        if locator[0] != MCR or locator[1] not in MCR_LISTS or item["stav"] != "inserted":
            continue
        original, = (by_id[identifier] for identifier in item["ids"])
        scope = scope_of(original)
        require(mcr_scope in (None, scope), "MČR scope changed")
        mcr_scope = scope
        expected = importer.build_result_row(source(locator), scope[1], scope[0])
        block = MCR_LISTS[locator[1]]
        current_block = original.get("result_list_id")
        require(current_block in (None, block), "MČR list assignment changed")
        require(importer._row_identity(expected) ==
                importer._row_identity({**original, "result_list_id": None}),
                f"MČR existing result changed: {original['_id']}")
        if current_block is None:
            updates.append({"collection": "results", "_id": original["_id"],
                            "expected_sha256": fingerprint(original), "source": locator,
                            "set": {"result_list_id": block},
                            "reason": "Doložená příslušnost k samostatné mužské listině HZS nebo SDH."})
    require(mcr_scope is not None, "Chybí rozsah MČR")
    overlay = {patch["_id"]: patch["set"] for patch in updates}
    require(sum(1 for k, v in ledger.items() if k[0] == MCR and k[1] in MCR_LISTS
                and v["stav"] == "inserted") == 151, "Neúplná mapa listin MČR")
    scopes[mcr_scope] = [{**doc, **overlay.get(doc["_id"], {})} for doc in scopes[mcr_scope]]

    inserts = []
    decisions = []
    uncertainty = Counter()
    district_audit = []
    category_audit = read_csv(audit / "kategorie.csv")
    require(len(category_audit) == 22, "Neúplný audit kategorií")
    for category in category_audit:
        category.update(verified_discipline="100m", official_evidence=CUP_EVIDENCE)
    for locator, item in ledger.items():
        path, ci, _ = locator
        original_action = item["stav"]
        historical_ids = item["ids"]
        record = {"source": locator, "original_action": original_action,
                  "historical_ids": historical_ids, "decision": "unchanged"}
        problem = conflict_rows.get(locator) or other_rows.get(locator)
        verdict = problem["verdikt"] if problem else None
        if problem:
            record["audit_reason"] = problem["důvod"]
        if original_action == "metadata":
            record["decision"] = "metadata_verified_separate_batch" if METADATA[path]["date"] else "metadata_review"
        elif original_action == "kategorie":
            confirmed, = json.loads(problem["přesné_shody_klíče"])
            require(confirmed in by_id, "Chybí existující výsledek kategorie")
            record.update(discipline="100m", matched_ids=[confirmed])
        elif original_action in ("inserted", "skipped"):
            require(all(identifier in by_id for identifier in historical_ids),
                    f"Zmizel historický dokument: {locator}")

        was_uncertain = verdict == "nejednoznačné" and original_action in ("conflict", "skipped")
        if original_action == "conflict" or was_uncertain:
            candidates = [by_id[identifier] for identifier in historical_ids]
            require(bool(candidates), f"Chybí kandidáti pro {locator}")
            row, decision, candidate_ids = assess(locator, candidates)
            record.update(rule_decision=decision, matched_ids=candidate_ids)
            if original_action == "conflict" and verdict == "chybná kolize":
                identifier = _import_id("result", importer._row_identity(row))
                if decision == "duplicate" and candidate_ids == [identifier]:
                    record.update(decision="already_applied", result_id=identifier)
                else:
                    require(decision == "insert" and identifier not in db["results"],
                            f"Plánovaná změna už není bezpečná: {locator}")
                    parent = db["competitions"][row["competition"]]
                    document = {"_id": identifier, **row, "date": parent["date"],
                                "match_status": "needs_review",
                                "match_reason": "repair_verified_result_unverified_athlete",
                                "quality_flag": "ok"}
                    inserts.append({"collection": "results", "document": document, "source": locator,
                                    "reason": problem["důvod"],
                                    "scope_snapshot_sha256": fingerprint(
                                        sorted(scopes[scope_of(row)], key=lambda doc: doc["_id"]))})
                    record.update(decision="insert", result_id=identifier)
            elif was_uncertain:
                if decision == "duplicate":
                    record["decision"] = "duplicate_confirmed"
                elif len(candidates) == 1 and same_chomutov_source(locator, candidates[0], row):
                    record.update(decision="duplicate_confirmed", evidence=CHOMUTOV_URL)
                else:
                    # A heuristic's 'insert' alone does not verify provenance or absence.
                    record["decision"] = "human_review"
                uncertainty[record["decision"]] += 1
            else:
                require(decision == "duplicate", f"V minulém konfliktu už není jediná shoda: {locator}")
                record["decision"] = "existing_performance"

        if (original_action == "skipped" and verdict == "chybná kolize") or (
                original_action == "kategorie" and verdict == "výkon uložen, rozdíl doplňujících polí"):
            identifier = (record.get("matched_ids") or historical_ids)[0]
            doc = by_id[identifier]
            district = source(locator).get("district")
            require(isinstance(district, str) and district.strip(), f"Chybí zdrojový okres: {locator}")
            record.update(decision="district_separate_review", district_result_id=doc["_id"])
            district_audit.append({"source": locator, "_id": doc["_id"], "source_district": district,
                                   "stored_district": doc.get("district"),
                                   "source_file": json.loads((root / path).read_bytes()).get("source_file")})
        decisions.append(record)

    require(len(inserts) == len({item["document"]["_id"] for item in inserts}), "Kolize ID plánovaných výsledků")
    require(len(inserts) + sum(r["decision"] == "already_applied" for r in decisions) == 94,
            "Neúplný plán pro 94 konfliktů")
    require(len(district_audit) == 1972 and sum(uncertainty.values()) == 453, "Neúplné prověření")
    require(Counter(x["original_action"] for x in decisions) ==
            {"inserted": 12166, "skipped": 12794, "conflict": 514, "kategorie": 662, "metadata": 1112},
            "Neodpovídají součty původního běhu")

    # Replay all planned inserts against a private in-memory overlay; repeat must find the same result.
    for item in inserts:
        doc = item["document"]
        scopes[scope_of(doc)].append(doc)
    for item in inserts:
        doc = item["document"]
        require(importer.assess_result(doc, scopes[scope_of(doc)]) == ("duplicate", [doc["_id"]]),
                f"Opakování plánu není jednoznačné: {item['source']}")

    metadata_evidence = {
        path: {**evidence, "same_date_competition_ids": [
            doc["_id"] for doc in db["competitions"].values()
            if str(doc["date"].date()) == evidence["date"]
        ] if evidence["date"] else []}
        for path, evidence in METADATA.items()
    }
    return {
        "format": 1, "dry_run": True, "source_sha256": source_hashes,
        "snapshot_sha256": digest_bytes(snapshot_path.read_bytes()),
        "insert_created_at": "UTC execution time, supplied only by a future executor",
        "existing_document_changes": updates, "inserts": inserts,
        "collections_before": counts, "collections_after": {**counts, "results": counts["results"] + len(inserts)},
        "decision_counts": dict(Counter(r["decision"] for r in decisions)),
        "uncertain_453": dict(uncertainty), "rows": decisions, "districts": district_audit,
        "metadata_evidence": metadata_evidence, "category_evidence": category_audit,
        "mcr_block_evidence": {
            "HZS": "https://cz.startovky.eu/vysledky/mistrovstvi-cr-v-pozarnim-sportu-hzs/stovka",
            "SDH": "https://cz.startovky.eu/vysledky/mistrovstvi-cr-v-pozarnim-sportu-muzi-sdh/stovka",
        },
    }


def _private_output(path, flags):
    return os.open(path, flags, 0o600)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = build_plan(args.root, args.audit, args.snapshot)
    with open(args.output, "x", encoding="utf-8", opener=_private_output) as handle:
        handle.write(json_util.dumps(plan, ensure_ascii=False, json_options=json_util.RELAXED_JSON_OPTIONS) + "\n")
    print(json.dumps({key: plan[key] for key in ("decision_counts", "collections_before", "collections_after")}, indent=2))


if __name__ == "__main__":
    main()
