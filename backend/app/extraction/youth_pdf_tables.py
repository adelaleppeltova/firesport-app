"""Geometric adapters for published individual youth 100 m hurdle tables."""

import re
from dataclasses import dataclass

from .metadata import norm
from .participants import integer

HURDLES = re.compile(r"\b100\s*m\s+(?:s\s+)?prek(?:azkami|azek|\.)")
OTHER = re.compile(
    r"\b(?:php|tafeta|stafeta|utok|vez|60\s*m|finalovy beh|superfinale)\b"
)
YOUTH = re.compile(r"\b(?:dorci|dorky|dorostenci|dorostenky)\b")
AGE = re.compile(r"\b(?:mladsi|stredni|st\s*edni|starsi)\b")


@dataclass
class SourceRow:
    category: str
    cells: dict
    surname_first: bool | None
    bbox: tuple
    source_category: str | None = None


@dataclass
class Section:
    kind: str
    heading: str
    rows: list
    bbox: tuple


def clean(value):
    return " ".join((value or "").split())


def ordered_lines(page):
    """Join text sharing a baseline, retaining coordinates and rotation."""
    lines = []
    for block in page.get_text("dict", flags=3)["blocks"]:
        for line in block.get("lines", []):
            value = clean("".join(span["text"] for span in line["spans"]))
            if value:
                lines.append((line["bbox"], value, abs(line["dir"][1]) > 0.9))
    return sorted(lines, key=lambda item: (item[0][1], item[0][0]))


def horizontal_lines(lines):
    grouped = []
    for (x, y, _, _), value, rotated in lines:
        if rotated:
            continue
        if grouped and abs(y - grouped[-1][0]) <= 2:
            grouped[-1][1].append((x, value))
        else:
            grouped.append((y, [(x, value)]))
    return [(y, " ".join(value for _, value in sorted(parts))) for y, parts in grouped]


def in_box(lines, box, rotated=False):
    x, y, right, bottom = box
    return [
        (bounds, value)
        for bounds, value, vertical in lines
        if vertical == rotated
        and x <= (bounds[0] + bounds[2]) / 2 < right
        and y <= (bounds[1] + bounds[3]) / 2 < bottom
    ]


def category_in(values):
    for raw in values:
        label = clean(raw)
        key = norm(label).replace("_", " ").replace("\u00ad", "-")
        if YOUTH.search(key) and re.fullmatch(
            r"(?:dorci|dorky|dorostenci|dorostenky|mladsi|stredni|st edni|starsi|jednotlivci|druzstva|[ –-])+",
            key,
        ):
            return label
    return None


def headline_kind(title):
    key = norm(title)
    if "php" in key and not HURDLES.search(key):
        return "php"
    if OTHER.search(key):
        return "other"
    if HURDLES.search(key):
        return "team" if "poradi druzstev" in key else "hurdles"
    return None


def heading_above(lines, table, top):
    x, y, right, _ = table.bbox
    # Discipline labels belong to this table's horizontal region and preceding gap.
    matches = [
        (value, headline_kind(value))
        for _, value in in_box(lines, (x - 20, top, right + 20, y))
        if headline_kind(value)
    ]
    return matches[-1] if matches else ("", None)


def direct_columns(row):
    keys = {}
    for index, raw in enumerate(row):
        key = norm(raw).rstrip(".")
        if key in {"poradi", "umisteni", "por"}:
            keys["rank"] = index
        elif key in {"start. cislo", "startovni cislo", "st.c", "st. c"}:
            keys["bib"] = index
        elif key in {
            "jmeno",
            "jmeno a prijmeni",
            "prijmeni a jmeno",
            "prijmeni, jmeno",
        }:
            keys["name"] = index
        elif key in {"krestni jmeno", "krestni jmena"}:
            keys["first_name"] = index
        elif key == "prijmeni":
            keys["last_name"] = index
        elif key in {"sdh", "kolektiv", "druzstvo"}:
            keys["team"] = index
        elif key == "okres":
            keys["district"] = index
        elif key in {"fscode", "fs code"}:
            keys["fscode"] = index
        elif re.fullmatch(r"(?:cas )?(?:1\.?|i\.?) (?:pokus[u]?|kolo)", key):
            keys["first"] = index
        elif re.fullmatch(r"(?:cas )?(?:2\.?|ii\.?) (?:pokus[u]?|kolo)", key):
            keys["second"] = index
        elif key in {"vysledny cas", "finalni cas"}:
            keys["final"] = index
    if "last_name" in keys and "first_name" not in keys and "name" in keys:
        if norm(row[keys["name"]]) == "jmeno":
            keys["first_name"] = keys.pop("name")
    has_name = "name" in keys or {"first_name", "last_name"} <= keys.keys()
    return keys if has_name and {"rank", "first", "second", "final"} <= keys.keys() else None


