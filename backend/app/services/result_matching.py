from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.db.database import db
from app.models.result import MatchStatus
from app.services.athlete_identity import (
    active_athlete_query,
    build_fs_code_query,
    is_valid_fs_code,
    normalize_athlete_document,
    normalize_fs_code,
)
from app.services.external_identity import ExternalIdentity, external_identities
from app.services.search_utils import build_diacritic_fuzzy_regex

athletes_collection = db["athletes"]
CANDIDATE_LIMIT = 50


def normalize_person_name(value: str | None) -> str:
    return " ".join(unicodedata.normalize("NFC", value or "").split())


def name_key(value: str | None) -> str:
    return normalize_person_name(value).casefold()


def build_name_candidate_query(value: str) -> dict:
    unaccented = "".join(
        char for char in unicodedata.normalize("NFD", value)
        if not unicodedata.combining(char)
    )
    pattern = r"\s*".join(build_diacritic_fuzzy_regex(char) for char in unaccented if char != " ")
    return {"$regex": rf"^\s*{pattern}\s*$", "$options": "i"}


@dataclass(frozen=True)
class IdentityObservation:
    first_name: str | None
    last_name: str | None
    birth_year: int | None
    fscode: str | None
    team: str | None = None
    external_identity: ExternalIdentity | None = None

    @property
    def name(self) -> tuple[str, str]:
        return name_key(self.first_name), name_key(self.last_name)


@dataclass
class CandidateSet:
    profiles: list[dict]
    external_owner: object | None = None
    truncated: bool = False


async def find_candidates(observation: IdentityObservation, *, include_variants: bool) -> CandidateSet:
    """Retrieve direct candidates. Truncated results cannot establish uniqueness."""
    first, last = observation.name
    code_query = build_fs_code_query(observation.fscode)
    query = [code_query] if code_query else []
    first_query = {"first_name": build_name_candidate_query(first)} if first else {}
    last_query = {"last_name": build_name_candidate_query(last)} if last else {}
    if first_query and last_query:
        query.append({**first_query, **last_query})

    owner = None
    if observation.external_identity:
        mapping = await external_identities.find_one({"_id": observation.external_identity.key})
        if mapping:
            owner = mapping["athlete_id"]
            query.append({"_id": owner})

    if not query:
        return CandidateSet([], owner)

    async def fetch(filters: list[dict]) -> list[dict]:
        cursor = athletes_collection.find(active_athlete_query({"$or": filters}))
        return await cursor.sort("_id", 1).limit(CANDIDATE_LIMIT + 1).to_list(CANDIDATE_LIMIT + 1)

    direct = await fetch(query)
    if len(direct) > CANDIDATE_LIMIT:
        return CandidateSet(direct[:CANDIDATE_LIMIT], owner, True)

    if include_variants or not direct:
        support = []
        if observation.birth_year is not None:
            support.append({"birth_year": observation.birth_year})
        if observation.team:
            support.append({"teams": {"$regex": rf"^{re.escape(observation.team)}$", "$options": "i"}})
        if first_query and last_query and support:
            variants = await fetch([
                {"$and": [
                    {"$or": [first_query, last_query]},
                    {"$or": support},
                    {"_id": {"$nin": [doc["_id"] for doc in direct]}},
                ]}
            ])
            direct.extend(doc for doc in variants if _name_variant(observation, doc))
    return CandidateSet(direct, owner)


def _name_variant(observation: IdentityObservation, profile: dict) -> bool:
    first, last = observation.name
    candidate_first, candidate_last = name_key(profile.get("first_name")), name_key(profile.get("last_name"))
    return bool(first and last and (
        (first == candidate_first and SequenceMatcher(None, last, candidate_last).ratio() >= 0.7)
        or (last == candidate_last and SequenceMatcher(None, first, candidate_first).ratio() >= 0.7)
    ))


