import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from .validation import validate
from .paths import resolve_path


def canonical_url(url):
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            parts.query,
            "",
        )
    )


def source_id(url):
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]


def document(source, competition, notes, warnings):
    return {
        "source_file": canonical_url(source),
        "generated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
        "competition": competition,
        "parsing_notes": list(dict.fromkeys(notes)),
        "warnings": list(dict.fromkeys(warnings)),
    }


def save(document, output, audit):
    validate(document, audit)
    output = Path(output)
    path = resolve_path(document, output)
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        old = {
            c["name"]: len(c["results"]) for c in previous["competition"]["categories"]
        }
        new = {
            c["name"]: len(c["results"]) for c in document["competition"]["categories"]
        }
        if any(new.get(name, 0) < count for name, count in old.items()):
            raise ValueError(
                "Import would remove existing results/categories; review source corrections manually"
            )

        def identities(category):
            result = set()
            for row in category["results"]:
                if row["start_number"] is not None:
                    result.add(("bib", row["start_number"]))
                elif row["fscode"] is not None:
                    result.add(("fscode", row["fscode"]))
                else:
                    result.add(
                        ("name", row["first_name"], row["last_name"], row["rank"])
                    )
            return result

        current = {c["name"]: c for c in document["competition"]["categories"]}
        for category in previous["competition"]["categories"]:
            if identities(category) - identities(current[category["name"]]):
                raise ValueError(
                    "Import would remove existing participant identities; review source corrections manually"
                )
        for category in previous["competition"]["categories"]:
            replacement = current[category["name"]]
            for field in (
                "birth_year",
                "fscode",
                "first_name",
                "last_name",
                "district",
            ):
                old_known = sum(row[field] is not None for row in category["results"])
                new_known = sum(
                    row[field] is not None for row in replacement["results"]
                )
                if new_known < old_known:
                    raise ValueError(
                        f"Import would lose previously published {field}; inspect source/profile failures before replacement"
                    )
        if {k: v for k, v in previous.items() if k != "generated_at"} == {
            k: v for k, v in document.items() if k != "generated_at"
        }:
            return path
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        validate(json.loads(Path(temporary).read_text(encoding="utf-8")), audit)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def summary(document):
    categories = document["competition"]["categories"]
    rows = [r for c in categories for r in c["results"]]
    attempts = [t for r in rows for t in r["times"]]
    return {
        "categories": len(categories),
        "results": len(rows),
        "attempts": dict(Counter(t["status"] for t in attempts)),
        "invalid_reasons": sum("invalid_reason" in t for t in attempts),
        **{
            f"missing_{key}": sum(r[key] is None for r in rows)
            for key in ("fscode", "birth_year", "district")
        },
        "warnings": len(document["warnings"]),
        "validation_errors": 0,
    }
