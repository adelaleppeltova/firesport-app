"""Read the official team standings from Pozarnisporty checkpoint races."""

import re

from bs4 import BeautifulSoup

from .metadata import competition_metadata, norm
from .participants import integer

HEADERS = [
    "poradi",
    "tym",
    "cas startu",
    "cas cile",
    "cisty cas",
    "cekaci cas",
    "vysledny cas",
]
INVALID_TIMES = {"", "-", "NP", "DNS", "DNF", "DSQ", "00:00:00"}


def _headers(table):
    return (
        [norm(cell.get_text(" ", strip=True)) for cell in table.tr.find_all("th")]
        if table.tr
        else []
    )


def _is_checkpoint_table(headers):
    return (
        headers[:7] == HEADERS
        and headers[-1:] == ["ksum"]
        and len(headers) > 8
        and headers[7:-1] == [f"k{i}" for i in range(1, len(headers) - 7)]
    )


def has_checkpoint_table(soup):
    return any(
        _is_checkpoint_table(_headers(table)) for table in soup.find_all("table")
    )


def _official_time(value):
    if value.upper() in INVALID_TIMES:
        return None
    match = re.fullmatch(r"(\d+):([0-5]\d):([0-5]\d)", value)
    if not match:
        raise ValueError(f"Unrecognized checkpoint finish time: {value!r}")
    hours, minutes, seconds = map(int, match.groups())
    return 3600 * hours + 60 * minutes + seconds


def parse_checkpoint_html(data):
    soup = BeautifulSoup(data, "html.parser")
    warnings = []
    competition = competition_metadata(soup, warnings, site=True)
    notes = [
        "Source: HTML team checkpoint standings. Start/finish clocks, splits, checkpoint scores and team rosters are not attempts."
    ]
    audit, categories = [], []
    measured = False
    for table in soup.find_all("table"):
        if table.find_parent(id="description"):
            continue
        headers = _headers(table)
        if not _is_checkpoint_table(headers):
            raise ValueError(
                "Mixed or unsupported checkpoint table; inspect all result sections"
            )
        label = table.parent.parent.select_one(":scope > div.font-bold")
        name = label.get_text(" ", strip=True) if label else None
        if not name or any(c["name"] == name for c in categories):
            raise ValueError("Missing or repeated checkpoint category label")
        if re.search(r"\b(finalovy beh|superfinale)\b", norm(name)):
            notes.append(f"Ignored separate final block: {name}")
            continue
        results = []
        for row in table.find_all("tr")[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            values = [cell.get_text(" ", strip=True) for cell in cells]
            if not any(values) or (
                len(values) == 1
                and norm(values[0]) == "v kategorii neni nikdo prihlasen"
            ):
                continue
            if (
                len(cells) == 2
                and not values[0]
                and cells[1].get("colspan") == "15"
                and re.fullmatch(r"showMembers\[\d+\]", row.get("x-show", ""))
            ):
                continue
            if len(cells) != len(headers) or any(
                c.get("colspan") or c.get("rowspan") for c in cells
            ):
                raise ValueError(f"{name}: unsupported checkpoint result row")
            rank, team = integer(values[0]), values[1]
            if not team or "neobsazen" in norm(team):
                continue
            elapsed = _official_time(values[6])
            measured |= elapsed is not None
            if (
                elapsed is None
                and rank is None
                and values[6].upper() not in {"NP", "DNS", "DNF", "DSQ"}
            ):
                continue
            results.append(
                {
                    "start_number": None,
                    "fscode": None,
                    "first_name": None,
                    "last_name": None,
                    "birth_year": None,
                    "team": team,
                    "district": None,
                    "times": [
                        {"try": i, "time": None, "status": "missing"} for i in (1, 2)
                    ],
                    "final_time": elapsed,
                    "final_status": "valid" if elapsed is not None else "invalid",
                    "rank": rank,
                }
            )
        warnings.append(
            f"{name}: team checkpoint discipline is outside the supported discipline enum"
        )
        categories.append({"name": name, "discipline": None, "results": results})
        audit.append({"category": name, "rows": len(results), "numbered_reasons": 0})
    if not measured:
        raise ValueError("No measured checkpoint results published")
    advertised = soup.select('input[wire\\:model^="selectedCategories."]')
    if advertised and len(advertised) != len(categories):
        raise ValueError("Checkpoint category list is incomplete")
    if soup.select('a[rel="next"], button[wire\\:click*="nextPage"]'):
        raise ValueError("Pagination detected in checkpoint results")
    competition["categories"] = categories
    return competition, notes, warnings, audit
