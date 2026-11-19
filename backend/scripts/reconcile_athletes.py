"""Plan and replay athlete assignments against a complete MongoDB snapshot."""

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
import os
from pathlib import Path
import re
import unicodedata

from bson import ObjectId, json_util
from pymongo import MongoClient, UpdateOne, WriteConcern

from app.category_catalog import BY_ID
from app.person_names import normalize_person_name
from app.services.athlete_identity import normalize_fs_code, normalize_fs_codes, normalize_teams
from app.services.data_import import _import_id
from scripts.audit_reconciliation_sources import audit_sources
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file, read_database


def folded(value):
    return "".join(c for c in unicodedata.normalize("NFD", value.casefold())
                   if not unicodedata.combining(c))


def name_fields(doc):
    return tuple(normalize_person_name(doc.get(field)) for field in ("first_name", "last_name"))


def exact_name(doc):
    return tuple(value.casefold() for value in name_fields(doc))


def plausible_name(doc):
    return all(re.fullmatch(r"[^\W\d_]+(?:[ '\u2019\-\u2010\u2011][^\W\d_]+)*", n)
               and folded(n) not in {"neznamy", "neznama", "neznam", "neobsazeno", "neuvedeno", "null", "none"}
               for n in name_fields(doc))


def name_key(doc):
    return tuple(folded(value) for value in name_fields(doc))


def valid_code(value):
    return bool(value and re.fullmatch(r"[0-9]{4,}", value) and int(value))


def is_individual(row):
    category = BY_ID.get(row.get("category"))
    return (row.get("classification_status") == "active" and row.get("result_type") == "individual"
            and row.get("duplicate_of") is None and category is not None
            and category.type == "individual" and category.discipline == row.get("discipline"))


def source_identity(row):
    return row.get("imported_athlete") or {}


def code_of(doc):
    return normalize_fs_code(doc.get("fscode"))


def historical_codes(profile):
    return normalize_fs_codes(profile.get("fs_codes"), profile.get("fscode"))


def is_manual(row):
    return (row.get("match_reason") or "").startswith("manual_admin_")


def scope(row):
    category = row.get("source_category") or {}
    return (row.get("competition"), row.get("discipline"), category.get("key") or row.get("category"),
            row.get("result_list_id"))


def close_spelling(a, b):
    if a == b or min(len(a), len(b)) < 3:
        return False
    shorter, longer = sorted((a, b), key=len)
    if longer.startswith(shorter + " ") or longer.endswith(" " + shorter):
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        changes = [i for i, ch in enumerate(a) if ch != b[i]]
        return (len(changes) == 1 or len(changes) == 2 and changes[1] == changes[0] + 1
                and a[changes[0]] == b[changes[1]] and a[changes[1]] == b[changes[0]])
    shorter, longer = sorted((a, b), key=len)
    i = next((i for i, ch in enumerate(shorter) if ch != longer[i]), len(shorter))
    return shorter[i:] == longer[i + 1:]