def crop_text(page, box):
    return clean(page.crop(box).extract_text(x_tolerance=1) or "")


def header_column_bounds(row, mapping):
    return {
        key: (row.cells[index][0], row.cells[index][2])
        for key, index in mapping.items()
        if row.cells[index] is not None
    }


def read_columns(page, y0, y1, bounds):
    values = {}
    for key, (x0, x1) in bounds.items():
        text = (page.crop((x0, y0, x1, y1)).extract_text(x_tolerance=1) or "").strip()
        values[key] = text if key in {"name", "first_name", "last_name"} else clean(text)
    if "name" in values:
        values["source_full_name"] = values["name"]
    elif {"first_name", "last_name"} <= values.keys():
        keys = sorted(("first_name", "last_name"), key=lambda key: bounds[key][0])
        values["source_full_name"] = " ".join(values[key] for key in keys if values[key])
    return values


def read_direct(page, table, start, bounds, category, surname_first):
    rows = []
    last_bottom = 0
    for row in table.rows[start:]:
        x, top, right, bottom = row.bbox
        if top < last_bottom - 1:
            continue  # a nested partial cell in a full-height athlete row
        last_bottom = bottom
        if right - x < 0.8 * (table.bbox[2] - table.bbox[0]):
            continue
        values = read_columns(page, top, bottom, bounds)
        if any(values.values()):
            rows.append(SourceRow(category, values, surname_first, row.bbox))
    return rows


def rotated_label(lines, box):
    return " ".join(
        value
        for _, value in sorted(in_box(lines, box, True), key=lambda item: item[0][0])
    )


def vertical_summary(page, lines, table, cells, preamble):
    """Read only the explicitly separated hurdles pair, with PHP as a boundary."""
    for i, row in enumerate(table.rows[:4]):
        labels = [
            rotated_label(lines, (box[0], table.bbox[1], box[2], box[3])) if box else ""
            for box in row.cells
        ]
        targets = [
            j for j, label in enumerate(labels) if headline_kind(label) == "hurdles"
        ]
        php = [j for j, label in enumerate(labels) if headline_kind(label) == "php"]
        if len(targets) == len(php) == 1 and targets[0] < php[0]:
            break
    else:
        return None
    target, php = targets[0], php[0]
    split_rank = php == target + 2
    rank_label = norm(labels[target + 1]) if php == target + 2 else ""
    if not any(norm(label).replace(" ", "") == "startovnicislo" for label in labels):
        return None  # Rank-only multi-event standings.
    attempts_labelled = any(
        norm(row[target]) == "1.pokus" for row in cells[i + 1 : i + 3]
    )
    if not attempts_labelled and rank_label != "body za umisteni":
        return None  # No individual timing columns.
    if not split_rank or target not in (3, 4):
        return Section(
            "unresolved", "Unsupported vertical Hurdles/PHP bands", [], table.bbox
        )
    category = category_in(
        [cell for line in cells[: i + 1] for cell in line] + preamble
    )
    if not category and table.rows[i].cells[1]:
        label = " ".join(value for _, value in in_box(lines, table.rows[i].cells[1]))
        category = category_in([label])
    if not category:
        return Section(
            "unresolved", "Missing category in vertical table", [], table.bbox
        )

    source_category = None
    if norm(category) in {"dorci", "dorky"}:
        for line in preamble:
            match = re.search(r"\bKOLO DOROSTU (MLADŠÍ|STŘEDNÍ|STARŠÍ)\b", line, re.I)
            if match:
                source_category = category
                category = f"{category} – {match[1]}"
                break
        if source_category is None:
            return Section(
                "unresolved",
                "Neurčená věková skupina v tabulce jednotlivců",
                [],
                table.bbox,
            )
    result = []
    last_bottom = 0
    header_pairs = [
        source for source in cells[i + 1 : i + 3] if norm(source[target]) == "1.pokus"
    ]
    actual_rank = bool(header_pairs and norm(header_pairs[0][target + 1]) == "p.")
    if rank_label == "body za umisteni":
        actual_rank = False
    for j, (row, values) in enumerate(zip(table.rows[i + 1 :], cells[i + 1 :]), i + 1):
        if row.bbox[1] < last_bottom - 1 or not integer(values[0]):
            continue
        last_bottom = row.bbox[3]
        values = [clean(value) for value in values]
        timing_box = row.cells[target]
        if timing_box is None:
            return Section("unresolved", "Missing hurdles attempt cell", [], table.bbox)
        next_row = table.rows[j + 1] if j + 1 < len(cells) else None
        second_box = next_row.cells[target] if next_row else None
        if second_box and timing_box[1] < second_box[1] < row.bbox[3] - 1:
            attempts = [crop_text(page, timing_box), crop_text(page, second_box)]
        else:
            # Some PDFs draw dotted separators that the table finder does not join.
            full_box = (timing_box[0], row.bbox[1], timing_box[2], row.bbox[3])
            upper = (full_box[1] + full_box[3]) / 2
            attempts = [
                crop_text(page, (full_box[0], full_box[1], full_box[2], upper)),
                crop_text(page, (full_box[0], upper, full_box[2], full_box[3])),
            ]
        if not any(values[1:target]) and not any(attempts):
            data = {"bib": values[0], "name": ""}
        else:
            data = {
                "bib": values[0],
                "name": values[1],
                "team": values[2],
                "district": values[3] if target == 4 else None,
                "first": attempts[0],
                "second": attempts[1],
                "rank": values[target + 1] if actual_rank else None,
            }
        # Only this variation publishes an explicit name-order label.
        order = True if rank_label == "body za umisteni" else None
        result.append(SourceRow(category, data, order, row.bbox, source_category))
    return Section("hurdles", labels[target], result, table.bbox)


