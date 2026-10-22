"""Check local Markdown links, README parity, and recount versioned JSON inputs.

Run from any directory: python3 docs/scripts/check_documentation.py
Uses only the standard library; never connects to MongoDB or changes data.
External URLs, Mermaid rendering and translated meaning require human review.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def prose(text: str) -> str:
    return re.sub(r"^```.*?^```[^\n]*$", "", text, flags=re.M | re.S)


def headings(text: str) -> list[str]:
    return re.findall(r"^#{1,6} (.+)$", prose(text), re.M)


def anchors(text: str) -> set[str]:
    found: set[str] = set()
    counts: dict[str, int] = {}
    for heading in headings(text):
        slug = "".join(
            char for char in heading.lower()
            if char in "_- " or unicodedata.category(char)[0] in "LN"
        ).replace(" ", "-")
        n = counts.get(slug, 0)
        counts[slug] = n + 1
        found.add(f"{slug}-{n}" if n else slug)
    return found


def main() -> None:
    files = [ROOT / "README.md", ROOT / "README.cs.md", *sorted((ROOT / "docs").rglob("*.md"))]
    errors: list[str] = []
    link_count = 0
    for path in files:
        for target in LINK.findall(prose(path.read_text())):
            target = target.strip().removeprefix("<").removesuffix(">")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            link_count += 1
            destination = path.parent / unquote(parsed.path) if parsed.path else path
            if not destination.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing {target}")
            elif parsed.fragment and destination.suffix == ".md":
                if unquote(parsed.fragment) not in anchors(destination.read_text()):
                    errors.append(f"{path.relative_to(ROOT)}: missing anchor {target}")
    en = (ROOT / "README.md").read_text()
    cs = (ROOT / "README.cs.md").read_text()
    if len(headings(en)) != len(headings(cs)):
        errors.append("README heading counts differ")
    if re.findall(r"!\[[^\]]*\]\((docs/screenshots/[^)]+)\)", en) != re.findall(
        r"!\[[^\]]*\]\((docs/screenshots/[^)]+)\)", cs
    ):
        errors.append("README screenshot order/paths differ")
    if "[CZ](README.cs.md)" not in en or "[EN](README.md)" not in cs:
        errors.append("README language navigation missing")

    inputs = sorted((ROOT / "data").rglob("*.json"))
    records = [json.loads(path.read_text()) for path in inputs]
    categories = [c for d in records for c in d["competition"]["categories"]]
    results = [r for c in categories for r in c["results"]]
    dates = [d["competition"]["date"] for d in records]
    print(json.dumps({
        "json_files": len(inputs), "category_blocks": len(categories),
        "source_results": len(results), "date_min": min(dates), "date_max": max(dates),
        "missing_or_zero_birth_year": sum(not r.get("birth_year") for r in results),
        "missing_fs_code": sum(not r.get("fscode") for r in results),
        "non_valid_final_status": sum(r.get("final_status") != "valid" for r in results),
        "missing_discipline_blocks": sum(not c.get("discipline") for c in categories),
        "files_with_source_file": sum("source_file" in d for d in records),
        "files_with_generated_at": sum("generated_at" in d for d in records),
    }, indent=2))
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(files)} Markdown files and {link_count} local links; README structure/images agree.")


if __name__ == "__main__":
    main()
