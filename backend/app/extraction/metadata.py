import re
import unicodedata
from datetime import date


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or "").lower())
    return re.sub(
        r"\s+", " ", "".join(c for c in value if not unicodedata.combining(c))
    ).strip()


def parse_date(text):
    patterns = [
        r"\b(\d{4})-(\d{2})-(\d{2})\b",
        r"\b(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})\b",
    ]
    for i, pattern in enumerate(patterns):
        m = re.search(pattern, text or "")
        if m:
            a, b, c = map(int, m.groups())
            try:
                return (
                    date(a, b, c).isoformat() if i == 0 else date(c, b, a).isoformat()
                )
            except ValueError:
                return None
    return None


def discipline(text):
    text = norm(text)
    for pattern, value in [
        (r"4\s*[x×]\s*100", "4x100m"),
        (r"100\s*m\s*(?:php|p)\b", "100mPHP"),
        (r"\b60\s*m\b|sedesatk", "60m"),
        (r"\b100\s*m\b|stovk", "100m"),
        (r"pozarni utok|\bpu\b", "PU"),
        (r"\bvez\b", "vez"),
    ]:
        if re.search(pattern, text):
            return value
    return None


def category_discipline(name, explicit, document):
    result = discipline(explicit) or discipline(name)
    if result:
        return result
    # Only use age mapping if the organizer explicitly defines both groups.
    text = norm(document)
    if (
        re.search(r"60\s*m", text)
        and re.search(r"100\s*m", text)
        and "pro kategorie dorost" in text
        and "mladsi zaci" in text
    ):
        category = norm(name)
        if re.search(r"(mladsi|starsi) zaci", category):
            return "60m"
        if re.search(r"dorost|muzi|zeny", category):
            return "100m"
    # A single explicit discipline is usable document-wide; conflicting ones are not.
    tokens = re.findall(
        r"4\s*[x×]\s*100\s*m?|100\s*m\s*(?:PHP|P)\b|(?:60|100)\s*m\b|"
        r"šedesát\w*|stovk\w*|požární útok|\bPU\b|(?:výstup na )?věž",
        document,
        re.I,
    )
    found = {discipline(token) for token in tokens} - {None}
    return next(iter(found)) if len(found) == 1 else None


def competition_metadata(soup, warnings, *, site=False):
    def element_text(selector):
        element = soup.select_one(selector)
        return element.get_text(" ", strip=True) if element else None

    def labelled(selector):
        element = soup.select_one(selector)
        children = element.find_all(recursive=False) if element else []
        return children[-1].get_text(" ", strip=True) if len(children) >= 2 else None

    title = element_text("h1")
    if site:
        title = element_text("main .text-normal") or title
    place = labelled("#place") or element_text("[data-race-place]")
    when = labelled("#start") or element_text("[data-race-date]")
    league = element_text("[data-race-league]")
    if not league and site and title:
        m = re.match(r"(STIMAX CUP\s+\d{4})(?:\s+-|$)", title)
        league = m[1] if m else None
    if title:
        title = re.sub(
            r"(?:\s+[-–|]\s+)?\b\d{1,2}\.\s*\d{1,2}\.\s*\d{4}\b(?:\s+\d{1,2}:\d{2})?",
            "",
            title,
        ).strip(" –-|")
        if (
            norm(title)
            in {
                "cesky pohar",
                "okresni kolo",
                "krajske kolo",
                "serial zavodu",
                "vysledkova listina",
            }
            and place
        ):
            title += f" – {place}"
    result = {"name": title, "place": place, "date": parse_date(when), "league": league}
    for key, value in result.items():
        if value is None:
            warnings.append(f"Competition: unavailable {key}")
    return result