def horizontal_summary(page, lines, table, cells):
    """Isolate independently labelled hurdle columns in two multi-discipline layouts."""
    rows = []
    mapping = None
    category = category_in(cells[0])
    heading = ""
    for line_index, (row, values) in enumerate(zip(table.rows, cells)):
        labels = [norm(value) for value in values]
        if "100m s php" in labels and "100m" in labels and line_index + 1 < len(cells):
            php, target = labels.index("100m s php"), labels.index("100m")
            header = [norm(value) for value in cells[line_index + 1]]
            if (
                target == php + 4
                and header[:5]
                == ["st.c.", "prijmeni a jmeno", "osh", "druzstvo/sdh", "kategorie"]
                and header[php:target]
                == header[target : target + 4]
                == ["cas", "cas", "vysledny cas", "poradi"]
            ):
                mapping = {
                    "bib": 0,
                    "name": 1,
                    "category": 4,
                    "first": target,
                    "second": target + 1,
                    "final": target + 2,
                    "rank": target + 3,
                }
                # These two published headers conflict with the cell contents. Preserve
                # the cells in the audit and leave both fields for manual verification.
                mapping["source_affiliation"] = 2
                mapping["source_district"] = 3
                heading = clean(values[target])
        if (
            "dvojboj" in labels
            and "beh na 100m" in labels
            and line_index + 1 < len(cells)
        ):
            target = labels.index("beh na 100m")
            next_row = table.rows[line_index + 1]
            header = [
                norm((rotated_label(lines, box) if box else "") or value)
                for box, value in zip(
                    next_row.cells, cells[line_index + 1], strict=True
                )
            ]
            if (
                category
                and labels.index("dvojboj") == target - 2
                and header[:4]
                == ["start. cislo", "jmeno a prijmeni", "soutezni druzstvo", "okres"]
                and header[target : target + 2] == ["cas", "poradi"]
            ):
                mapping = {
                    "bib": 0,
                    "name": 1,
                    "team": 2,
                    "district": 3,
                    "final": target,
                    "rank": target + 1,
                }
                heading = clean(values[target])
        bib = integer(values[0])
        overflowing_bib = None
        if mapping and "category" in mapping and not bib:
            overflowing_bib = re.fullmatch(r"(\d+)([^\W\d_]+)", clean(values[0]))
        if mapping and (bib is not None or overflowing_bib):
            data = {key: clean(values[col]) for key, col in mapping.items()}
            data["source_full_name"] = (values[mapping["name"]] or "").strip()
            label = data.pop("category", category)
            if "source_affiliation" in data:
                # Flag text crossing the nominal name boundary for review.
                edge = row.cells[1][2]
                chars = page.crop(
                    (row.bbox[0], row.bbox[1], row.bbox[2], row.bbox[3])
                ).chars
                if any(c["x0"] < edge < c["x1"] and c["text"].strip() for c in chars):
                    data["name_overflow"] = True
                if overflowing_bib:
                    data["bib"] = overflowing_bib[1]
                    data["name"] = overflowing_bib[2] + data["name"]
                    data["source_full_name"] = overflowing_bib[2] + data["source_full_name"]
                    data["name_overflow"] = True
                data["surname_first"] = True
            rows.append(
                SourceRow(label, data, data.pop("surname_first", False), row.bbox)
            )
    return Section("hurdles", heading, rows, table.bbox) if mapping else None