def build_plan(snapshot):
    profiles = snapshot["athletes"]
    active = {i: p for i, p in profiles.items() if p.get("is_active") is not False}
    rows = snapshot["results"]
    named_profiles, code_profiles, aliases = defaultdict(set), defaultdict(set), defaultdict(set)
    source_names, source_codes, variants, occupied = (defaultdict(list) for _ in range(4))
    issues = []
    for i, profile in profiles.items():
        if i in active:
            named_profiles[name_key(profile)].add(i)
        elif (target := profile.get("merged_into_athlete_id")) and ObjectId.is_valid(target):
            if ObjectId(target) in active:
                aliases[name_key(profile)].add(ObjectId(target))
        for code in historical_codes(profile):
            if i in active:
                code_profiles[code].add(i)
        if not plausible_name(profile):
            issues.append({"reason": "profile_name_quality", "athlete_id": i})
    for code, ids in code_profiles.items():
        if len(ids) > 1:
            issues.append({"reason": "shared_profile_fscode", "fscode": code, "athlete_ids": sorted(ids)})

    for rid, row in rows.items():
        person = source_identity(row)
        key = name_key(person)
        aid = row.get("athlete")
        if aid is not None:
            if aid not in active:
                issues.append({"reason": "invalid_athlete_reference", "result_id": rid, "athlete_id": aid})
            elif all(key) and row.get("duplicate_of") is None:
                aliases[key].add(aid)
                profile = active[aid]
                year, known_year = person.get("birth_year"), profile.get("birth_year")
                code = code_of(person)
                if (key != name_key(profile) or year is not None and known_year not in (None, year)
                        or code and code_profiles[code] - {aid}):
                    issues.append({"reason": "linked_identity_discrepancy", "result_id": rid, "athlete_id": aid})
            if is_individual(row):
                occupied[aid, scope(row)].append(rid)
        if row.get("duplicate_of") is not None or row.get("result_type") == "team":
            continue
        if row.get("classification_status") not in {"active", "historical", "team_member"}:
            continue
        if all(key):
            source_names[key].append(rid)
        if code := code_of(person):
            source_codes[code].append(rid)

    for key in set(named_profiles) | set(aliases) | set(source_names):
        if all(key):
            variants[0, key[0]].append(key)
            variants[1, key[1]].append(key)

    linked_codes = {
        code: {rows[rid]["athlete"] for rid in ids if rows[rid].get("athlete") is not None}
        for code, ids in source_codes.items()
    }
    review, proposals, new_groups = {}, {}, defaultdict(list)
    proposed_codes = {}

    def leave(rid, reason, candidates=()):
        review[rid] = {"reason": reason, "athlete_ids": sorted(candidates)}

    def potential_variant(key, person, row, *, ignore_profile=None):
        swapped = key[1], key[0]
        if (aliases.get(swapped, set()) | named_profiles.get(swapped, set())) - {ignore_profile}:
            return True
        year = person.get("birth_year")
        team = folded(row.get("team") or "")
        if year is None and not team:
            return False
        for pos in (0, 1):
            for near in variants[pos, key[pos]]:
                if not close_spelling(near[1 - pos], key[1 - pos]):
                    continue
                for aid in (named_profiles[near] | aliases[near]) - {ignore_profile}:
                    other = active[aid]
                    other_year = other.get("birth_year")
                    if year is not None and other_year not in (None, year):
                        continue
                    if year is not None and year == other_year or team and team in {
                        folded(t) for t in normalize_teams(other.get("teams"), other.get("team"))
                    }:
                        return True
                for other_id in source_names[near]:
                    other = rows[other_id]
                    if ignore_profile is not None and other.get("athlete") == ignore_profile:
                        continue
                    other_year = source_identity(other).get("birth_year")
                    if year is not None and other_year not in (None, year):
                        continue
                    if year is not None and year == other_year or team and folded(other.get("team") or "") == team:
                        return True
        return False

    def propose_existing(rid, aid, reason):
        proposals[rid] = (aid, reason)

    for rid, row in rows.items():
        if not is_individual(row) or row.get("athlete") is not None:
            continue
        if is_manual(row):
            leave(rid, row["match_reason"])
            continue
        person = source_identity(row)
        key, year, code = name_key(person), person.get("birth_year"), code_of(person)
        peers = named_profiles[key] | aliases[key]
        owners = code_profiles[code] if code else set()
        if not all(key):
            leave(rid, "name_segmentation_review" if row.get("source_full_name") else "missing_name")
        elif not plausible_name(person):
            leave(rid, "name_quality_review", peers | owners)
        elif year is not None and (type(year) is not int or not 1900 <= year <= getattr(row.get("date"), "year", 0)):
            leave(rid, "conflicting_birth_year", peers | owners)
        elif code and (not valid_code(code) or len(owners) > 1):
            leave(rid, "shared_fscode" if len(owners) > 1 else "conflicting_fscode", peers | owners)
        elif code and any(
            (all(name_key(other)) and name_key(other) != key)
            or (year is not None and other.get("birth_year") not in (None, year))
            for other_id in source_codes[code]
            if (other := source_identity(rows[other_id]))
        ):
            leave(rid, "conflicting_fscode", peers | owners)
        elif owners:
            aid, = owners
            profile = active[aid]
            observed_years = {source_identity(rows[i]).get("birth_year") for i in source_codes[code]} - {None}
            if profile.get("birth_year") is not None:
                observed_years.add(profile["birth_year"])
            competing = {p for p in peers - owners if year is not None and active[p].get("birth_year") == year}
            if (linked_codes.get(code, set()) - owners
                    or exact_name(profile) != exact_name(person) or len(observed_years) > 1
                    or year is not None and observed_years - {year}
                    or profile.get("birth_year") is None and competing):
                leave(rid, "conflicting_fscode", peers | owners)
            else:
                propose_existing(rid, aid, "batch_name_plus_fscode")
        elif peers:
            compatible = {p for p in peers if year is None or active[p].get("birth_year") in (None, year)}
            if len(compatible) > 1:
                leave(rid, "multiple_name_candidates", compatible)
            elif len(compatible) == 1:
                aid, = compatible
                profile = active[aid]
                if exact_name(profile) == exact_name(person) and year is not None and year == profile.get("birth_year"):
                    if code and linked_codes.get(code, set()) - {aid}:
                        leave(rid, "conflicting_fscode", compatible)
                    elif potential_variant(key, person, row, ignore_profile=aid):
                        leave(rid, "possible_name_variant", compatible)
                    else:
                        propose_existing(rid, aid, "batch_name_plus_birth_year")
                        if code:
                            proposed_codes[rid] = code
                else:
                    leave(rid, "insufficient_identity", compatible)
            else:
                leave(rid, "conflicting_birth_year", peers)
        elif code and linked_codes.get(code):
            leave(rid, "conflicting_fscode")
        elif potential_variant(key, person, row):
            leave(rid, "possible_name_variant")
        else:
            new_groups[key].append(rid)

    planned_profiles = {}
    for key, ids in new_groups.items():
        source_ids = source_names[key]
        evidence = [source_identity(rows[i]) for i in source_ids]
        years = {p.get("birth_year") for p in evidence} - {None}
        codes = {code_of(p) for p in evidence} - {None}
        spellings = {exact_name(p) for p in evidence}
        genders = {BY_ID[rows[i]["category"]].gender for i in source_ids if is_individual(rows[i])}
        unsafe = (len(years) > 1 or len(spellings) > 1 or len(genders) > 1
                  or any(code_profiles[c] or linked_codes.get(c) for c in codes)
                  or any(is_manual(rows[i]) for i in source_ids))
        if unsafe:
            for rid in ids:
                leave(rid, "conflicting_source_identity")
            continue
        strong = [i for i in ids if source_identity(rows[i]).get("birth_year") or code_of(source_identity(rows[i]))]
        chosen = strong or (ids if len(source_ids) == 1 else [])
        for rid in set(ids) - set(chosen):
            leave(rid, "insufficient_identity")
        if not chosen:
            continue
        chosen_years = {source_identity(rows[i]).get("birth_year") for i in chosen} - {None}
        chosen_codes = {code_of(source_identity(rows[i])) for i in chosen} - {None}
        # Each additional code requires a row carrying the common birth year.
        year_backed_codes = {code_of(source_identity(rows[i])) for i in chosen
                             if source_identity(rows[i]).get("birth_year") is not None}
        if ((chosen_years and chosen_codes - year_backed_codes)
                or (not chosen_years and len(chosen_codes) > 1)):
            for rid in chosen:
                leave(rid, "conflicting_source_identity")
            continue
        if any(is_individual(rows[i]) and scope(rows[i]) == scope(rows[j])
               for i in chosen for j in source_ids if i != j):
            for rid in chosen:
                leave(rid, "same_result_list_conflict")
            continue
        birth_year = next(iter(chosen_years), None)
        codes_to_store = sorted(chosen_codes)
        # Preserve IDs for the previous single-code and no-code profile shapes.
        code_key = codes_to_store if len(codes_to_store) > 1 else next(iter(codes_to_store), None)
        identity = exact_name(source_identity(rows[min(chosen)]))
        aid = _import_id("athlete-reconciliation-v1", identity, birth_year, code_key)
        if aid in profiles or aid in planned_profiles:
            raise ValueError("Kolize ID nového profilu.")
        first, last = name_fields(source_identity(rows[min(chosen)]))
        planned_profiles[aid] = {
            "_id": aid, "first_name": first, "last_name": last, "birth_year": birth_year,
            "fs_codes": codes_to_store, "teams": normalize_teams([rows[i].get("team") for i in sorted(chosen)]),
            "is_active": True, "merged_into_athlete_id": None,
        }
        for rid in chosen:
            proposals[rid] = (aid, "batch_created_profile")

    proposed_scopes = Counter((aid, scope(rows[rid])) for rid, (aid, _) in proposals.items())
    creates, updates = {}, {}
    extra_codes = defaultdict(set)
    for rid, (aid, reason) in proposals.items():
        slot = aid, scope(rows[rid])
        if occupied[slot] or proposed_scopes[slot] > 1:
            leave(rid, "same_result_list_conflict", [aid] if aid in active else [])
            continue
        if aid in planned_profiles:
            creates[aid] = planned_profiles[aid]
        updates[rid] = {"athlete": aid, "match_status": "matched", "match_reason": reason}
        if rid in proposed_codes:
            extra_codes[aid].add(proposed_codes[rid])
    profile_updates = [
        {"_id": aid, "set": {"fs_codes": normalize_fs_codes(historical_codes(profiles[aid]), sorted(extra_codes[aid]))}}
        for aid in sorted(extra_codes)
    ]
    for rid, item in review.items():
        row = rows[rid]
        if not is_manual(row) and (row.get("match_status"), row.get("match_reason")) != ("needs_review", item["reason"]):
            updates[rid] = {"match_status": "needs_review", "match_reason": item["reason"]}

    queue = sum(is_individual(row) and row.get("match_status") in {"needs_review", "unmatched"} for row in rows.values())
    return {
        "creates": [creates[i] for i in sorted(creates)],
        "profile_updates": profile_updates,
        "updates": [{"_id": i, "set": updates[i]} for i in sorted(updates)],
        "review": [{"_id": i, **review[i]} for i in sorted(review)],
        "issues": sorted(issues, key=fingerprint),
        "counts": {
            "profiles_before": len(profiles), "results_before": len(rows),
            "admin_before": queue,
            "new_profiles": len(creates),
            "profiles_with_added_codes": len(profile_updates),
            "assignments": dict(Counter(u["match_reason"] for u in updates.values() if "athlete" in u)),
            "review_reasons": dict(Counter(r["reason"] for r in review.values())),
            "status_updates": sum("athlete" not in u for u in updates.values()),
        },
    }


