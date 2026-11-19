"""Conservative Unicode normalization for already separated personal names."""
import unicodedata

NAME_FIELDS = ("first_name", "last_name")


def normalize_person_name(value: str | None) -> str:
    text = " ".join(unicodedata.normalize("NFC", value if isinstance(value, str) else "").split())
    if len(text) > 1 and text.isalpha() and text.islower():
        return text[0].upper() + text[1:]
    return text


def name_issues(person: dict) -> list[str]:
    issues = []
    for field in NAME_FIELDS:
        raw = person.get(field)
        if not isinstance(raw, str) or not raw.strip():
            issues.append(f"missing_{field}")
            continue
        normalized = normalize_person_name(raw)
        if normalized != raw:
            issues.append(f"format_{field}")
        if (normalized[0].islower() or sum(c.isupper() for c in normalized) > 1 and normalized.isupper()
                or any(not (c.isalpha() or unicodedata.category(c).startswith("M") or c in " -‐‑'’")
                       for c in normalized)):
            issues.append(f"verify_{field}")
    return issues


def missing_name(person: dict) -> bool:
    return not all(normalize_person_name(person.get(field)) for field in NAME_FIELDS)
