"""Resolve source labels without rewriting their historical competition group."""
import re
from dataclasses import dataclass, replace
from datetime import date

from app.category_catalog import CATEGORIES, DISCIPLINES, FINAL_TIME_SENTINELS, Category, Discipline
from app.extraction.metadata import norm
from app.services.category_source_rules import organizer_label, team_member_source

def label_key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm(value)).strip()


DISCIPLINE_KEYS = {label_key(value): key for key, value in DISCIPLINES.items()}
AGE_RANGE = r"\b(\d{1,3})\s*(?:[-–—−]|a\b|do\b)\s*(\d{1,3})\b"
CANONICAL_NAME = {(c.discipline, label_key(c.name)): c for c in CATEGORIES}
PROGRESSION = re.compile(r"\bmcr\b|\bmistrovstvi ceske republiky\b|\b(?:krajske|okresni|okrskove) kolo\b")


def source_discipline(value: str | None) -> Discipline | None:
    key = label_key(value)
    compact = key.replace(" ", "")
    if compact in DISCIPLINES:
        return compact
    if key in DISCIPLINE_KEYS:
        return DISCIPLINE_KEYS[key]
    match = re.fullmatch(r"(?:beh na )?(60|100) ?m (?:s prekazkami|prekazek)", key)
    return f"{match[1]}m" if match else None


def source_age(name: str) -> tuple[int, int] | None:
    matches = {(int(a), int(b)) for a, b in re.findall(AGE_RANGE, norm(name))}
    return next(iter(matches)) if len(matches) == 1 else None


def competition_age(when, birth_year) -> int | None:
    if isinstance(when, str):
        try:
            when = date.fromisoformat(when)
        except ValueError:
            return None
    if not isinstance(when, date) or type(birth_year) is not int:
        return None
    return when.year - birth_year if 0 <= when.year - birth_year <= 100 else None


def group_metadata(name, discipline, *, legacy_id=None, affiliation=None, source_url=None) -> dict:
    bounds = source_age(name)
    return {
        "name": name, "key": label_key(name), "discipline": discipline,
        "min_age": bounds[0] if bounds else None, "max_age": bounds[1] if bounds else None,
        "legacy_category_id": legacy_id, "affiliation": affiliation, "source_url": source_url,
    }


@dataclass(frozen=True)
class Resolution:
    discipline: Discipline | None
    category: Category | None = None
    reason: str | None = None
    per_result: bool = False
    unsupported: bool = False
    affiliation: str | None = None
    evidence: dict | None = None

    @property
    def status(self) -> str:
        if self.category:
            return "active"
        return "unsupported" if self.unsupported else "review"


def _gender(key: str) -> str | None:
    words = set(key.split())
    male = words.intersection({"muzi", "chlapci", "dorostenci"})
    female = words.intersection({"zeny", "divky", "dorostenky"})
    if bool(male) == bool(female):
        return None
    return "male" if male else "female"


def _event_key(competition: dict) -> str:
    league = competition.get("league") or []
    if isinstance(league, str):
        league = [league]
    return label_key(" ".join([competition.get("name") or "", *league]))


def resolve_category(
    name: str, raw_discipline: str | None, competition: dict, person: dict,
    *, team: str | None = None, team_table: bool = False, gender: str | None = None,
    verified_individual_row: bool = False,
) -> Resolution:
    original = _resolve_category(name, raw_discipline, competition, person,
                                 team=team, team_table=team_table, gender=gender,
                                 verified_individual_row=verified_individual_row)
    if original.discipline is None or team_table:
        return original
    key = label_key(name)
    if team and all(str(person.get(field) or "").strip() for field in ("first_name", "last_name")):
        if team_source := team_member_source(key, original.discipline, competition):
            return Resolution(original.discipline, reason="team_member_result_requires_separate_treatment",
                              evidence={"kind": "team_member_standing", "url": team_source},
                              per_result=original.per_result)
    if original.category:
        return original
    verified = organizer_label(key, original.discipline, competition)
    if verified is None:
        return original
    official_label, source_url = verified
    resolved = _resolve_category(official_label, raw_discipline, competition, person,
                                 team=team, gender=gender, verified_individual_row=verified_individual_row)
    return replace(resolved, evidence={"kind": "organizer_category", "label": official_label, "url": source_url})


