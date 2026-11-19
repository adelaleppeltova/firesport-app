"""Local, content-bound verification of OCR diagnostics."""

import csv
from pathlib import Path

from .youth_pdf_tables import Section, SourceRow, category_in, headline_kind

FIELDS = {
    "rank",
    "bib",
    "name",
    "team",
    "district",
    "fscode",
    "first",
    "second",
    "final",
}


def ocr_words(tsv):
    """Preserve OCR geometry and confidence without guessing damaged characters."""
    words = []
    for row in csv.reader(tsv.splitlines(), delimiter="\t"):
        if len(row) < 12 or row[0] != "5" or not row[11].strip():
            continue
        left, top, width, height = map(int, row[6:10])
        words.append(
            {
                "text": row[11],
                "bbox": [left, top, left + width, top + height],
                "confidence": float(row[10]),
            }
        )
    return words


def ocr_lines(words):
    """Group horizontal OCR tokens by their vertical midpoint for visual review."""
    lines = []
    for word in sorted(
        words, key=lambda token: (token["bbox"][1] + token["bbox"][3]) / 2
    ):
        _, top, _, bottom = word["bbox"]
        center = (top + bottom) / 2
        if not lines or center - lines[-1][0] > (bottom - top) * 0.5:
            lines.append((center, []))
        lines[-1][1].append(word)
    return [sorted(tokens, key=lambda token: token["bbox"][0]) for _, tokens in lines]


def checked_box(value, region):
    if (
        not isinstance(value, list)
        or len(value) != 4
        or not all(isinstance(x, (int, float)) for x in value)
        or not (
            region[0] <= value[0] < value[2] <= region[2]
            and region[1] <= value[1] < value[3] <= region[3]
        )
    ):
        raise ValueError(f"Souřadnice ověření jsou mimo oblast {tuple(region)}.")
    return tuple(value)


def checked_region(entry, region):
    """Rehydrate a human-checked region from the exact source PDF."""
    if not isinstance(entry, dict) or entry.get("verified") is not True:
        raise ValueError("Chybí potvrzení vizuální kontroly celé oblasti.")
    evidence = entry.get("metadata_lines", [])
    if not isinstance(evidence, list) or any(
        not isinstance(line, str) for line in evidence
    ):
        raise ValueError("Neplatné přepsané záhlaví OCR.")
    tables = entry.get("tables")
    if not isinstance(tables, list):
        raise ValueError("V ověření OCR chybí seznam tabulek.")
    output = []
    for table in tables:
        box = checked_box(table["bbox"], region)
        title, category = table["heading"], table["category"]
        if headline_kind(title) != "hurdles" or not category_in([category]):
            raise ValueError(
                "Přepsaná tabulka nemá jednoznačné záhlaví překážek a kategorie."
            )
        if "jednotliv" not in title.lower() and not table.get("individual_columns"):
            raise ValueError("Chybí důkaz o individuálních sloupcích tabulky.")
        order = table.get("name_order")
        if order not in {"surname-first", "given-first", None}:
            raise ValueError("Neplatné pořadí jména v ověření.")
        rows = []
        for row in table["rows"]:
            cells = row["cells"]
            if (
                not isinstance(cells, dict)
                or cells.keys() - FIELDS
                or any(
                    value is not None and not isinstance(value, str)
                    for value in cells.values()
                )
            ):
                raise ValueError("Neplatné zdrojové buňky v ověření OCR.")
            row_box = checked_box(row["bbox"], box)
            if rows and rows[-1].bbox[3] > row_box[1]:
                raise ValueError("Řádky ověření OCR se překrývají.")
            rows.append(
                SourceRow(
                    category,
                    cells,
                    None if order is None else order == "surname-first",
                    row_box,
                )
            )
        output.append(Section("hurdles", title, rows, box))
    return output, [(0, line) for line in evidence]


def read_review(path: Path | None):
    if path is None:
        return {}
    import json

    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, dict):
        raise ValueError("Ověření musí být slovník podle SHA-256 zdrojového PDF.")
    return entries
