"""Extract all published tables, preserving the original category labels."""

import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from .metadata import norm, competition_metadata, category_discipline
from .participants import (
    integer,
    fscode,
    birth_year,
    split_name,
    profile_year,
    split_team_times,
)
from .times import parse_time, final_time
from .penalties import assign_reasons

ALIASES = {
    "rank": ["or.", "poradi", "por.", "rank", "umisteni"],
    "name": ["jmeno", "zavodnik", "name"],
    "first_name": ["krestni jmeno", "first name"],
    "last_name": ["prijmeni", "last name"],
    "start_number": [
        "startovni cislo",
        "start. c.",
        "st. c.",
        "bib",
        "cislo zavodnika",
    ],
    "fscode": ["fscode", "fs code"],
    "birth_year": ["rok narozeni", "nar.", "narozen", "datum narozeni"],
    "team": ["sdh/tym", "druzstvo", "sbor", "team", "organizace"],
    "district": ["okres", "okr.", "district"],
    "final": ["vysl. cas", "vysledny cas", "nejlepsi cas", "final time"],
    "reason": [
        "duvod pen.",
        "duvod penalizace",
        "penalizace",
        "poznamka k pokusu",
        "reason",
        "invalid reason",
    ],
}


def column_map(headers):
    result = {}
    for i, header in enumerate(headers):
        key = norm(header)
        for field, aliases in ALIASES.items():
            if key in aliases:
                if field in result:
                    raise ValueError(f"Duplicate column: {field}")
                result[field] = i
        m = re.fullmatch(r"(?:cas|pokus|try)\s*([1-4])\.?", key)
        if m:
            result[f"try{m[1]}"] = i
    return result


def is_result_header(mapping):
    names = "name" in mapping or {"first_name", "last_name"} <= mapping.keys()
    return names and bool({"rank", "try1", "try2", "final"} & mapping.keys())


def table_label(table):
    caption = table.find("caption")
    if caption:
        return caption.get_text(" ", strip=True)
    # Site's explicit category container.
    for parent in table.parents:
        banner = parent.select_one("div.bg-red-600.text-white")
        if banner and len(parent.select("table")) == 1:
            return re.sub(r"^\d+\)\s*", "", banner.get_text(" ", strip=True))
        if parent.name in {"body", "html"}:
            break
    heading = table.find_previous(["h2", "h3", "h4"])
    return heading.get_text(" ", strip=True) if heading else None