def _resolve_category(
    name: str, raw_discipline: str | None, competition: dict, person: dict,
    *, team: str | None = None, team_table: bool = False, gender: str | None = None,
    verified_individual_row: bool = False,
) -> Resolution:
    discipline = source_discipline(raw_discipline)
    if discipline is None:
        return Resolution(None, reason="unsupported_discipline" if raw_discipline else "missing_discipline",
                          unsupported=bool(raw_discipline))

    key = label_key(name)
    age_range = source_age(name)
    age = competition_age(competition.get("date"), person.get("birth_year"))
    person_named = all(str(person.get(field) or "").strip() for field in ("first_name", "last_name"))
    # Old importer preserved team ranking rows with empty person fields.
    rosterless_team = bool(team and not any(person.get(k) for k in ("first_name", "last_name", "birth_year", "fscode")))
    words = set(key.split())
    stated_gender = _gender(key)
    if gender in {"male", "female"} and stated_gender not in {None, gender}:
        return Resolution(discipline, reason="conflicting_gender")
    if gender is None:
        gender = stated_gender

    direct = CANONICAL_NAME.get((discipline, key))
    explicit_team = bool(words & {"druzstvo", "druzstva", "druzstev"})
    if team_table or explicit_team:
        team_label = " ".join(word for word in key.split() if word not in {"druzstvo", "druzstva", "druzstev"})
        if (
            discipline == "100m" and team_label in {"dorostenci", "dorostenky", "dorost chlapci", "dorost divky"}
            and rosterless_team and PROGRESSION.search(_event_key(competition))
        ):
            return Resolution(discipline, next(c for c in CATEGORIES if c.type == "team" and c.gender == gender))
        return Resolution(discipline, reason="unverified_team_or_progression")

    if rosterless_team and not verified_individual_row:
        return Resolution(discipline, reason="unverified_team_or_progression")

    if discipline == "60m":
        # Explicit subdivisions and conflicting age intervals never become general groups.
        key = key.replace("stasi ", "starsi ")
        youth = "younger" if "mladsi" in key.split() else "older" if "starsi" in key.split() else None
        label_pattern = r"(?:(?:mladsi|starsi)(?: zaci| zakyne)?(?: [ab])? )?(?:divky|chlapci)(?: (?:mladsi|starsi|a|b))?"
        core = re.sub(r"\b(?:vek|od|let)\b", " ", key)
        core = re.sub(r"\b\d+\b.*", "", core)
        core = " ".join(core.split())
        conflicting_groups = {"mladsi", "starsi"} <= words
        if gender and not conflicting_groups and re.fullmatch(label_pattern, core):
            if age_range:
                for category in CATEGORIES:
                    if category.discipline != "60m" or category.gender != gender:
                        continue
                    if category.age_system == "general":
                        allowed_youth = "younger" if category.min_age == 6 else "older"
                        compatible = (category.min_age, category.max_age) == age_range or (
                            allowed_youth == "older" and age_range == (11, 15)
                        )
                        if youth == allowed_youth and compatible and not words & {"a", "b"}:
                            return Resolution(discipline, category)
                    elif (category.min_age, category.max_age) == age_range:
                        expected = "younger" if category.max_age <= 11 else "older"
                        if youth not in {None, expected}:
                            break
                        return _validated(category, age, person, competition)
                return Resolution(discipline, reason="noncanonical_60m_age_range")
            if youth and not words & {"a", "b"} and not any(word.isdigit() for word in words):
                category = next(c for c in CATEGORIES if c.discipline == discipline and c.gender == gender
                                and c.age_system == "general" and c.key.endswith(youth))
                return Resolution(discipline, category)
        return Resolution(discipline, reason="unverified_60m_category")

    if key == "muzi hzs":
        # Named rows in documented HZS national championships are individual standings.
        if person_named and re.search(r"\bmcr (?:v|ve) ps\b|\bmistrovstvi ceske republiky v pozarnim sportu\b",
                                     _event_key(competition)):
            return _validated(CANONICAL_NAME[("100m", "muzi")], age, person, competition, affiliation="HZS")
        return Resolution(discipline, reason="unverified_hzs_context", affiliation="HZS")

    if direct:
        return _validated(direct, age, person, competition)

    # Recognized 100 m aliases and combined groups. Exact numeric ranges restrict
    # the eligible targets, even when an adult label is used for youth starts.
    base = re.sub(r"\s+(?:(?:vek|nad)\s+)?\d.*", "", key)
    title = re.fullmatch(r"(mladsi|stredni|starsi) (dorost|dorostenci|dorostenky)", base)
    reversed_title = re.fullmatch(r"(dorostenci|dorostenky) (mladsi|stredni|starsi)", base)
    youth = title[1] if title else reversed_title[2] if reversed_title else None
    youth_range = {"mladsi": (13, 14), "stredni": (15, 16), "starsi": (17, 18)}
    bare_youth = base in {"dorostenci", "dorostenky", "dorost chlapci", "dorost divky"}
    combined = bool(re.fullmatch(
        r"(?:(?:dorostenci|dorost chlapci)(?: a)? muzi|(?:dorostenky|dorost divky)(?: a)? zeny|"
        r"muzi(?: a)? starsi dorostenci|zeny(?: a)? starsi dorostenky)", base
    ))
    if not (title or reversed_title or bare_youth or combined or base in {"muzi", "zeny", "chlapci", "divky"}):
        return Resolution(discipline, reason="unverified_100m_category")
    bounds = age_range
    if bounds is None:
        if youth:
            bounds = youth_range[youth]
        elif bare_youth:
            bounds = (13, 18)
        elif combined:
            # 'nad 17' is interpreted literally, not as a synonym for 17–100.
            bounds = (18 if "nad 17" in key else 17 if "starsi" in words else 13, 100)
    if not bounds or not gender:
        return Resolution(discipline, reason="missing_100m_age_range_or_gender", per_result=True)
    if (youth and bounds != youth_range[youth]) or (bare_youth and not 13 <= bounds[0] <= bounds[1] <= 18):
        return Resolution(discipline, reason="conflicting_source_age_range")

    candidates = [
        c for c in CATEGORIES if c.discipline == discipline and c.gender == gender and c.type == "individual"
        and c.min_age <= bounds[1] and c.max_age >= bounds[0]
    ]
    if len(candidates) == 1 and bounds == (candidates[0].min_age, candidates[0].max_age):
        return _validated(candidates[0], age, person, competition)
    if (not person_named and not verified_individual_row) or age is None:
        return Resolution(discipline, reason="missing_verified_individual_or_birth_year", per_result=True)
    if bounds[0] <= age <= bounds[1]:
        for category in candidates:
            if category.min_age <= age <= category.max_age:
                return Resolution(discipline, category, per_result=True)
    return Resolution(discipline, reason="outside_source_or_canonical_age_range", per_result=True)


def _validated(category, age, person, competition, *, affiliation=None):
    if person.get("birth_year") is not None and competition.get("date") and (
        age is None or not category.min_age <= age <= category.max_age
    ):
        return Resolution(category.discipline, reason="outside_canonical_age_range", affiliation=affiliation)
    return Resolution(category.discipline, category, affiliation=affiliation)


def source_performance_issue(row: dict) -> str | None:
    """Flag contradictory official statuses without changing the original performance."""
    if row.get("final_time_status") != "valid":
        return None
    time = row.get("final_time")
    attempts = row.get("times") or []
    if time in FINAL_TIME_SENTINELS or (
        time in (1800, 3540) and attempts and all(attempt.get("status") == "invalid" for attempt in attempts)
    ):
        return "possible_placeholder_final_time"
    if type(time) not in (int, float) or not 0 < time < float("inf"):
        return "missing_or_invalid_official_final_time"
    return None