def extract_sections(pdf_page, page, previous):
    """Return classified sections and carry only a proven leading continuation."""
    lines = ordered_lines(pdf_page)
    sections = []
    logical_lines = horizontal_lines(lines)
    prior_bottom = 0
    for table in page.find_tables():
        if len(table.columns) < 4:
            continue
        cells = table.extract(x_tolerance=1)
        top = table.bbox[1]
        preamble = [
            value
            for _, value in in_box(
                lines,
                (max(0, table.bbox[0] - 20), prior_bottom, table.bbox[2] + 20, top),
            )
        ]
        heading, kind = heading_above(lines, table, prior_bottom)
        prior_bottom = table.bbox[3]
        direct = next(
            (
                (i, mapped)
                for i, row in enumerate(cells[:4])
                if (mapped := direct_columns(row))
            ),
            None,
        )
        if direct:
            if kind in {"other", "php", "team"}:
                sections.append(
                    Section(kind, heading, cells[direct[0] + 1 :], table.bbox)
                )
                previous = None
                continue
            if kind != "hurdles":
                sections.append(
                    Section(
                        "unresolved", "Unknown individual discipline", [], table.bbox
                    )
                )
                previous = None
                continue
            index, mapping = direct
            header = cells[index]
            category = category_in(
                [
                    value
                    for _, value in in_box(
                        lines,
                        (table.bbox[0], top, table.bbox[2], table.rows[index].bbox[1]),
                    )
                ]
                + [cell for row in cells[:index] for cell in row]
                + preamble
            )
            if not category and " - " in heading:
                pieces = heading.split(" - ")
                # For headings with the age attached to "jednotlivci", preserve source
                # gender and age label in their published order.
                category = category_in(pieces)
                if category and len(pieces) > 2 and AGE.search(norm(pieces[-1])):
                    category = f"{category} - {pieces[-1]}"
            if not category:
                sections.append(Section("unresolved", heading, [], table.bbox))
                previous = None
                continue
            bounds = header_column_bounds(table.rows[index], mapping)
            category_key = norm(category)
            order = (
                False
                if norm(header[mapping["name"]]) == "jmeno a prijmeni"
                else True
                if "bib" in mapping
                else None
            )
            rows = read_direct(page, table, index + 1, bounds, category, order)
            section = Section("hurdles", heading, rows, table.bbox)
            if "druzstva" in norm(heading) or (category_key in {"dorci", "dorky"}):
                section.kind = "team_individuals"
            sections.append(section)
            if rows:
                previous = (section, bounds, category, order) if rows else None
            continue
        summary = vertical_summary(page, lines, table, cells, preamble)
        if summary is None:
            summary = horizontal_summary(page, lines, table, cells)
        if summary:
            sections.append(summary)
        elif (
            not sections
            and previous
            and not heading
            and all(integer(row[0]) is not None for row in cells if any(row))
        ):
            section, bounds, category, order = previous
            first_row = table.rows[0]
            first_cells = first_row.cells
            old_left = bounds["rank"][0]
            old_right = bounds["final"][1]
            if (
                abs(table.bbox[0] - old_left) < 3
                and abs(table.bbox[2] - old_right) < 3
                and abs(first_cells[0][2] - bounds["rank"][1]) < 3
                and all(
                    integer(label) is not None or re.match(r"^\d+[.]?\s+\d+\s", label)
                    for y, label in logical_lines
                    if y < top
                )
            ):
                rows = read_direct(page, table, 0, bounds, category, order)
                # A page break can leave the first row without its upper rule.
                row_height = first_row.bbox[3] - first_row.bbox[1]
                extra_box = (old_left, max(0, top - row_height - 2), old_right, top)
                extra = read_columns(page, extra_box[1], extra_box[3], bounds)
                if any(extra.values()):
                    rows.insert(0, SourceRow(category, extra, order, extra_box))
                last = integer(section.rows[-1].cells.get("rank"))
                first = integer(rows[0].cells.get("rank")) if rows else None
                if last is not None and first is not None and first > last:
                    sections.append(
                        Section(section.kind, section.heading, rows, table.bbox)
                    )
                    previous = (sections[-1], bounds, category, order)
                    continue
            sections.append(
                Section("unresolved", "Unproven continuation", [], table.bbox)
            )
        else:
            # These are audit counts for clearly classified tables only.
            excluded = kind or "other"
            if kind == "hurdles":  # Hurdle summary with no individual rows
                excluded = (
                    "team"
                    if any(
                        {"kolektiv", "soucet"} <= {norm(value) for value in row}
                        for row in cells[:2]
                    )
                    else "unresolved"
                )
            sections.append(
                Section(
                    excluded,
                    heading,
                    cells if excluded != "unresolved" else [],
                    table.bbox,
                )
            )
        previous = None
    return sections, previous, logical_lines