def expected_state(snapshot, plan, timestamp):
    after = {**snapshot, "athletes": dict(snapshot["athletes"]), "results": dict(snapshot["results"])}
    for profile in plan["creates"]:
        after["athletes"][profile["_id"]] = {**profile, "created_at": timestamp}
    for update in plan.get("profile_updates", []):
        aid = update["_id"]
        after["athletes"][aid] = {**after["athletes"][aid], **update["set"], "updated_at": timestamp}
    for update in plan["updates"]:
        rid = update["_id"]
        after["results"][rid] = {**after["results"][rid], **update["set"], "updated_at": timestamp}
    return after


def apply_plan(database, before, plan, timestamp):
    after = expected_state(before, plan, timestamp)
    current = read_database(database)
    for name, documents in current.items():
        original, expected = before[name], after[name]
        if not set(original) <= set(documents) <= set(expected):
            raise ValueError(f"Změnil se rozsah kolekce {name}.")
        if any(doc != original.get(i) and doc != expected.get(i) for i, doc in documents.items()):
            raise ValueError(f"Změnil se obsah kolekce {name}.")
    concern = WriteConcern(w="majority", j=True)
    profiles = [document for identifier, document in after["athletes"].items()
                if identifier not in current["athletes"]]
    if profiles:
        database["athletes"].with_options(write_concern=concern).insert_many(profiles)
    for name, operations in (("athletes", plan.get("profile_updates", [])), ("results", plan["updates"])):
        collection = database[name].with_options(write_concern=concern)
        pending = []
        for op in operations:
            identifier = op["_id"]
            old = before[name][identifier]
            if current[name][identifier] == after[name][identifier]:
                continue
            guard = {key: {"$eq": value} for key, value in old.items()}
            for key in op["set"].keys() | {"updated_at"}:
                if key not in old:
                    guard[key] = {"$exists": False}
            pending.append(UpdateOne(guard, {"$set": {**op["set"], "updated_at": timestamp}}))
        for index in range(0, len(pending), 500):
            batch = pending[index:index + 500]
            if collection.bulk_write(batch).matched_count != len(batch):
                raise ValueError(f"Souběžná změna dokumentu v kolekci {name}.")
    if read_database(database) != after:
        raise ValueError("Kontrolní export neodpovídá plánu.")
    return after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", type=Path, help="Saved report with the reviewed plan")
    parser.add_argument("--approve-plan")
    parser.add_argument("--database", default="firesport")
    parser.add_argument("--source-root", type=Path, default=Path("../data"))
    args = parser.parse_args()
    snapshot = load_snapshot(args.snapshot)
    plan = build_plan(snapshot)
    sources = audit_sources(args.source_root, snapshot)
    digest = fingerprint({"snapshot": [list(docs.values()) for docs in snapshot.values()],
                          "plan": plan, "source_hashes": sources["hashes"]})
    if args.apply:
        if args.report or not args.approve_plan:
            parser.error("--apply requires --approve-plan and excludes --report")
        report = json_util.loads(args.apply.read_text(encoding="utf-8"))
        if args.approve_plan != digest or report["plan_sha256"] != digest:
            raise ValueError("Otisk schváleného plánu nesouhlasí.")
        uri = os.environ["FIRESPORT_RECONCILE_MONGO_URI"]
        with MongoClient(uri, serverSelectionTimeoutMS=5000, tz_aware=False) as client:
            after = apply_plan(client[args.database], snapshot, plan, report["write_timestamp"])
        after_plan = build_plan(after)
        after_counts = after_plan["counts"]
        print(json_util.dumps({"admin_after": after_counts["admin_before"], "next_run": after_counts}))
    else:
        if not args.report or args.approve_plan:
            parser.error("The dry run requires --report")
        with private_file(args.report) as stream:
            stream.write(json_util.dumps({
                "plan_sha256": digest, "write_timestamp": datetime.now(UTC).replace(tzinfo=None), **plan, "sources": sources,
            }, indent=2))
    print(json_util.dumps({"plan_sha256": digest, **plan["counts"], "sources": sources["counts"]}))


if __name__ == "__main__":
    main()
