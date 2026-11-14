import re
from .metadata import norm


def integer(value):
    text = str(value or "").strip().rstrip(".")
    return int(text) if re.fullmatch(r"\d+", text) else None


def fscode(raw, warnings, context):
    value = str(raw or "").strip()
    if not re.fullmatch(r"\d{4,}", value):
        if value:
            warnings.append(f"{context}: invalid FSCode {value!r}")
        return None
    if value.startswith("0"):
        warnings.append(f"{context}: FSCode leading zero formatting lost: {value}")
    return int(value)


def split_name(raw, warnings, context, *, surname_first=False):
    text = re.sub(r"\s*\([^)]*\)", "", raw).strip()
    if "," in text:
        last, first = text.split(",", 1)
        if last.strip() and first.strip():
            return first.strip(), last.strip()
    parts = text.split()
    if surname_first and len(parts) == 2:
        return parts[1], parts[0]
    # Recognizable surname particles, using the source's surname-first convention.
    if (
        surname_first
        and len(parts) >= 4
        and norm(" ".join(parts[:2])) in {"van de", "van der", "von der"}
    ):
        return " ".join(parts[3:]), " ".join(parts[:3])
    warnings.append(f"{context}: ambiguous name segmentation: {raw!r}")
    return None, None


def birth_year(raw):
    m = re.fullmatch(
        r"\s*(?:\d{1,2}\.\s*\d{1,2}\.\s*|\d{2}-\d{2}-)?(\d{4})\s*", str(raw or "")
    )
    if m:
        return int(m[1])
    m = re.fullmatch(r"(\d{4})-\d{2}-\d{2}", str(raw or "").strip())
    return int(m[1]) if m else None


def profile_year(soup):
    for label in soup.find_all(
        string=re.compile(r"^\s*(Narozen[áa]?|Born)\s*:\s*$", re.I)
    ):
        sibling = label.parent.find_next_sibling()
        if sibling:
            return birth_year(sibling.get_text(" ", strip=True))
    return None


def split_team_times(team, first, second):
    """Repair only an explicit two-time suffix when both mapped time cells are empty."""
    if first or second or not team:
        return team, first, second, False
    match = re.fullmatch(
        r"(\S(?:.*\S)?)\s+(\d{1,3}[,.]\d{2,3})\s+(\d{1,6}[,.]\d{2,3})", team
    )
    if not match:
        return team, first, second, False
    return match[1], match[2], match[3], True
