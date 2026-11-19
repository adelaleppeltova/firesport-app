"""Read Pozarnisporty team standings with explicit final and attempt or stream columns."""

import re

from bs4 import BeautifulSoup

from .metadata import TEAM_TABLE_NOTE, category_discipline, competition_metadata, norm
from .participants import integer
from .times import final_time, parse_time


def _layout(row):
    headers = [
        norm(cell.get_text(" ", strip=True))
        for cell in row.find_all(["th", "td"], recursive=False)
    ]
    if headers[:3] != ["por.", "nazev", "vysledny cas"] or headers[-1:] != ["body"]:
        return None
    timing = headers[3:-1]
    if not timing or len(timing) % 2:
        return None
    times, notes = timing[::2], timing[1::2]
    count = len(times)
    if notes != [f"pozn. {i}" for i in range(1, count + 1)]:
        return None
    if count <= 4 and all(
        column in (f"cas {i}", f"cas {i} (p/n)") for i, column in enumerate(times, 1)
    ):
        return "attempts", count

    streams = [
        f"{side} proud - {i} (p/n)" for i in range(1, 5) for side in ("levy", "pravy")
    ]
    if times == streams[:count] and (count == 1 or count in (2, 4, 6, 8)):
        return "streams", count
    return None


def _time(text):
    text = re.sub(r"\s+\(([PN])\)$", r" \1", text, flags=re.I)
    if re.fullmatch(r"-+|0+(?::0+){0,2}(?:[.,]0+)?(?:-| [PN])?", text):
        return "-"
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2}[.,]\d{1,3})( [PN])?", text)
    if match and int(match[2]) < 60:
        return f"{int(match[1]) * 60 + int(match[2])}:{match[3]}{match[4] or ''}"
    return text


def _attempts(values, count, context, warnings):
    attempts, reasons = [], 0
    for number in (1, 2):
        time_col = 2 * number + 1
        text = _time(values[time_col]) if number <= count else None
        attempt = {
            "try": number,
            **parse_time(text, warnings, context, absent=number > count),
        }
        note = values[time_col + 1] if number <= count else ""
        if note:
            if re.match(r"^N\s*[-–:]", note, re.I):
                attempt["invalid_reason"] = note
                reasons += 1
                if attempt["status"] != "invalid":
                    warnings.append(
                        f"{context}: penalty on {attempt['status']} try {number}: {note}"
                    )
            else:
                warnings.append(
                    f"{context}: unclassified note for try {number}: {note}"
                )
        attempts.append(attempt)
    for number in range(3, count + 1):
        if note := values[2 * number + 2]:
            warnings.append(f"{context}: ignored note for try {number}: {note}")
    return attempts, reasons


def has_compact_team_table(soup):
    return any(table.tr and _layout(table.tr) for table in soup.find_all("table"))


