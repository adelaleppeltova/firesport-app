#!/usr/bin/env python3
"""Audit official final times in source JSON without changing the files."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    issues = 0
    for path in args.files:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        for category in data["competition"]["categories"]:
            for index, result in enumerate(category["results"], start=1):
                value = result.get("final_time")
                if result.get("final_status") == "valid" and not (
                    type(value) in (int, float) and 0 < value < float("inf")
                ):
                    issues += 1
                    print(f"{path} · {category['name']} · řádek {index}: ověřte oficiální výsledný čas.")
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
