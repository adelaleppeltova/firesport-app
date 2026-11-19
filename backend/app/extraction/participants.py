import re
import unicodedata
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


def name_part(raw):
    """Return a name field for parsing while leaving its source text to the caller."""
    text = " ".join(unicodedata.normalize("NFC", raw if isinstance(raw, str) else "").split())
    lexical = re.sub(r" (?:ml|st)\.$", "", text, flags=re.I)
    if (any(c.isalpha() for c in lexical)
            and all(c.isalpha() or unicodedata.category(c).startswith("M") or c in " -‐‑'’" for c in lexical)):
        return text
    return None


SITE_NAME_SUFFIX = re.compile(
    r"\s+\((?:[0-9]+|Praha|Středočeský|Jihočeský|Plzeňský|Karlovarský|Ústecký|Liberecký|"
    r"Královéhradecký|Pardubický|Vysočina|Jihomoravský|Olomoucký|Zlínský|Moravskoslezský|)\)$"
)


def split_name(raw, warnings, context, *, surname_first=None, surname_uppercase=False, site_suffix=False):
    text = " ".join((raw or "").split())
    if site_suffix:
        while (cleaned := SITE_NAME_SUFFIX.sub("", text)) != text:
            text = cleaned
    if text.count(",") == 1:
        left, right = map(name_part, text.split(","))
        if left and right:
            return (left, right) if surname_first is False else (right, left)
    parts = text.split()
    if surname_first is not None and len(parts) == 2 and all(name_part(part) for part in parts):
        return (parts[1], parts[0]) if surname_first else tuple(parts)
    if surname_first and len(parts) >= 4 and norm(" ".join(parts[:2])) in {"van de", "van der", "von der"}:
        last, first = name_part(" ".join(parts[:3])), name_part(" ".join(parts[3:]))
        if last and first:
            return first, last
    if surname_uppercase and parts and all(name_part(part) for part in parts):
        styles = [part.isupper() for part in parts]
        boundaries = [i for i in range(1, len(styles)) if styles[i] != styles[i - 1]]
        if len(boundaries) == 1 and (surname_first is None or surname_first == styles[0]):
            boundary = boundaries[0]
            left, right = " ".join(parts[:boundary]), " ".join(parts[boundary:])
            return (right, left) if styles[0] else (left, right)
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