def parse_html(data, url, fetcher=None):
    soup = BeautifulSoup(data, "html.parser")
    site = urlsplit(url).hostname in {"pozarnisporty.cz", "www.pozarnisporty.cz"}
    warnings, notes, categories, audit = (
        [],
        ["Source: HTML; all result tables inspected."],
        [],
        [],
    )
    competition = competition_metadata(soup, warnings, site=site)
    document = soup.get_text("\n", strip=True)
    profile_failures = 0
    profile_used = 0
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        header_index = next(
            (
                i
                for i, row in enumerate(rows)
                if is_result_header(
                    column_map(
                        [
                            c.get_text(" ", strip=True)
                            for c in row.find_all(["th", "td"], recursive=False)
                        ]
                    )
                )
            ),
            None,
        )
        if header_index is None:
            # Unrecognized result-like tables must not silently disappear.
            if any("cas" in norm(row.get_text(" ")) for row in rows[:2]):
                raise ValueError("Unrecognized result-like table; adapter needed")
            continue
        headers = [
            c.get_text(" ", strip=True)
            for c in rows[header_index].find_all(["th", "td"], recursive=False)
        ]
        columns = column_map(headers)
        if not ("name" in columns or {"first_name", "last_name"} <= columns.keys()):
            raise ValueError("Result table has no identifiable participant column")
        name = table_label(table)
        if not name:
            raise ValueError("Result table category cannot be determined")
        if re.search(r"\b(finalovy beh|superfinale)\b", norm(name)):
            notes.append(f"Ignored separate final block: {name}")
            continue
        explicit = table.get("data-discipline", "")
        disc = category_discipline(name, explicit, document)
        if disc is None:
            warnings.append(f"{name}: unknown discipline")
        notes.append(
            f"{name}: columns {columns}; discipline={disc}; category from caption/heading/source banner."
        )
        if "try3" in columns or "try4" in columns:
            notes.append(f"{name}: try 3/4 columns ignored; first two retained.")
        results, reasons_count, source_count = [], 0, 0
        for row in rows[header_index + 1 :]:
            cells = row.find_all(["td", "th"], recursive=False)
            values = [c.get_text(" ", strip=True) for c in cells]
            if not cells or values == headers:
                continue
            if any("neobsazen" in norm(v) for v in values):
                continue
            if len(cells) != len(headers) or any(
                c.get("rowspan") or c.get("colspan") for c in cells
            ):
                raise ValueError(f"{name}: unsupported merged/wrapped row: {values!r}")
            source_count += 1

            def get(field):
                return values[columns[field]] if field in columns else None

            raw_name = (
                get("name") or f"{get('last_name') or ''} {get('first_name') or ''}"
            )
            context = f"{name} / {raw_name} / rank {get('rank')}"
            if "first_name" in columns and "last_name" in columns:
                first, last = get("first_name") or None, get("last_name") or None
            else:
                first, last = split_name(
                    raw_name,
                    warnings,
                    context,
                    surname_first=site
                    or table.get("data-name-order") == "surname-first",
                )
            start = get("start_number") or None
            if start is None and site:
                m = re.search(r"\((\d+)\)\s*$", raw_name)
                start = m[1] if m else None
            if {"team", "try1", "try2"} <= columns.keys():
                team, one, two, repaired = split_team_times(
                    get("team"), get("try1"), get("try2")
                )
                if repaired:
                    (
                        values[columns["team"]],
                        values[columns["try1"]],
                        values[columns["try2"]],
                    ) = team, one, two
                    notes.append(
                        f"{context}: unambiguous decimal-time suffix split from team into mapped empty try columns."
                    )
            attempts = [
                {
                    "try": i,
                    **parse_time(
                        get(f"try{i}"),
                        warnings,
                        context,
                        absent=f"try{i}" not in columns,
                    ),
                }
                for i in (1, 2)
            ]
            reasons_count += len(
                re.findall(r"(?:^|[,;]\s*)[12]\s*[-–—.]\s*", get("reason") or "")
            )
            assign_reasons(get("reason"), attempts, warnings, context)
            final = final_time(
                get("final"),
                attempts,
                warnings,
                context,
                placeholder=site,
                absent="final" not in columns,
            )
            year = birth_year(get("birth_year"))
            if year is None and fetcher and "name" in columns:
                link = cells[columns["name"]].find("a", href=True)
                if link:
                    profile = urljoin(url, link["href"])
                    if (
                        urlsplit(profile).hostname == urlsplit(url).hostname
                        and "/user/card/" in urlsplit(profile).path
                    ):
                        try:
                            content, _ = fetcher.get(profile)
                            year = profile_year(BeautifulSoup(content, "html.parser"))
                            profile_used += 1
                        except (OSError, ValueError) as exc:
                            profile_failures += 1
                            warnings.append(f"{context}: profile fetch failed: {exc}")
            result = {
                "start_number": start,
                "fscode": fscode(get("fscode"), warnings, context),
                "first_name": first,
                "last_name": last,
                "birth_year": year,
                "team": get("team") or None,
                "district": get("district") or None,
                "times": attempts,
                "final_time": final["time"],
                "final_status": final["status"],
                "rank": integer(get("rank")),
            }
            if result in results:
                notes.append(f"{name}: exact repeated source row removed: {raw_name}")
                source_count -= 1
                reasons_count -= sum("invalid_reason" in t for t in attempts)
                continue
            results.append(result)
        container = (table.parent.parent or table.parent).get_text(" ", strip=True)
        declared = re.search(
            r"(?:racers in the category|zavodniku v kategorii)\s*:\s*(\d+)",
            norm(container),
        )
        if declared and int(declared[1]) != source_count:
            raise ValueError(
                f"{name}: declared {declared[1]} participants but extracted {source_count}"
            )
        if any(c["name"] == name for c in categories):
            raise ValueError(
                f"Repeated category {name!r}; source adapter must distinguish/merge continuation explicitly"
            )
        for field in (
            "fscode",
            "birth_year",
            "district",
            "rank",
            "start_number",
            "team",
        ):
            missing = sum(r[field] is None for r in results)
            if missing:
                warnings.append(
                    f"{name}: unavailable {field} for {missing}/{len(results)} results"
                )
        for i in (1, 2):
            if f"try{i}" not in columns:
                warnings.append(f"{name}: try {i} column not published; status missing")
        if "final" not in columns:
            warnings.append(f"{name}: official final time column not published")
        categories.append({"name": name, "discipline": disc, "results": results})
        audit.append(
            {"category": name, "rows": source_count, "numbered_reasons": reasons_count}
        )
    if not categories:
        raise ValueError("No supported published result tables")
    # Check categories advertised by the site's filter, including unloaded sections.
    advertised = soup.select('input[wire\\:model^="selectedCategories."]')
    if advertised and len(advertised) != len(categories):
        raise ValueError(
            f"Only {len(categories)}/{len(advertised)} advertised categories loaded"
        )
    if soup.select('a[rel="next"], button[wire\\:click*="nextPage"]'):
        raise ValueError(
            "Pagination detected; source adapter must load all pages before publication"
        )
    notes += [
        f"Profiles inspected: {profile_used}; failed: {profile_failures}. Only birth year extracted.",
        "Official rank and final time copied; no ranking or best-time calculation.",
        "Numbered penalties assigned to corresponding tries; unnumbered reasons warned.",
        "On pozarnisporty.cz start number is the last numeric name suffix, never lane; region is not district.",
    ]
    competition["categories"] = categories
    return competition, notes, warnings, audit
