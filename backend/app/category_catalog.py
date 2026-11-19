"""Canonical application categories. Extraction keeps the original source categories."""
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Literal

from bson import ObjectId

from app.person_names import missing_name

Discipline = Literal["100m", "60m"]
DISCIPLINES: dict[Discipline, str] = {
    "100m": "Běh na 100 m s překážkami",
    "60m": "Běh na 60 m s překážkami",
}
CATEGORY_COLLECTION = "canonical_categories"
CATALOG_VERSION = 1
FINAL_TIME_SENTINELS = (998, 999, 999.99, 999990)
VALID_FINAL_TIME_FILTER = {
    "final_time_status": "valid",
    "final_time": {"$gt": 0, "$lt": float("inf"), "$nin": list(FINAL_TIME_SENTINELS)},
}


@dataclass(frozen=True)
class Category:
    key: str
    name: str
    discipline: Discipline
    gender: Literal["male", "female"]
    min_age: int
    max_age: int
    type: Literal["individual", "team"] = "individual"
    age_system: Literal["general", "age_group"] = "age_group"

    @property
    def id(self) -> ObjectId:
        return ObjectId(sha256(f"firesport/canonical-category/{self.key}".encode()).digest()[:12])

    def document(self) -> dict:
        return {"_id": self.id, **asdict(self)}


CATEGORIES = (
    Category("100m-men", "Muži", "100m", "male", 19, 100),
    Category("100m-boys-17-18", "Starší dorostenci", "100m", "male", 17, 18),
    Category("100m-boys-15-16", "Střední dorostenci", "100m", "male", 15, 16),
    Category("100m-boys-13-14", "Mladší dorostenci", "100m", "male", 13, 14),
    Category("100m-women", "Ženy", "100m", "female", 19, 100),
    Category("100m-girls-17-18", "Starší dorostenky", "100m", "female", 17, 18),
    Category("100m-girls-15-16", "Střední dorostenky", "100m", "female", 15, 16),
    Category("100m-girls-13-14", "Mladší dorostenky", "100m", "female", 13, 14),
    Category("100m-boys-team", "Dorostenci - družstvo", "100m", "male", 13, 18, "team"),
    Category("100m-girls-team", "Dorostenky - družstvo", "100m", "female", 13, 18, "team"),
    Category("60m-girls-younger", "Mladší dívky", "60m", "female", 6, 10, age_system="general"),
    Category("60m-boys-younger", "Mladší chlapci", "60m", "male", 6, 10, age_system="general"),
    Category("60m-girls-older", "Starší dívky", "60m", "female", 10, 15, age_system="general"),
    Category("60m-boys-older", "Starší chlapci", "60m", "male", 10, 15, age_system="general"),
    Category("60m-girls-7-8", "Mladší dívky 7–8 let", "60m", "female", 7, 8),
    Category("60m-girls-9-11", "Mladší dívky 9–11 let", "60m", "female", 9, 11),
    Category("60m-girls-12-13", "Starší dívky 12–13 let", "60m", "female", 12, 13),
    Category("60m-girls-14-15", "Starší dívky 14–15 let", "60m", "female", 14, 15),
    Category("60m-boys-7-8", "Mladší chlapci 7–8 let", "60m", "male", 7, 8),
    Category("60m-boys-9-11", "Mladší chlapci 9–11 let", "60m", "male", 9, 11),
    Category("60m-boys-12-13", "Starší chlapci 12–13 let", "60m", "male", 12, 13),
    Category("60m-boys-14-15", "Starší chlapci 14–15 let", "60m", "male", 14, 15),
)
BY_ID = {category.id: category for category in CATEGORIES}
BY_KEY = {category.key: category for category in CATEGORIES}


def active_results(*, discipline: Discipline | None = None, individual: bool = False) -> dict:
    """Shared public/statistical Mongo filter. Legacy and review rows remain private."""
    categories = [
        category for category in CATEGORIES
        if (discipline is None or category.discipline == discipline)
        and (not individual or category.type == "individual")
    ]
    if discipline is not None:
        return {
            "classification_status": "active", "discipline": discipline, "duplicate_of": None,
            **({"result_type": "individual"} if individual else {}),
            "category": {"$in": [category.id for category in categories]},
        }
    return {
        "classification_status": "active",
        "$or": [active_results(discipline=key, individual=individual) for key in DISCIPLINES],
    }


def valid_time(result: dict) -> float | None:
    value = result.get("final_time")
    if (
        result.get("final_time_status") == "valid" and type(value) in (int, float)
        and 0 < value < float("inf") and value not in FINAL_TIME_SENTINELS
    ):
        return float(value)
    return None


def supplemental_record_filter() -> dict:
    return {
        "classification_status": {"$in": ["historical", "team_member"]},
        "duplicate_of": None,
        "record_evidence.athlete": {"$exists": True},
    }


def supplemental_record_exclusion(result: dict) -> str | None:
    if result.get("duplicate_of") is not None:
        return "duplicate"
    time = valid_time(result)
    attempts = result.get("published_attempts", result.get("times")) or []
    if time is None or not any(a.get("status") == "valid" and a.get("time") == time for a in attempts):
        return "unverified_valid_time"
    status = result.get("classification_status")
    evidence = result.get("record_evidence") or {}
    if (not result.get("athlete") or evidence.get("athlete") != result["athlete"]
            or evidence.get("competition") != result.get("competition")
            or evidence.get("time") != time or evidence.get("source_url") is None):
        return "identity_or_source_unverified"
    if status == "historical":
        if (result.get("discipline") == "60m" and result.get("result_type") == "individual"
                and result.get("category") is None and result.get("historical_age_range") in ([6, 8], [8, 11])):
            return None
    if status == "team_member":
        category = BY_ID.get(result.get("category"))
        if (result.get("discipline") == "100m" and result.get("result_type") == status
                and category and category.type == "team" and category.discipline == "100m"
                and result.get("team_entry_id") and (result.get("member_evidence") or {}).get("source_sha256")):
            return None if evidence.get("rules_url") and evidence.get("rules_sha256") else "comparison_rules_unverified"
    return "unsupported_record_type"


def personal_records(results: list[dict]) -> dict[Discipline, float | None]:
    records = dict.fromkeys(DISCIPLINES)
    for result in results:
        imported = result.get("imported_athlete")
        if isinstance(imported, dict) and missing_name(imported) and (
            result.get("match_reason") not in {"manual_admin_assignment", "manual_admin_create_athlete"}
        ):
            continue
        category = BY_ID.get(result.get("category"))
        time = valid_time(result)
        discipline = result.get("discipline")
        canonical = (
            category and category.type == "individual" and time is not None
            and result.get("classification_status") == "active" and result.get("duplicate_of") is None
            and discipline == category.discipline and result.get("result_type") == "individual"
        )
        if canonical or (
            discipline in DISCIPLINES and result.get("classification_status") in {"historical", "team_member"}
            and supplemental_record_exclusion(result) is None
        ):
            current = records[discipline]
            if current is None or time < current:
                records[discipline] = time
    return records
