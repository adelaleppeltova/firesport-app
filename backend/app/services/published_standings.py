"""Competition standings kept outside the individual statistics."""
from hashlib import sha256

from bson import ObjectId

from app.category_catalog import BY_KEY
from app.services.category_normalization import source_age

TEAM_MEMBER = "team_member"
HISTORICAL = "historical"
TEAM_BY_LABEL = {
    "dorostenci": BY_KEY["100m-boys-team"],
    "dorostenky": BY_KEY["100m-girls-team"],
}
HISTORICAL_AGE_RANGES = {(6, 8), (8, 11)}


def historical_age_range(source: dict) -> tuple[int, int] | None:
    age_range = (source.get("min_age"), source.get("max_age"))
    if age_range in HISTORICAL_AGE_RANGES:
        return age_range
    for evidence in source.get("classification_evidence", []):
        if evidence.get("kind") == "organizer_category":
            age_range = source_age(evidence.get("label") or "")
            if age_range in HISTORICAL_AGE_RANGES:
                return age_range
    return None


def historical_fields(discipline, reason, source) -> dict:
    if discipline == "60m" and reason == "noncanonical_60m_age_range":
        if age_range := historical_age_range(source):
            return {
                "classification_status": HISTORICAL,
                "classification_reason": None,
                "historical_age_range": list(age_range),
                "result_type": "individual",
            }
    return {}


def team_entry_id(competition: ObjectId, category: ObjectId, source_number: int) -> ObjectId:
    key = f"firesport/team-entry/{competition}/{category}/{source_number}"
    return ObjectId(sha256(key.encode()).digest()[:12])
