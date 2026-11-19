"""Scope of the administrator's result matching queue."""

from app.category_catalog import DISCIPLINES, active_results
from app.models.result import MatchStatus

REVIEW_STATUSES = (MatchStatus.needs_review.value, MatchStatus.unmatched.value)


def review_results_query() -> dict:
    return {**active_results(individual=True), "match_status": {"$in": list(REVIEW_STATUSES)}}


def in_review_queue(row: dict) -> bool:
    """Evaluate the queue scope on an offline BSON result snapshot."""
    discipline = row.get("discipline")
    if discipline not in DISCIPLINES or row.get("match_status") not in REVIEW_STATUSES:
        return False
    scope = active_results(discipline=discipline, individual=True)
    return row.get("category") in scope["category"]["$in"] and all(
        row.get(field) == value for field, value in scope.items() if field != "category"
    )
