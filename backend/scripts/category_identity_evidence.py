"""Corroborate historical birth years without linking people by name alone."""
from collections import defaultdict

from app.services.athlete_identity import normalize_fs_code, normalize_fs_codes
from app.services.result_matching import normalize_person_name

CODE_MATCH = {"name_plus_fscode", "auto_reassigned_name_plus_fscode"}
EXPLICIT_MATCH = {*CODE_MATCH, "manual_admin_assignment"}


def name(person: dict) -> tuple[str, str]:
    return tuple(normalize_person_name(person.get(field)).casefold() for field in ("first_name", "last_name"))


class BirthYearEvidence:
    def __init__(self, db: dict):
        self.profiles = db["athletes"]
        self.code_owners = defaultdict(set)
        self.linked_rows = defaultdict(list)
        self.code_rows = defaultdict(list)
        for profile_id, profile in self.profiles.items():
            if profile.get("is_active") is not False and not profile.get("merged_into_athlete_id"):
                for code in normalize_fs_codes(profile.get("fs_codes"), profile.get("fscode")):
                    self.code_owners[code].add(profile_id)
        for row in db["results"].values():
            person = row.get("imported_athlete") or {}
            if row.get("athlete") is not None:
                self.linked_rows[row["athlete"]].append(row)
            if code := normalize_fs_code(person.get("fscode")):
                self.code_rows[code].append(row)

    def record_identity(self, result: dict) -> bool:
        person = result.get("imported_athlete") or {}
        athlete = result.get("athlete")
        profile = self.profiles.get(athlete) or {}
        code = normalize_fs_code(person.get("fscode"))
        if (not code or not code.isascii() or not code.isdecimal() or len(code) < 4
                or self.code_owners[code] != {athlete}
                or result.get("match_status") != "matched" or result.get("match_reason") not in EXPLICIT_MATCH
                or not all(name(person)) or name(profile) != name(person)):
            return False
        years = {profile.get("birth_year"), person.get("birth_year")}
        for peer in self.code_rows[code]:
            imported = peer.get("imported_athlete") or {}
            if name(imported) != name(person) or peer.get("athlete") not in (None, athlete):
                return False
            years.add(imported.get("birth_year"))
        return len(years - {None}) <= 1

    def for_result(self, result: dict) -> dict | None:
        person = result.get("imported_athlete") or {}
        if (person.get("birth_year") is not None or not all(name(person))
                or result.get("match_status") != "matched"
                or result.get("match_reason") not in EXPLICIT_MATCH):
            return None
        profile_id = result.get("athlete")
        profile = self.profiles.get(profile_id) or {}
        if name(profile) != name(person):
            return None
        unique_codes = {
            code for code in normalize_fs_codes(profile.get("fs_codes"), profile.get("fscode"))
            if self.code_owners[code] == {profile_id} and code.isascii() and code.isdecimal() and len(code) >= 4
        }
        source_code = normalize_fs_code(person.get("fscode"))
        if (source_code and source_code not in unique_codes
                or result["match_reason"] in CODE_MATCH and not source_code
                or not unique_codes):
            return None

        known_years = {profile["birth_year"]} if type(profile.get("birth_year")) is int else set()
        corroborators = []
        for code in unique_codes:
            for row in self.code_rows[code]:
                peer = row.get("imported_athlete") or {}
                if name(peer) != name(person):
                    return None
                year = peer.get("birth_year")
                if type(year) is not int:
                    continue
                known_years.add(year)
                if (row.get("athlete") == profile_id and row.get("match_status") == "matched"
                        and row.get("match_reason") in CODE_MATCH and row.get("competition") != result.get("competition")):
                    corroborators.append(row["_id"])
        for row in self.linked_rows[profile_id]:
            peer = row.get("imported_athlete") or {}
            if type(peer.get("birth_year")) is int:
                known_years.add(peer["birth_year"])
        if len(known_years) != 1 or not corroborators:
            return None
        return {
            "kind": "corroborated_birth_year", "birth_year": next(iter(known_years)),
            "athlete_id": profile_id, "source_result_ids": sorted(set(corroborators), key=str),
        }
