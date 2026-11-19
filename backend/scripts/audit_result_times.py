"""Audit results in data/ without writing to the results or the database."""

import argparse
import json
import math
from collections import Counter
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from statistics import quantiles
from urllib.parse import urlsplit

from app.extraction.times import final_attempt_issue

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
REVIEW_LIMITS = {"100m": 32.16, "60m": 38.14}


def html_source_check(snapshot_dir):
    from app.extraction.fetch import Fetcher
    from app.extraction.html import parse_html
    from app.extraction.storage import source_id

    fetcher = Fetcher(timeout=8)

    @lru_cache
    def load(url):
        archive = snapshot_dir / source_id(url) / "source.html"
        try:
            if archive.is_file():
                data = archive.read_bytes()
                provenance = "archived_html"
            else:
                data, resolved = fetcher.get(url)
                if resolved != url:
                    raise ValueError(f"Unexpected resolved URL: {resolved}")
                provenance = "downloaded_html"
            competition, _, _, _ = parse_html(data, url)
        except (OSError, ValueError) as error:
            return None, {"status": "source_unresolved", "detail": str(error)}
        return competition, {"provenance": provenance, "sha256": sha256(data).hexdigest()}

    def check(candidate, row):
        url = candidate["source_file"] or ""
        source = urlsplit(url)
        if source.scheme != "https" or source.netloc != "pozarnisporty.cz" or not source.path.startswith("/races/"):
            return {"status": "manual_source_review"}
        competition, evidence = load(url)
        if competition is None:
            return evidence
        if not candidate["date"] or competition["date"] != candidate["date"]:
            return {**evidence, "status": "source_date_unresolved"}
        matches = [
            source_row
            for category in competition["categories"]
            if (category["name"], category["discipline"]) == (candidate["category"], candidate["discipline"])
            for source_row in category["results"]
            if same_participant(row, source_row)
        ]
        if len(matches) != 1:
            return {**evidence, "status": "source_row_unresolved"}
        published = matches[0]
        return {
            **evidence,
            "status": "agrees" if performance(row) == performance(published) else "differs",
            "final_time": published["final_time"],
            "final_status": published["final_status"],
            "times": published["times"],
        }

    return check


def same_participant(row, source):
    def identity(entry):
        return tuple(" ".join((entry.get(key) or "").casefold().split()) for key in (
            "first_name", "last_name", "team",
        ))

    first, last, team = identity(row)
    source_first, source_last, source_team = identity(source)
    bib, source_bib = row.get("start_number"), source.get("start_number")
    if all((first, last)):
        return (first, last, team) == (source_first, source_last, source_team) and (
            not bib or not source_bib or bib == source_bib
        )
    return bool(bib and bib == source_bib and (not team or team == source_team))


def performance(row):
    attempts = [(a["try"], a["time"], a["status"]) for a in row["times"] if a["try"] in (1, 2)]
    return row["final_time"], row["final_status"], attempts


def audit(data_dir, *, check_source=None):
    candidates = []
    by_discipline = {discipline: [] for discipline in REVIEW_LIMITS}
    for path in sorted(data_dir.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"), parse_constant=str)
        competition = document["competition"]
        for category_index, category in enumerate(competition["categories"]):
            discipline = category.get("discipline")
            if discipline not in REVIEW_LIMITS:
                continue
            for result_index, row in enumerate(category["results"]):
                if row.get("final_status") != "valid":
                    continue
                final = row.get("final_time")
                attempts = row.get("times") or []
                if type(final) not in (float, int) or not math.isfinite(final) or final <= 0:
                    reasons = ["missing_or_invalid_official_final_time"]
                else:
                    by_discipline[discipline].append(final)
                    issue = final_attempt_issue(final, attempts)
                    reasons = [issue] if issue else []
                    if final > REVIEW_LIMITS[discipline]:
                        reasons.append("above_review_limit")
                if reasons:
                    candidate = {
                        "review_status": "needs_review",
                        "reasons": reasons,
                        "file": path.relative_to(data_dir).as_posix(),
                        "source_file": document.get("source_file"),
                        "competition": competition["name"],
                        "date": competition.get("date"),
                        "discipline": discipline,
                        "category": category["name"],
                        "result_pointer": f"/competition/categories/{category_index}/results/{result_index}",
                        "rank": row.get("rank"),
                        "start_number": row.get("start_number"),
                        "final_time": final,
                        "times": attempts,
                    }
                    if check_source is not None:
                        candidate["source_check"] = check_source(candidate, row)
                    candidates.append(candidate)

    summary = {}
    for discipline, times in by_discipline.items():
        reasons = Counter(
            reason
            for candidate in candidates if candidate["discipline"] == discipline
            for reason in candidate["reasons"]
        )
        summary[discipline] = {
            "review_limit": REVIEW_LIMITS[discipline],
            "valid_positive_finite_times": len(times),
            "p99": quantiles(times, n=100, method="inclusive")[-1] if len(times) > 1 else max(times, default=None),
            "maximum": max(times, default=None),
            "candidate_count": sum(candidate["discipline"] == discipline for candidate in candidates),
            "reason_counts": dict(reasons),
        }
    report = {"disciplines": summary, "candidates": candidates}
    if check_source is not None:
        report["source_summary"] = dict(Counter(row["source_check"]["status"] for row in candidates))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--verify-html", action="store_true", help="Compare with official pozarnisporty.cz race pages")
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_DATA_DIR.parent / ".extraction-diagnostics")
    args = parser.parse_args()
    if not args.data_dir.is_dir():
        parser.error(f"Data directory does not exist: {args.data_dir}")
    check_source = html_source_check(args.snapshot_dir) if args.verify_html else None
    print(json.dumps(audit(args.data_dir, check_source=check_source), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
