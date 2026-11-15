"""Synthetic replay. Run as a module with the previous matcher file for comparison."""
import asyncio
import json
import runpy
import sys
from unittest.mock import AsyncMock, patch

import pytest

from app.services.external_identity import ExternalIdentity
from app.services.result_matching import decide_athlete_match
from app.tests.test_result_matching import _athlete, mock_find

EXTERNAL_ID = ExternalIdentity(provider="example.test", person_id="70001", evidence_url="https://example.test/70001")

# Every case is independent. A null label means no matching profile exists.
CASES = [
    ("unique-code", [_athlete(1, 2000, ["12345"])], {}, 1, 1),
    ("changed-team", [_athlete(1, 2000, ["12345"])], {"team": "Nový tým"}, 1, 1),
    ("shared-code", [_athlete(1, 2000, ["12345"]), _athlete(2, 2000, ["12345"])], {}, 1, None),
    ("possible-typo", [_athlete(1, 2000)], {"last_name": "Novka", "fscode": None}, 1, None),
    ("two-identical-names", [_athlete(1, 2000), _athlete(2, 2000)], {"fscode": None}, 2, None),
    ("same-name-missing-year", [_athlete(1, 2000), _athlete(2)], {"fscode": None}, 2, None),
    ("same-name-year-team-different-person", [_athlete(1, 2000)], {"fscode": None}, None, None),
    ("same-name-year-confirmed", [_athlete(1, 2000)], {"fscode": None}, 1, None),
    ("new-profile-same-name-year", [_athlete(1, 2000)], {}, None, None),
    ("name-only", [_athlete(1, 2000)], {"fscode": None, "birth_year": None}, 1, None),
    ("known-year-conflict", [_athlete(1, 2001, ["12345"])], {}, 1, None),
    ("known-code-conflict", [_athlete(1, 2000, ["54321"])], {}, 1, None),
    ("unknown-athlete", [_athlete(1, 2000, last="Model")], {"fscode": None}, None, None),
    ("inactive-code-owner", [_athlete(1, 2000, ["12345"], active=False)], {}, None, None),
    ("verified-external-id-namesake", [_athlete(1, 2000), _athlete(2, 2000)],
     {"fscode": None, "external_owner": 2}, 2, 2),
    ("verified-external-id-no-team", [_athlete(1, 2000)], {"external_owner": 1, "fscode": None, "team": None}, 1, 1),
    ("verified-external-id-missing-name", [_athlete(1, 2000)],
     {"external_owner": 1, "fscode": None, "first_name": ""}, 1, 1),
    ("different-external-and-code-owners", [_athlete(1, 2000, ["12345"]), _athlete(2, 2000)],
     {"external_owner": 2}, 2, None),
    ("verified-external-id-conflicting-year", [_athlete(1, 2001)], {"external_owner": 1, "fscode": None}, 1, None),
    ("unknown-namespace", [_athlete(1, 2000)], {"external_owner": None, "fscode": None}, None, None),
    ("verified-external-id-conflicting-code", [_athlete(1, 2000, ["54321"])], {"external_owner": 1}, 1, None),
    ("verified-external-id-conflicting-known-name", [_athlete(1, 2000)],
     {"external_owner": 1, "fscode": None, "first_name": "", "last_name": "Jiný"}, 1, None),
    ("invalid-fscode", [_athlete(1, 2000, ["12"])], {"fscode": "12"}, 1, None),
]


async def replay(case, *, matcher=decide_athlete_match, baseline=False):
    _, profiles, overrides, _, _ = case
    observation = {"first_name": "Jan", "last_name": "Novák", "birth_year": 2000, "fscode": "12345", "team": "Lhota"}
    observation.update({key: value for key, value in overrides.items() if key != "external_owner"})
    mapping = None
    if "external_owner" in overrides and not baseline:
        observation["external_identity"] = EXTERNAL_ID
        if overrides["external_owner"] is not None:
            mapping = {"athlete_id": overrides["external_owner"]}
    with (
        patch.object(matcher.__globals__["athletes_collection"], "find", side_effect=mock_find(profiles)),
        patch("app.services.result_matching.external_identities.find_one", AsyncMock(return_value=mapping)) as lookup,
    ):
        decision = await matcher(**observation)
    if "external_identity" in observation:
        lookup.assert_awaited_once_with({"_id": EXTERNAL_ID.key})
    profile = decision["matched_athlete"]
    return (profile["_id"] if profile else None), decision["match_status"].value


@pytest.mark.parametrize("case", CASES, ids=[case[0] for case in CASES])
def test_synthetic_matching_replay(case):
    actual, _ = asyncio.run(replay(case))
    assert actual == case[4]


def test_candidate_cap_fails_closed_even_when_first_candidate_looks_unique():
    profiles = [_athlete(1, 2000, ["12345"])] + [_athlete(index, 2001) for index in range(2, 52)]
    case = ("candidate-cap", profiles, {}, 1, None)
    assert asyncio.run(replay(case)) == (None, "needs_review")


async def report(matcher, *, baseline=False):
    predictions = [await replay(case, matcher=matcher, baseline=baseline) for case in CASES]
    successful = sum(predicted is not None and predicted == case[3] for case, (predicted, _) in zip(CASES, predictions))
    false_matches = [
        case[0] for case, (predicted, _) in zip(CASES, predictions)
        if predicted is not None and predicted != case[3]
    ]
    automatic = successful + len(false_matches)
    positives = sum(case[3] is not None for case in CASES)
    return {
        "cases": len(CASES), "positives": positives, "true_matches": successful,
        "false_matches": false_matches, "needs_review": sum(status == "needs_review" for _, status in predictions),
        "unmatched": sum(status == "unmatched" for _, status in predictions),
        "admin_queue": len(CASES) - automatic,
        "precision": successful / automatic if automatic else None,
        "recall": successful / positives if positives else None,
    }


if __name__ == "__main__":
    previous_matcher = runpy.run_path(sys.argv[1])["decide_athlete_match"]
    print(json.dumps({
        "previous": asyncio.run(report(previous_matcher, baseline=True)),
        "current": asyncio.run(report(decide_athlete_match)),
    }, indent=2))
