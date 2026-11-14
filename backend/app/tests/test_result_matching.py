import asyncio
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.result import MatchStatus
from app.services.result_matching import decide_athlete_match


def _athlete(identifier, year=None, codes=(), *, first="Jan", last="Novák", active=True):
    return {
        "_id": identifier,
        "first_name": first,
        "last_name": last,
        "birth_year": year,
        "fs_codes": list(codes),
        "teams": ["Lhota"],
        "is_active": active,
    }


def _matches(doc, query):
    for key, condition in query.items():
        if key == "$and":
            if not all(_matches(doc, entry) for entry in condition):
                return False
        elif key == "$or":
            if not any(_matches(doc, entry) for entry in condition):
                return False
        elif isinstance(condition, dict):
            value = doc.get(key)
            if "$ne" in condition and value == condition["$ne"]:
                return False
            if "$in" in condition and not any(item in value for item in condition["$in"]):
                return False
            if "$regex" in condition and not any(
                re.search(condition["$regex"], item, re.I)
                for item in (value if isinstance(value, list) else [value])
            ):
                return False
        elif doc.get(key) != condition:
            return False
    return True


@pytest.mark.parametrize(
    "profiles, year, code, last, team, status, reason, expected_id",
    [
        ([_athlete(1, 2000), _athlete(2, 2001)], 2000, None, "Novák", None,
         "matched", "name_plus_birth_year", 1),
        ([_athlete(1, 2000)], 2001, None, "Novák", "Lhota",
         "needs_review", "conflicting_birth_year", None),
        ([_athlete(1, 2000), _athlete(2, 2000)], 2000, None, "Novák", "Lhota",
         "needs_review", "multiple_name_candidates", None),
        ([_athlete(1, 2000)], None, None, "Novák", "Lhota",
         "needs_review", "insufficient_identity", None),
        ([_athlete(1, 2000)], 2000, None, "Novák", "Bukovice",
         "matched", "name_plus_birth_year", 1),
        ([_athlete(1, 2000, [12345, "54321"])], None, "12345", "Novák", None,
         "matched", "name_plus_fscode", 1),
        ([_athlete(1, 2000, ["12345"]), _athlete(2, 2000)], 2000, "12345", "Novák", None,
         "matched", "name_plus_fscode", 1),
        ([_athlete(1, 2000), _athlete(2, 2000, ["12345"], last="Malý")], 2000, "12345", "Novák", None,
         "needs_review", "conflicting_fscode", None),
        ([_athlete(1, 2000, ["12345"]), _athlete(2, 2000, ["12345"], last="Malý")],
         2000, "12345", "Novák", None, "needs_review", "shared_fscode", None),
        ([_athlete(1, None, ["12345"]), _athlete(2, 2000)], 2000, "12345", "Novák", None,
         "needs_review", "conflicting_fscode", None),
        ([_athlete(1, 2000, ["54321"])], 2000, "12345", "Novák", None,
         "needs_review", "unrecognized_fscode", None),
        ([_athlete(1, 2000)], None, None, "Novák", None, "needs_review", "insufficient_identity", None),
        ([_athlete(1, 2000), _athlete(2)], 2000, None, "Novák", None,
         "needs_review", "multiple_name_candidates", None),
        ([_athlete(1, 2000)], 2000, None, "Novak", None, "needs_review", "insufficient_identity", None),
        ([_athlete(1, 2000)], 2000, None, "Novka", None, "needs_review", "possible_name_variant", None),
        ([_athlete(1, 2000, ["12345"])], 2000, "12345", "Novak", None,
         "needs_review", "conflicting_fscode", None),
        ([_athlete(1, 2000), _athlete(2, 2000, active=False)], 2000, None, "Novák", None,
         "matched", "name_plus_birth_year", 1),
        ([_athlete(1, 2000, last="Novák Svoboda")], 2000, None, "NovákSvoboda", None,
         "needs_review", "insufficient_identity", None),
        ([], 2000, "12345", "Novák", None, "unmatched", "no_match", None),
    ],
)
def test_automatic_matching(profiles, year, code, last, team, status, reason, expected_id):
    def find(query):
        docs = [doc for doc in profiles if _matches(doc, query)]
        cursor = MagicMock(to_list=AsyncMock(return_value=docs))
        cursor.limit.return_value = cursor
        return cursor

    with patch("app.services.result_matching.athletes_collection.find", side_effect=find):
        result = asyncio.run(
            decide_athlete_match(first_name="Jan", last_name=last, birth_year=year, fscode=code, team=team)
        )

    assert result["match_status"] == MatchStatus(status)
    assert result["match_reason"] == reason
    athlete = result["matched_athlete"]
    assert (athlete["_id"] if athlete else None) == expected_id