def parse_team_html(data):
    soup = BeautifulSoup(data, "html.parser")
    notes = [TEAM_TABLE_NOTE]
    warnings, categories, audit = [], [], []
    competition = competition_metadata(soup, warnings, site=True)
    has_performance = False
    for table in soup.find_all("table"):
        if table.find_parent(id="description"):
            continue
        rows = table.find_all("tr")
        layout = _layout(rows[0]) if rows else None
        if layout is None:
            raise ValueError(
                "Mixed or unsupported team table; inspect all result sections"
            )
        kind, count = layout
        card = table.parent.parent
        label = card.select_one(":scope > div.font-semibold.text-red-600")
        name = label.get_text(" ", strip=True) if label else None
        if not name or any(c["name"] == name for c in categories):
            raise ValueError("Missing or repeated team category label")
        if re.search(r"\b(finalovy beh|superfinale)\b", norm(name)):
            notes.append(f"Ignored separate final block: {name}")
            continue
        disc = (
            "PU"
            if kind == "streams"
            else category_discipline(name, "", competition["name"] or "")
        )
        if disc is None:
            warnings.append(f"{name}: unknown discipline")
        if kind == "streams":
            notes.append(
                f"{name}: left/right stream times are splits; no official overall attempt times published."
            )
        elif count > 2:
            notes.append(f"{name}: try 3/4 columns ignored; first two retained.")
        results, reasons, source_count, unpublished = [], 0, 0, 0
        for row in rows[1:]:
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
                and cells[1].get("colspan") == "11"
                and re.fullmatch(r"showMembers\[\d+\]", row.get("x-show", ""))
            ):
                continue
            if len(values) != count * 2 + 4 or any(
                cell.get("rowspan") or cell.get("colspan") for cell in cells
            ):
                raise ValueError(
                    f"{name}: unsupported nonempty team detail or wrapped row"
                )
            if not values[1] or "neobsazen" in norm(values[1]):
                continue
            rank = integer(values[0])
            # The final is column 2. Remaining time columns are 3, 5, 7, 9.
            time_cells = [
                _time(values[2]),
                *(_time(values[2 * i + 1]) for i in range(1, count + 1)),
            ]
            if (
                rank is None
                and all(value in ("", "-") for value in time_cells)
                and not any(values[2 * i + 2] for i in range(1, count + 1))
            ):
                unpublished += 1
                continue
            has_performance |= any(
                value.upper() in {"NP", "DNS", "DNF", "DSQ"}
                or parse_time(value.removesuffix(" N"), [])["time"] is not None
                for value in time_cells
            ) or any(
                re.match(r"^N\s*[-–:]", values[2 * i + 2], re.I)
                for i in range(1, count + 1)
            )
            source_count += 1
            label = values[1]
            context = f"{name} / {label}"
            if kind == "streams":
                attempts = [
                    {"try": number, "time": None, "status": "missing"}
                    for number in (1, 2)
                ]
                for slot in range(1, count + 1):
                    if note := values[2 * slot + 2]:
                        side = "left" if slot % 2 else "right"
                        warnings.append(
                            f"{context}: {side} stream note for try {(slot + 1) // 2}: {note}"
                        )
            else:
                attempts, assigned = _attempts(values, count, context, warnings)
                reasons += assigned
            if kind == "streams":
                final = parse_time(_time(values[2]), warnings, context)
                if final["status"] != "valid":
                    final["time"] = None
            else:
                final = final_time(
                    _time(values[2]), attempts, warnings, context, placeholder=True
                )
            results.append(
                {
                    "start_number": None,
                    "fscode": None,
                    "first_name": None,
                    "last_name": None,
                    "birth_year": None,
                    "team": label,
                    "district": None,
                    "times": attempts,
                    "rank": rank,
                    "final_time": final["time"],
                    "final_status": final["status"],
                }
            )
        if unpublished:
            notes.append(f"{name}: {unpublished} unscored registrations skipped.")
        categories.append({"name": name, "discipline": disc, "results": results})
        audit.append(
            {"category": name, "rows": source_count, "numbered_reasons": reasons}
        )
    advertised = soup.select('input[wire\\:model^="selectedCategories."]')
    if not categories or (advertised and len(advertised) != len(categories)):
        raise ValueError("Team category list is empty or incomplete")
    if soup.select('a[rel="next"], button[wire\\:click*="nextPage"]'):
        raise ValueError("Pagination detected in team results")
    published = [row for category in categories for row in category["results"]]
    ranked = [row for row in published if row["rank"] is not None]
    if len(ranked) >= 3 and all(
        row["final_time"] is None
        and row["times"][0]["time"] == row["rank"] * 60
        and row["times"][1]["time"] is None
        for row in ranked
    ):
        raise ValueError(
            "Team times encode rank as whole minutes; source confirmation required"
        )
    if not has_performance:
        raise ValueError("No published compact team results")
    competition["categories"] = categories
    return competition, notes, warnings, audit
