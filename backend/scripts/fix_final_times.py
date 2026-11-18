#!/usr/bin/env python3
"""Report time discrepancies in source JSON files without modifying them."""

import argparse
import json
from pathlib import Path

from app.result_values import best_valid_attempt, final_result_fields


def inspect_times(document):
    for category in document.get("competition", {}).get("categories", []):
        for index, row in enumerate(category.get("results", []), 1):
            final = final_result_fields(row, status_key="final_status")
            best = best_valid_attempt(row.get("times", []))
            status, time = final["final_time_status"], final["final_time"]
            if status == "valid" and (best is None or time == best):
                continue
            yield {
                "category": category.get("name"),
                "discipline": category.get("discipline"),
                "row": index,
                "final_time": time,
                "final_status": status,
                "best_valid_attempt": best,
                "conflict": best is not None and status in {"valid", "invalid"},
            }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", type=Path, nargs="+")
    args = parser.parse_args(argv)
    reports = {}
    for path in args.files:
        try:
            reports[str(path)] = list(
                inspect_times(json.loads(path.read_text(encoding="utf-8")))
            )
        except (OSError, ValueError) as exc:
            reports[str(path)] = {"error": str(exc)}
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return int(any(isinstance(items, dict) for items in reports.values()))


if __name__ == "__main__":
    raise SystemExit(main())