def compare_candidate(observation: IdentityObservation, raw_profile: dict, external_owner=None) -> dict:
    profile = normalize_athlete_document(raw_profile)
    first, last = observation.name
    candidate_name = name_key(profile.get("first_name")), name_key(profile.get("last_name"))
    exact = bool(first and last and (first, last) == candidate_name)
    strong, supporting, conflicts = [], [], []
    if exact:
        supporting.append("exact_name")
    elif any(left and right and left != right for left, right in zip((first, last), candidate_name)):
        if _name_variant(observation, profile):
            supporting.append("name_variant")
        conflicts.append("different_name")

    year = profile.get("birth_year")
    if year is not None and observation.birth_year is not None:
        if year == observation.birth_year:
            supporting.append("birth_year")
        else:
            conflicts.append("birth_year")

    code = normalize_fs_code(observation.fscode)
    if code and is_valid_fs_code(code) and profile["fs_codes"]:
        if code in profile["fs_codes"]:
            strong.append("fscode")
        else:
            conflicts.append("fscode")
    if external_owner is not None:
        if external_owner == profile["_id"]:
            strong.append("verified_external_id")
        else:
            conflicts.append("verified_external_id")

    if observation.team and name_key(observation.team) in {name_key(team) for team in profile["teams"]}:
        supporting.append("historical_team")
    return {"profile": profile, "strong": strong, "supporting": supporting, "conflicts": conflicts}


def evaluate_candidates(observation: IdentityObservation, candidates: CandidateSet) -> dict:
    evidence = [compare_candidate(observation, profile, candidates.external_owner) for profile in candidates.profiles]
    evidence.sort(key=lambda item: (
        not bool(item["strong"]), bool(item["conflicts"]), -len(item["strong"]),
        "exact_name" not in item["supporting"], -len(item["supporting"]),
        str(item["profile"]["_id"]),
    ))

    def decision(reason: str, winner: dict | None = None, *, review: bool = True) -> dict:
        status = MatchStatus.matched if winner else MatchStatus.needs_review if review else MatchStatus.unmatched
        return {
            "match_status": status, "match_reason": reason,
            "matched_athlete": winner["profile"] if winner else None, "candidates": evidence,
        }

    if candidates.truncated:
        return decision("candidate_limit")
    code = normalize_fs_code(observation.fscode)
    if code and not is_valid_fs_code(code):
        return decision("invalid_fscode")
    code_matches = [item for item in evidence if "fscode" in item["strong"]]
    if len(code_matches) > 1:
        return decision("shared_fscode")
    if observation.external_identity and candidates.external_owner is None:
        return decision("unverified_external_id")
    identifier_matches = [item for item in evidence if item["strong"]]
    if identifier_matches:
        if len(identifier_matches) != 1:
            return decision("conflicting_identifiers")
        winner = identifier_matches[0]
        if winner["conflicts"]:
            return decision("conflicting_identifiers" if observation.external_identity else "conflicting_fscode")
        exact_name = "exact_name" in winner["supporting"]
        verified_id = "verified_external_id" in winner["strong"]
        if not exact_name and not (verified_id and "birth_year" in winner["supporting"]):
            return decision("insufficient_identity")
        if observation.birth_year is not None and winner["profile"].get("birth_year") is None and any(
            other is not winner and "exact_name" in other["supporting"] and "birth_year" in other["supporting"]
            for other in evidence
        ):
            return decision("conflicting_identifiers" if verified_id else "conflicting_fscode")
        return decision("verified_external_id" if verified_id else "name_plus_fscode", winner)
    if candidates.external_owner is not None:
        return decision("inactive_external_identity")
    if not all(observation.name):
        return decision("missing_name", review=bool(evidence))

    # Without a strong identifier, use known conflicts to explain the review decision.
    exact = [item for item in evidence if "exact_name" in item["supporting"]]
    compatible = [item for item in exact if "birth_year" not in item["conflicts"]]
    if len(compatible) > 1:
        return decision("multiple_name_candidates")
    if compatible:
        if observation.fscode:
            return decision("unrecognized_fscode")
        return decision("insufficient_identity")
    if exact:
        return decision("conflicting_birth_year")
    if evidence:
        return decision("possible_name_variant")
    return decision("no_match", review=False)


async def decide_athlete_match(
    *, first_name: str, last_name: str, birth_year: int | None, fscode: str | None,
    team: str | None = None, external_identity: ExternalIdentity | None = None,
    include_variants: bool = False,
) -> dict:
    observation = IdentityObservation(first_name, last_name, birth_year, fscode, team, external_identity)
    candidates = await find_candidates(observation, include_variants=include_variants)
    return evaluate_candidates(observation, candidates)
