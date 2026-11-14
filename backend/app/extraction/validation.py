import json
import math
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).with_name("results.schema.json")


def validate(document, audit=None):
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(document)
    for category in document["competition"]["categories"]:
        rows = category["results"]
        signatures = set()
        for row in rows:
            signature = json.dumps(row, sort_keys=True, ensure_ascii=False)
            if signature in signatures:
                raise ValueError(f"Duplicate result in {category['name']}")
            signatures.add(signature)
            tries = [t["try"] for t in row["times"]]
            if len(set(tries)) != len(tries):
                raise ValueError("Duplicate attempt number")
            if any(
                "neobsazen" in str(row[field]).lower()
                for field in ("first_name", "last_name")
            ):
                raise ValueError("Unoccupied slot is not a participant")
            for attempt in row["times"]:
                number = attempt["time"]
                if number is not None and (
                    not math.isfinite(number)
                    or number < 0
                    or number in (998, 999, 999.99, 999990)
                ):
                    raise ValueError("Invalid numeric time")
                if attempt["status"] == "valid" and number is None:
                    raise ValueError("Valid attempt requires measured time")
                if attempt["status"] == "missing" and number is not None:
                    raise ValueError("Missing attempt must have null time")
            if row["final_status"] != "valid" and row["final_time"] is not None:
                raise ValueError("Nonvalid final must have null time")
            if row["final_status"] == "valid" and (
                row["final_time"] is None
                or not math.isfinite(row["final_time"])
                or row["final_time"] in (998, 999, 999.99, 999990)
            ):
                raise ValueError("Valid final requires measured time")
    if audit is not None:
        categories = document["competition"]["categories"]
        if len(audit) != len(categories):
            raise ValueError("Category audit mismatch")
        for source, category in zip(audit, categories):
            if source["category"] != category["name"] or source["rows"] != len(
                category["results"]
            ):
                raise ValueError("Source row count mismatch")
            assigned = sum(
                "invalid_reason" in t for r in category["results"] for t in r["times"]
            )
            if assigned != source["numbered_reasons"]:
                raise ValueError("Numbered penalty audit mismatch")
