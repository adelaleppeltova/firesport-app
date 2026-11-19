"""One regression per audit conflict using only anonymized equality patterns."""

import json
from collections import Counter
from pathlib import Path

import pytest

from app.services.data_import import DataImporter

FIXTURE = Path(__file__).parent / "fixtures" / "incremental_conflict_patterns.json"
PATTERNS = json.loads(FIXTURE.read_text())
CASES = [
    pytest.param(group["rows"], group["expected"], id=f"audit-log-line-{line}")
    for group in PATTERNS for line in group["log_lines"]
]


def test_all_audited_conflicts_have_fixtures():
    lines = [line for group in PATTERNS for line in group["log_lines"]]
    assert len(lines) == len(set(lines)) == 514
    assert Counter(case.values[1] for case in CASES) == {"insert": 94, "duplicate": 406, "review": 14}


@pytest.mark.parametrize(("rows", "expected"), CASES)
def test_audited_conflict(rows, expected, monkeypatch):
    imp = DataImporter()
    monkeypatch.setattr(imp, "_row_identity", lambda row: {k: v for k, v in row.items() if k != "_id"})
    incoming, *stored = rows
    candidates = [{**row, "_id": index} for index, row in enumerate(stored)]
    action, candidate_ids = imp.assess_result(incoming, candidates)
    assert action == expected
    assert bool(candidate_ids) == (action != "insert")
