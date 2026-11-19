#!/usr/bin/env python3
"""Read-only category migration planning and explicit application of an approved snapshot."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import os
import re
from urllib.parse import urlsplit
from pathlib import Path

from bson import json_util
from pymongo import MongoClient, WriteConcern

from app.models.result import TimeAttempt
from app.category_catalog import BY_ID, CATEGORIES, CATEGORY_COLLECTION, supplemental_record_exclusion
from app.services.category_normalization import group_metadata, label_key, resolve_category, source_performance_issue
from app.services.data_import import DataImporter
from app.services.category_source_rules import team_member_source
from app.services.published_standings import HISTORICAL, TEAM_BY_LABEL, TEAM_MEMBER, historical_fields, team_entry_id
from scripts.category_identity_evidence import BirthYearEvidence

INPUT_COLLECTIONS = ("categories", "competitions", "athletes", "results")
READ_COLLECTIONS = (*INPUT_COLLECTIONS, CATEGORY_COLLECTION)
VERSION = 4


def fingerprint(value) -> str:
    return sha256(json_util.dumps(
        value, sort_keys=True, json_options=json_util.CANONICAL_JSON_OPTIONS
    ).encode()).hexdigest()


def load_snapshot(path: Path) -> dict:
    documents = {name: {} for name in READ_COLLECTIONS}
    counts = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            name, document = json_util.loads(line)
            if name == "count":
                if document["collection"] in counts:
                    raise ValueError("Duplicitní deklarace počtu ve snímku.")
                counts[document["collection"]] = document["count"]
            elif name in documents:
                if document["_id"] in documents[name]:
                    raise ValueError(f"Duplicitní _id v kolekci {name}.")
                documents[name][document["_id"]] = document
    for name in INPUT_COLLECTIONS:
        if counts.get(name) != len(documents[name]):
            raise ValueError(f"Neúplný snímek kolekce {name}.")
    if counts.get(CATEGORY_COLLECTION, 0) != len(documents[CATEGORY_COLLECTION]):
        raise ValueError("Neúplný kanonický katalog ve snímku.")
    return documents


def read_database(db) -> dict:
    existing = set(db.list_collection_names())
    return {
        name: {document["_id"]: document for document in db[name].find({}).sort("_id", 1)}
        if name in existing else {} for name in READ_COLLECTIONS
    }


def sorted_values(documents):
    return (documents[key] for key in sorted(documents, key=str))


def classify_legacy_result(
    result: dict, db: dict, births: BirthYearEvidence | None = None, individual_proof: dict | None = None,
) -> tuple[dict, bool]:
    legacy = db["categories"].get(result.get("category"))
    competition = db["competitions"].get(result.get("competition"))
    athlete_id = result.get("athlete")
    person = result.get("imported_athlete") or {}
    category_name = (legacy or {}).get("name") or ""
    source_discipline = (legacy or {}).get("discipline")
    explicit_discipline = result.get("discipline")
    resolution = resolve_category(category_name, source_discipline, competition or {}, person,
                                  team=result.get("imported_team") or result.get("team"))
    evidence = [resolution.evidence] if resolution.evidence else []
    if resolution.reason == "missing_verified_individual_or_birth_year" and births:
        if birth := births.for_result(result):
            inferred = resolve_category(
                category_name, source_discipline, competition or {},
                {**person, "birth_year": birth["birth_year"]},
                team=result.get("imported_team") or result.get("team"),
            )
            if inferred.category:
                resolution = inferred
                evidence = [birth, *([resolution.evidence] if resolution.evidence else [])]
    if individual_proof:
        if resolution.reason not in {"missing_verified_individual_or_birth_year", "unverified_team_or_progression"}:
            raise ValueError(f"Neočekávaný doklad individuálního řádku {result['_id']}.")
        verified = resolve_category(category_name, source_discipline, competition or {}, person,
                                    team=result.get("imported_team") or result.get("team"),
                                    verified_individual_row=True)
        evidence = [{"kind": "verified_individual_row", **individual_proof}]
        if verified.evidence:
            evidence.append(verified.evidence)
        resolution = verified
    reason = resolution.reason or source_performance_issue(result)
    if not legacy:
        reason = "missing_category_reference"
    elif not competition:
        reason = "missing_competition_reference"
    elif athlete_id is not None and athlete_id not in db["athletes"]:
        reason = "missing_athlete_reference"
    elif explicit_discipline and explicit_discipline != resolution.discipline:
        reason = "conflicting_result_discipline"
    elif resolution.category and resolution.category.type == "team" and athlete_id is not None:
        reason = "team_with_athlete_reference"
    category = resolution.category if reason is None else None
    source = group_metadata(category_name, source_discipline, legacy_id=result.get("category"),
                            affiliation=resolution.affiliation, source_url=(competition or {}).get("source_url"))
    updates = {
        "category": category.id if category else None,
        "discipline": resolution.discipline,
        "result_type": category.type if category else None,
        "classification_status": "active" if category else "unsupported" if resolution.unsupported else "review",
        "classification_reason": reason,
        "source_category": source,
    }
    if evidence:
        source["classification_evidence"] = evidence
    if "discipline" in result:
        source["legacy_result_discipline"] = explicit_discipline
    updates.update(historical_fields(resolution.discipline, reason, source))
    return updates, resolution.per_result


def duplicate_candidates(db: dict, decisions: dict) -> list[dict]:
    """Find identical official rows even when the old category references differ."""
    rows = defaultdict(list)
    for result in sorted_values(db["results"]):
        decision = decisions[result["_id"]]
        category = decision.get("category")
        discipline = decision.get("discipline")
        source = decision.get("source_category") or {}
        discipline = discipline or source.get("discipline")
        if not discipline:
            continue
        try:
            identity = DataImporter._row_identity(result)
        except (KeyError, TypeError, ValueError):
            continue
        if not all(identity["name"]) and not identity["team"]:
            continue
        if not (identity["fscode"] or identity["birth_year"] or identity["start_number"] or result.get("athlete")):
            continue
        if identity["final_time"] is None and identity["rank"] is None and not any(t[1] is not None for t in identity["times"]):
            continue
        for field in ("category", "source_group", "district", "discipline", "result_list_id"):
            identity.pop(field, None)
        key = (discipline, fingerprint(identity))
        rows[key].append((result["_id"], category, source.get("key"), result.get("result_list_id")))
    duplicates = []
    for items in rows.values():
        if len(items) < 2:
            continue
        candidate_ids = [item[0] for item in items]
        same_scope = len({item[1:] for item in items}) == 1
        block_ids = [item[3] for item in items]
        distinct_verified_lists = all(block_ids) and len(set(block_ids)) == len(items)
        duplicates.append({
            "result_ids": candidate_ids, "same_scope": same_scope,
            "distinct_verified_lists": distinct_verified_lists,
        })
    return duplicates


def verified_duplicate_pairs(duplicates, evidence: dict | None, db: dict) -> dict:
    """Require source evidence and exact snapshot rows for each pair to archive."""
    if evidence is None:
        return {}
    if evidence.get("version") != 1 or not isinstance(evidence.get("duplicates"), list):
        raise ValueError("Neplatný formát doložených duplicit.")
    candidates = {frozenset(cluster["result_ids"]) for cluster in duplicates if not cluster["distinct_verified_lists"]}
    seen = set()
    verified = {}
    for proof in evidence["duplicates"]:
        keep, copy = proof["keep"], proof["copy"]
        pair = frozenset({keep, copy})
        locator = urlsplit(proof.get("source_url", ""))
        digests = (proof.get("keep_sha256"), proof.get("copy_sha256"), proof.get("source_sha256"))
        if (
            keep == copy or pair not in candidates or pair & seen
            or locator.scheme != "https" or not locator.hostname
            or any(not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) for digest in digests)
            or type(proof.get("text_line")) is not int or proof["text_line"] < 1
            or type(proof.get("source_page")) is not int or proof["source_page"] < 1
        ):
            raise ValueError(f"Nedoložený nebo nesourodý pár duplicit {keep}/{copy}.")
        if db["results"][keep].get("result_list_id") != db["results"][copy].get("result_list_id"):
            raise ValueError(f"Rozdílné identifikátory výsledkových listin pro pár {keep}/{copy}.")
        if fingerprint(db["results"][keep]) != digests[0] or fingerprint(db["results"][copy]) != digests[1]:
            raise ValueError(f"Doklady duplicit neodpovídají snímku pro pár {keep}/{copy}.")
        seen.update(pair)
        verified[copy] = proof
    return verified


def verified_source(source):
    url = urlsplit(source["source_url"])
    if (url.scheme != "https" or url.hostname != "mladez.dh.cz"
            or not re.fullmatch(r"[0-9a-f]{64}", source["source_sha256"])):
        raise ValueError("Neplatný doklad týmové listiny.")
    return {"source_url": source["source_url"], "source_sha256": source["source_sha256"]}


def attach_team_standings(db, changes, evidence):
    if evidence is None:
        return {}
    if evidence.get("version") != 1 or not isinstance(evidence.get("team_lists"), list):
        raise ValueError("Neplatný soubor družstevních listin.")
    expected = defaultdict(set)
    for identifier, decision in changes.items():
        if decision.get("classification_reason") == "team_member_result_requires_separate_treatment":
            expected[db["results"][identifier]["competition"], decision["source_category"]["key"]].add(identifier)
    teams_by_event = defaultdict(list)
    for listing in evidence["team_lists"]:
        event, key = listing["competition"], listing["source_category_key"]
        category = TEAM_BY_LABEL.get(key)
        if category is None or not team_member_source(key, "100m", db["competitions"].get(event, {})):
            raise ValueError("Soubor družstev odkazuje na neověřenou soutěž nebo kategorii.")
        members = listing["members"]
        if {member["id"] for member in members} != expected.pop((event, key), None):
            raise ValueError("Družstevní listina nepokrývá schválené řádky.")
        if len({member["id"] for member in members}) != len(members):
            raise ValueError("Opakovaný řádek člena družstva.")
        total_source = verified_source(listing["totals_source"])
        member_source = verified_source(listing["members_source"])
        totals = {}
        for entry in listing["totals"]:
            number = entry["source_number"]
            if type(number) is not int or number <= 0 or number in totals:
                raise ValueError("Neplatné nebo opakované závodní číslo družstva.")
            valid = entry["total_status"] == "valid"
            if valid:
                value = entry["total_time"]
                if type(value) not in (int, float) or not 0 < value < float("inf") or not entry["name"]:
                    raise ValueError("Platný týmový součet nebo název chybí.")
            elif entry["total_time"] is not None or entry["total_status"] != "invalid":
                raise ValueError("Neplatný stav týmového součtu.")
            if type(entry["rank"]) is not int or entry["rank"] <= 0:
                raise ValueError("Neplatné oficiální pořadí družstva.")
            identity = team_entry_id(event, category.id, number)
            totals[number] = {**entry, **total_source, "_id": identity, "category": category.id}
        for member in members:
            identifier = member["id"]
            row = db["results"][identifier]
            team = totals.get(member["team_number"])
            if (fingerprint(row) != member["row_sha256"] or team is None or not team["name"]
                    or label_key(row.get("team")) != label_key(team["name"])):
                raise ValueError(f"Člen družstva {identifier} nesouhlasí s ověřenou listinou.")
            attempts = member["published_attempts"]
            if (type(member["source_page"]) is not int or member["source_page"] <= 0
                    or [attempt.get("attempt") for attempt in attempts] != [1, 2]):
                raise ValueError("Neplatná posloupnost publikovaných pokusů člena.")
            current = row.get("times") or []
            verified_attempts = [TimeAttempt.model_validate(attempt).model_dump(mode="json", exclude_none=True)
                                 for attempt in attempts]
            decision = changes[identifier]
            decision.update(
                category=category.id, result_type=TEAM_MEMBER, classification_status=TEAM_MEMBER,
                classification_reason=None, team_entry_id=team["_id"],
                member_evidence={**member_source, "source_page": member["source_page"]},
            )
            if published_name := member.get("published_name"):
                decision["published_name"] = published_name
            if [(a.get("time"), a.get("status")) for a in current] != [
                (a.get("time"), a["status"]) for a in verified_attempts
            ]:
                decision["published_attempts"] = [dict(attempt, time=attempt.get("time")) for attempt in verified_attempts]
        teams_by_event[event].extend(totals.values())
    if expected:
        raise ValueError("V souboru chybí doložené družstevní listiny pro část snímku.")
    return {
        event: {"team_results": sorted(teams, key=lambda t: (str(t["category"]), t["source_number"]))}
        for event, teams in teams_by_event.items()
    }


def validate_standings_references(results, competitions, catalog):
    teams = {}
    for event, competition in competitions.items():
        for team in competition.get("team_results") or []:
            category = BY_ID.get(team.get("category"))
            number = team.get("source_number")
            if (category is None or category.type != "team" or category.id not in catalog
                    or (number is None and not label_key(team.get("name")))
                    or team["_id"] in teams
                    or team["_id"] != team_entry_id(event, category.id, number, team.get("name"))):
                raise ValueError("Neplatný odkaz týmového výsledku.")
            teams[team["_id"]] = event, category.id
    for row in results.values():
        if row.get("classification_status") == TEAM_MEMBER:
            if teams.get(row.get("team_entry_id")) != (row.get("competition"), row.get("category")):
                raise ValueError(f"Výsledek {row['_id']} odkazuje na cizí nebo chybějící družstvo.")
        elif row.get("team_entry_id") is not None:
            raise ValueError(f"Neočekávaný odkaz na družstvo ve výsledku {row['_id']}.")


def verified_individual_rows(db, evidence):
    if evidence is None:
        return {}
    if evidence.get("version") != 1 or not isinstance(evidence.get("individual_rows"), list):
        raise ValueError("Neplatný soubor dokladů individuálních řádků.")
    verified = {}
    for proof in evidence["individual_rows"]:
        identifier = proof["id"]
        row = db["results"].get(identifier)
        competition = db["competitions"].get(row.get("competition")) if row else {}
        source = db["categories"].get(row.get("category")) if row else {}
        url = urlsplit(proof["source_url"])
        if (not row or identifier in verified or row.get("athlete")
                or "classification_status" in row or row.get("rank") is None or not row.get("start_number")
                or not competition or competition.get("source_url") != proof["source_url"]
                or url.scheme != "https" or url.hostname not in {"pozarnisporty.cz", "www.pozarnisporty.cz"}
                or not re.fullmatch(r"/races/[0-9]+/?", url.path)
                or not source or label_key(source.get("name")) != label_key(proof["source_category"])
                or not re.fullmatch(r"[0-9a-f]{64}", proof["source_sha256"])
                or fingerprint(row) != proof["row_sha256"]):
            raise ValueError(f"Doklad individuálního řádku nesouhlasí se snímkem {identifier}.")
        verified[identifier] = {key: proof[key] for key in ("source_url", "source_sha256", "source_category")}
    return verified


def build_plan(
    db: dict, evidence: dict | None = None, *, team_evidence: dict | None = None,
    individual_evidence: dict | None = None,
) -> tuple[dict, dict]:
    expected = {category.id: category.document() for category in CATEGORIES}
    for category_id, document in db[CATEGORY_COLLECTION].items():
        if expected.get(category_id) != document:
            raise ValueError(f"Konflikt kanonického dokumentu {category_id}.")

    decisions = {}
    individual_checks = set()
    changes = {}
    legacy_rows = defaultdict(list)
    reference_issues = []
    births = BirthYearEvidence(db)
    individual_proofs = verified_individual_rows(db, individual_evidence)
    for row in sorted_values(db["results"]):
        identifier = row["_id"]
        source = row.get("source_category") or {}
        legacy_id = source.get("legacy_category_id", row.get("category"))
        if legacy_id in db["categories"]:
            legacy_rows[legacy_id].append(row)
        for field, collection in (("category", "categories"), ("competition", "competitions"), ("athlete", "athletes")):
            ref = row.get(field)
            if ref is None and field == "athlete":
                continue
            if field == "category" and "classification_status" in row:
                if ref is None or ref in db[CATEGORY_COLLECTION]:
                    continue
            if ref not in db[collection]:
                reference_issues.append({"collection": "results", "id": identifier, "field": field, "reference": ref})

        if "classification_status" not in row:
            decisions[identifier], per_result = classify_legacy_result(row, db, births, individual_proofs.get(identifier))
            if per_result:
                individual_checks.add(identifier)
            changes[identifier] = decisions[identifier]
        else:
            validate_classification(row, db[CATEGORY_COLLECTION])
            decisions[identifier] = row

    team_updates = attach_team_standings(db, changes, team_evidence)
    candidates = duplicate_candidates(db, decisions)
    verified = verified_duplicate_pairs(candidates, evidence, db)
    for copy, proof in verified.items():
        if copy not in changes:
            raise ValueError(f"Výsledek {copy} je již klasifikován.")
        changes[copy].update(
            category=None, result_type=None, classification_status="duplicate",
            classification_reason="verified_duplicate_official_row",
            duplicate_of=proof["keep"], team_entry_id=None,
            duplicate_evidence={key: proof[key] for key in ("source_url", "source_sha256", "source_page", "text_line")},
        )

    confirmed = []
    duplicates = []
    for cluster in candidates:
        identifiers = cluster["result_ids"]
        archived = [identifier for identifier in identifiers if decisions[identifier]["classification_status"] == "duplicate"]
        if len(identifiers) == 2 and len(archived) == 1:
            copy = archived[0]
            keep = decisions[copy].get("duplicate_of")
            if keep in identifiers and keep != copy:
                confirmed.append({**cluster, "copy": copy, "keep": keep, "evidence": decisions[copy]["duplicate_evidence"]})
                continue
        duplicates.append(cluster)
        if cluster["distinct_verified_lists"]:
            continue
        for identifier in identifiers:
            if identifier in changes and changes[identifier]["classification_status"] in {"active", HISTORICAL, TEAM_MEMBER}:
                changes[identifier].update(
                    category=None, result_type=None, classification_status="review",
                    team_entry_id=None,
                    classification_reason="possible_duplicate_official_row",
                )
    for identifier, decision in decisions.items():
        if decision["classification_status"] == "duplicate":
            original = decisions.get(decision.get("duplicate_of"))
            if not original or identifier == decision.get("duplicate_of") or original["classification_status"] == "duplicate":
                raise ValueError(f"Neplatný odkaz archivované duplicity {identifier}.")

    team_rules = {
        member["id"]: verified_source(member["comparison_rules"])
        for listing in (team_evidence or {}).get("team_lists", [])
        for member in listing["members"] if "comparison_rules" in member
    }
    for identifier, decision in changes.items():
        status = decision["classification_status"]
        if status not in {HISTORICAL, TEAM_MEMBER}:
            continue
        row = db["results"][identifier]
        event = db["competitions"].get(row.get("competition"), {})
        if not births.record_identity(row) or source_performance_issue(row):
            continue
        if status == TEAM_MEMBER:
            url = decision["member_evidence"]["source_url"]
        else:
            url = event.get("source_url")
            source = urlsplit(url or "")
            if (source.scheme != "https" or source.hostname not in {
                "pozarnisport.hasicovo.cz", "pozarnisporty.cz", "www.pozarnisporty.cz",
            } or not re.fullmatch(r"/races/\d+/?", source.path)):
                continue
        proof = {"athlete": row["athlete"], "competition": row["competition"],
                 "time": row.get("final_time"), "source_url": url}
        if identifier in team_rules and status == TEAM_MEMBER:
            proof["rules_url"] = team_rules[identifier]["source_url"]
            proof["rules_sha256"] = team_rules[identifier]["source_sha256"]
        exclusion = supplemental_record_exclusion({**row, **decision, "record_evidence": proof})
        if exclusion is None or exclusion == "comparison_rules_unverified":
            decision["record_evidence"] = proof

    competition_targets = defaultdict(set)
    for row in db["results"].values():
        decision = decisions[row["_id"]]
        if decision["classification_status"] == "active":
            competition_targets[row.get("competition")].add(decision["category"])

    competition_changes = team_updates
    for competition in sorted_values(db["competitions"]):
        old = competition.get("categories")
        if old is None or "legacy_category_refs" in competition:
            continue
        if not isinstance(old, list):
            raise ValueError(f"Neplatný seznam kategorií soutěže {competition['_id']}.")
        for ref in old:
            if ref not in db["categories"] and ref not in db[CATEGORY_COLLECTION]:
                reference_issues.append({
                    "collection": "competitions", "id": competition["_id"], "field": "categories", "reference": ref,
                })
        targets = sorted(competition_targets[competition["_id"]])
        competition_changes.setdefault(competition["_id"], {}).update(categories=targets, legacy_category_refs=old)

    categories = []
    category_aliases = defaultdict(list)
    for legacy in sorted_values(db["categories"]):
        rows = legacy_rows[legacy["_id"]]
        outcomes = [decisions[row["_id"]] for row in rows]
        targets = Counter(BY_ID[item["category"]].key for item in outcomes if item["classification_status"] == "active")
        issues = Counter(item.get("classification_reason") for item in outcomes if item.get("classification_reason"))
        individual = sum(row["_id"] in individual_checks for row in rows)
        sample = resolve_category(legacy.get("name", ""), legacy.get("discipline"), {}, {})
        if sample.unsupported:
            status = "unsupported"
        elif individual or len(targets) > 1 or targets and issues:
            status = "per_result"
        elif (targets and not issues) or (not rows and sample.category):
            status = "automatic"
        else:
            status = "ambiguous"
        categories.append({
            "legacy_id": legacy["_id"], "name": legacy.get("name"), "discipline": legacy.get("discipline"),
            "status": status, "results": len(rows),
            "athletes": len({row["athlete"] for row in rows if row.get("athlete") is not None}),
            "targets": dict(targets), "empty_category_target": sample.category.key if not rows and sample.category else None,
            "individual_checks": individual, "problems": dict(issues),
        })
        category_aliases[(legacy.get("discipline"), label_key(legacy.get("name")))].append(legacy["_id"])

    planned_rows = {key: {**db["results"][key], **decision} for key, decision in decisions.items()}
    planned_events = {key: {**row, **competition_changes.get(key, {})} for key, row in db["competitions"].items()}
    for row in planned_rows.values():
        validate_classification(row, expected)
    validate_standings_references(planned_rows, planned_events, expected)
    active_status = Counter(decision["classification_status"] for decision in decisions.values())
    supplemental = [row for row in planned_rows.values() if row["classification_status"] in {HISTORICAL, TEAM_MEMBER}]

    record_audit = {
        status: dict(Counter(
            supplemental_record_exclusion(row) or "eligible"
            for row in supplemental if row["classification_status"] == status
        ))
        for status in (HISTORICAL, TEAM_MEMBER)
    }

    unsupported = Counter(
        (decision.get("source_category") or {}).get("discipline")
        for decision in decisions.values() if decision["classification_status"] == "unsupported"
    )
    pending = [
        {"id": identifier, "competition": db["results"][identifier].get("competition"),
         "source_category": decision.get("source_category"), "reason": decision.get("classification_reason"),
         "status": decision["classification_status"]}
        for identifier, decision in decisions.items() if decision["classification_status"] in {"review", "unsupported"}
    ]
    plan_hash = fingerprint({
        "version": VERSION, "catalog": list(expected.values()),
        "snapshot": {name: fingerprint(list(sorted_values(db[name]))) for name in READ_COLLECTIONS},
        "results": [{"id": key, "set": changes[key]} for key in changes],
        "competitions": [{"id": key, "set": competition_changes[key]} for key in competition_changes],
    })
    report = {
        "plan_sha256": plan_hash, "migration_version": VERSION, "personal_record_audit": record_audit,
        "counts": {
            "input_categories": len(db["categories"]), "expected_canonical_categories": len(CATEGORIES),
            "results_before": len(decisions), "results_after": len(decisions),
            "affected_competitions": len({db["results"][key].get("competition") for key in changes} - {None}),
            "affected_athletes": len({db["results"][key].get("athlete") for key in changes} - {None}),
            "update_results": len(changes), "update_competitions": len(competition_changes),
            "individual_checks": len(individual_checks),
            "automatically_convertible": sum(
                decision["classification_status"] == "active" and key not in individual_checks
                for key, decision in decisions.items()
            ),
            "active": active_status["active"], "review": active_status["review"],
            "unique_result_records": len(decisions) - active_status["duplicate"],
            "historical_60m": active_status[HISTORICAL], "team_member_runs": active_status[TEAM_MEMBER],
            "historical_unverified_final_times": sum(
                bool(source_performance_issue(row)) for row in supplemental if row["classification_status"] == HISTORICAL
            ),
            "team_standings": sum(len(event.get("team_results") or []) for event in planned_events.values()),
            "team_attempt_discrepancies": sum(bool(row.get("published_attempts")) for row in supplemental),
            "team_unrepresented_source_rows": sum(
                len(listing.get("unrepresented_source_rows", []))
                for listing in (team_evidence or {}).get("team_lists", [])
            ),
            "historical_age_ranges": dict(sorted(Counter(
                "–".join(map(str, row["historical_age_range"]))
                for row in supplemental if row["classification_status"] == HISTORICAL
            ).items())),
            "unsupported": active_status["unsupported"], "unsupported_by_discipline": dict(unsupported),
            "duplicate_clusters": len(duplicates),
            "confirmed_duplicate_clusters": len(confirmed),
            "archived_duplicate_results": active_status["duplicate"], "reference_issues": len(reference_issues),
        },
        "categories": categories,
        "canonical_catalog": list(expected.values()),
        "potential_duplicate_categories": [ids for ids in category_aliases.values() if len(ids) > 1],
        "potential_duplicate_results": duplicates,
        "confirmed_duplicate_results": confirmed,
        "classification_evidence": [
            {"id": identifier, "category": decision["category"], "sources": sources}
            for identifier, decision in decisions.items()
            if (sources := (decision.get("source_category") or {}).get("classification_evidence"))
            and decision["classification_status"] == "active"
        ],
        "reference_issues": reference_issues,
        "published_standings": {
            "unrepresented_team_source_rows": [
                {**entry, "competition": listing["competition"], "category": listing["source_category_key"],
                 "source": listing["members_source"]}
                for listing in (team_evidence or {}).get("team_lists", [])
                for entry in listing.get("unrepresented_source_rows", [])
            ],
            "team_members": [{"id": row["_id"], "team_entry_id": row["team_entry_id"],
                              "competition": row["competition"], "evidence": row["member_evidence"],
                              "published_attempts_differ": bool(row.get("published_attempts"))}
                             for row in supplemental if row["classification_status"] == TEAM_MEMBER],
            "historical_groups": [
                {"competition": competition, "category": category, "range": ages, "rows": count}
                for (competition, category, ages), count in Counter(
                    (row["competition"], row["source_category"]["name"], tuple(row["historical_age_range"]))
                    for row in supplemental if row["classification_status"] == HISTORICAL
                ).items()
            ],
        },
        "manual_review": pending,
    }
    return report, {"results": changes, "competitions": competition_changes}


def validate_classification(row, catalog):
    category = BY_ID.get(row.get("category"))
    status = row["classification_status"]
    if status != "duplicate" and row.get("duplicate_of") is not None:
        raise ValueError(f"Výsledek {row['_id']} současně odkazuje na duplicitní kopii.")
    if status == TEAM_MEMBER:
        if (not category or category.type != "team" or category.id not in catalog
                or row.get("discipline") != "100m" or row.get("result_type") != TEAM_MEMBER
                or row.get("team_entry_id") is None or not row.get("member_evidence")):
            raise ValueError(f"Neplatný odkaz běhu člena družstva {row['_id']}.")
    elif status == HISTORICAL:
        if (row.get("category") is not None or row.get("discipline") != "60m"
                or row.get("result_type") != "individual" or row.get("historical_age_range") not in ([6, 8], [8, 11])):
            raise ValueError(f"Neplatná historická věková skupina {row['_id']}.")
    elif status == "active":
        if (not category or category.id not in catalog or row.get("discipline") != category.discipline
                or row.get("result_type") != category.type):
            raise ValueError(f"Neplatný kanonický odkaz výsledku {row['_id']}.")
    elif status not in {"review", "unsupported", "duplicate"} or row.get("category") is not None:
        raise ValueError(f"Neplatný stav klasifikace výsledku {row['_id']}.")


def install_catalog(db):
    expected = [category.document() for category in CATEGORIES]
    validator = {"$or": [{"$and": [
        {"$jsonSchema": {
            "bsonType": "object", "required": list(document), "additionalProperties": False,
            "properties": {key: {} for key in document},
        }},
        document,
    ]} for document in expected]}
    if CATEGORY_COLLECTION not in db.list_collection_names():
        db.create_collection(CATEGORY_COLLECTION, validator=validator)
    else:
        db.command("collMod", CATEGORY_COLLECTION, validator=validator,
                   validationLevel="strict", validationAction="error")
    catalog = db[CATEGORY_COLLECTION]
    catalog.create_index("key", unique=True, name="unique_canonical_category_key")
    for document in expected:
        catalog.update_one({"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True)
    if {doc["_id"]: doc for doc in catalog.find({})} != {doc["_id"]: doc for doc in expected}:
        raise RuntimeError("Obsah kanonického katalogu nesouhlasí s definicí.")


def assert_compatible_snapshot(current, original, updates):
    expected_catalog = {category.id: category.document() for category in CATEGORIES}
    if any(expected_catalog.get(key) != doc for key, doc in current[CATEGORY_COLLECTION].items()):
        raise ValueError("Neočekávané dokumenty v kanonickém katalogu.")
    for name in INPUT_COLLECTIONS:
        if set(current[name]) != set(original[name]):
            raise ValueError(f"Kolekce {name} změnila množinu dokumentů.")
        for identifier, before in original[name].items():
            after = {**before, **updates.get(name, {}).get(identifier, {})}
            actual = current[name][identifier]
            if actual != before and actual != after:
                raise ValueError(f"Dokument {name}/{identifier} se od schváleného plánu změnil.")


def apply_plan(db, snapshot, updates):
    # Maintenance mode is required. The full read is a preflight, and each
    # atomic update additionally compares the complete old document.
    current = read_database(db)
    assert_compatible_snapshot(current, snapshot, updates)
    install_catalog(db)
    for name in ("competitions", "results"):
        for identifier, fields in updates[name].items():
            before = snapshot[name][identifier]
            if current[name][identifier] == {**before, **fields}:
                continue
            outcome = db[name].update_one(
                {"_id": identifier, "$expr": {"$eq": ["$$ROOT", {"$literal": current[name][identifier]}]}},
                {"$set": fields},
            )
            if outcome.matched_count != 1:
                raise RuntimeError(f"Současná změna v {name}/{identifier}.")
    final = read_database(db)
    assert_compatible_snapshot(final, snapshot, updates)
    for name, changes in updates.items():
        for identifier, fields in changes.items():
            if final[name][identifier] != {**snapshot[name][identifier], **fields}:
                raise RuntimeError(f"Nedokončená migrace {name}/{identifier}.")
    validate_standings_references(final["results"], final["competitions"], final[CATEGORY_COLLECTION])
    for row in final["results"].values():
        validate_classification(row, final[CATEGORY_COLLECTION])


def private_file(path: Path):
    return os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Výchozí režim bez DB zápisů.")
    mode.add_argument("--apply", action="store_true")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--snapshot", type=Path)
    inputs.add_argument("--live-read-only", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--individual-evidence", type=Path, help="Ověřené původní řádky jednotlivců.")
    parser.add_argument("--team-evidence", type=Path, help="Ověřené oficiální družstevní listiny.")
    parser.add_argument("--evidence", type=Path, help="Ověřené páry duplicit z tohoto snímku.")
    parser.add_argument("--save-snapshot", type=Path)
    parser.add_argument("--approve-plan")
    parser.add_argument("--database", default="firesport")
    args = parser.parse_args()
    if args.apply and (not args.snapshot or not args.approve_plan):
        parser.error("--apply vyžaduje --snapshot a --approve-plan.")
    if args.save_snapshot and not args.live_read_only:
        parser.error("--save-snapshot vyžaduje --live-read-only.")
    uri_name = "CATEGORY_MIGRATION_WRITE_URI" if args.apply else "CATEGORY_MIGRATION_READ_URI"
    uri = os.environ.get(uri_name)
    if (args.apply or args.live_read_only) and not uri:
        parser.error(f"Chybí {uri_name}.")

    if args.snapshot:
        snapshot = load_snapshot(args.snapshot)
    else:
        with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
            snapshot = read_database(client[args.database])
    if args.save_snapshot:
        with private_file(args.save_snapshot) as handle:
            for name, documents in snapshot.items():
                handle.write(json_util.dumps(["count", {"collection": name, "count": len(documents)}]) + "\n")
                for document in sorted_values(documents):
                    handle.write(json_util.dumps([name, document]) + "\n")
    evidence = json_util.loads(args.evidence.read_text(encoding="utf-8")) if args.evidence else None
    team_evidence = json_util.loads(args.team_evidence.read_text(encoding="utf-8")) if args.team_evidence else None
    individual_evidence = json_util.loads(args.individual_evidence.read_text(encoding="utf-8")) if args.individual_evidence else None
    report, updates = build_plan(snapshot, evidence, team_evidence=team_evidence, individual_evidence=individual_evidence)
    if args.report:
        with private_file(args.report) as handle:
            handle.write(json_util.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json_util.dumps({"plan_sha256": report["plan_sha256"], "counts": report["counts"]}, indent=2))
    if args.apply:
        if args.approve_plan != report["plan_sha256"]:
            parser.error("Otisk schváleného plánu neodpovídá snímku a pravidlům.")
        with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
            db = client.get_database(args.database, write_concern=WriteConcern(w="majority"))
            apply_plan(db, snapshot, updates)
        print("Migrace dokončena a ověřena.")


if __name__ == "__main__":
    main()
