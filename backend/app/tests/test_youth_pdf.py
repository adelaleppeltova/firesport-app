"""Offline fixtures model the independent PDF result layouts without athlete data."""

import hashlib
import json
import os
from pathlib import Path

import pymupdf
import pytest

from app.extraction import youth_pdf
from app.extraction.youth_pdf_review import checked_region, ocr_words
from app.extraction.youth_pdf_tables import SourceRow, headline_kind

METADATA = "Krajská soutěž dorostu 13. 6. 2026 Písek"
HURDLES = "Běh na 100m s přek. - Pořadí jednotlivců"
PHP = "Běh na 100 m s PHP - Jednotlivci - Pořadí"
COLUMNS = [
    "Pořadí",
    "Start. číslo",
    "Jméno",
    "SDH",
    "I. pokusu",
    "II. pokusu",
    "Výsledný čas",
]
ATHLETE = ["1", "4", "55 - Černá Alena", "Dolní Dlouhá Ves", "18,58", "NP", "18,58"]
TSV = "5\t1\t1\t1\t1\t1\t20\t25\t40\t10\t35.2\t1O,3S\n"


def font_path():
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if Path(path).is_file():
            return path
    pytest.skip("A Unicode font is required to draw the synthetic fixture")


def write_text(page, x, y, text, *, rotate=0):
    page.insert_text(
        (x, y),
        text,
        fontname="fixture",
        fontfile=font_path(),
        fontsize=9,
        rotate=rotate,
    )


def grid(page, top, rows):
    columns = [30, 78, 140, 275, 395, 465, 535, 620]
    for i in range(len(rows) + 1):
        y = top + i * 23
        page.draw_line((columns[0], y), (columns[-1], y))
    for x in columns:
        page.draw_line((x, top), (x, top + len(rows) * 23))
    for i, row in enumerate(rows):
        for x, item in zip(columns, row):
            if item:
                write_text(page, x + 3, top + 15 + i * 23, item)


@pytest.fixture
def text_pdf(tmp_path):
    path = tmp_path / "results.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=655, height=500)
        write_text(page, 30, 30, METADATA)
        write_text(page, 30, 60, "Jihočeský kraj")
        write_text(page, 30, 90, PHP)
        grid(
            page,
            103,
            [
                ["Dorky mladší"],
                COLUMNS,
                [
                    "1",
                    "4",
                    "Černá Alena",
                    "Dolní Dlouhá Ves",
                    "16,12",
                    "16,04",
                    "16,04",
                ],
            ],
        )
        write_text(page, 30, 205, HURDLES)
        grid(page, 218, [["Dorky mladší"], COLUMNS, ATHLETE])
        page = pdf.new_page(width=655, height=500)
        grid(
            page,
            30,
            [
                ["3", "9", "Černá Alena", "Jiný klub", "20,15", "21,23", "21,23"],
                ["4", "6", "NESTARTOVALO", "Miletín", "DNS", "DNS", "DNS"],
            ],
        )
        pdf.save(path)
    return path


def test_direct_tables_and_continuation(text_pdf, tmp_path):
    result, audit, report = youth_pdf.convert(text_pdf, tmp_path / "review")
    assert report["errors"] == []
    assert result["competition"]["date"] == "2026-06-13"
    assert result["competition"]["place"] == "Písek"
    assert report["region"] == "Jihočeský"
    (category,) = result["competition"]["categories"]
    assert (category["discipline"], category["name"]) == ("100m", "Dorky mladší")
    first, second = category["results"]
    assert (first["first_name"], first["last_name"], first["team"]) == (
        "Alena",
        "Černá",
        "Dolní Dlouhá Ves",
    )
    assert first["start_number"] == "4" and first["fscode"] is None
    assert first["times"] == [
        {"try": 1, "time": 18.58, "status": "valid"},
        {"try": 2, "time": None, "status": "invalid", "invalid_reason": "NP"},
    ]
    assert second["rank"] == 3 and second["final_time"] == 21.23
    assert audit[0]["rows"] == 2
    assert report["excluded"] == {"php": 1, "placeholder": 1}
    assert report["rows"][0]["source_identifier"] == "55"
    assert [row["page"] for row in report["rows"]] == [1, 2, 2]
    assert any("minima pokusů" in warning for warning in report["warnings"])


def test_vertical_attempt_columns_exclude_php_and_overall(tmp_path):
    path = tmp_path / "vertical.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=655, height=500)
        write_text(page, 30, 30, METADATA)
        write_text(page, 30, 50, "Dorky mladší")
        columns = [30, 65, 175, 290, 330, 390, 440, 500, 540, 575, 620]
        for x in columns:
            top = 189 if x in (390, 500) else 70
            page.draw_line((x, top), (x, 270))
        for y in (70, 225, 270):
            page.draw_line((30, y), (620, y))
        page.draw_line((330, 189), (540, 189))
        for y in (208, 247):
            for a, b in ((330, 390), (440, 500)):
                page.draw_line((a, y), (b, y))
        write_text(page, 50, 175, "startovní číslo", rotate=90)
        write_text(page, 354, 175, "Běh na 100 m", rotate=90)
        write_text(page, 368, 175, "s překážkami", rotate=90)
        write_text(page, 463, 175, "Běh na 100 m", rotate=90)
        write_text(page, 478, 175, "s PHP", rotate=90)
        for x in (335, 445):
            write_text(page, x, 201, "1.pokus")
            write_text(page, x, 220, "2.pokus")
        for x in (402, 510):
            write_text(page, x, 211, "P.")
        for x, value in zip(
            columns,
            [
                "7",
                "Černá Alena",
                "SDH Horní Ves",
                "PB",
                "20,40",
                "5",
                "16,22",
                "1",
                "6",
                "2",
            ],
        ):
            write_text(page, x + 3, 242, value)
        write_text(page, 335, 263, "NP")
        write_text(page, 445, 263, "16,11")
        pdf.save(path)

    review = {
        hashlib.sha256(path.read_bytes()).hexdigest(): {"name_order": "surname-first"}
    }
    result, _, report = youth_pdf.convert(path, tmp_path / "review", review)
    assert report["errors"] == []
    (record,) = result["competition"]["categories"][0]["results"]
    assert record["rank"] == 5
    assert [t["time"] for t in record["times"]] == [20.4, None]
    assert record["final_time"] is None and record["final_status"] == "missing"


@pytest.mark.parametrize("mixed", [False, True])
def test_scanned_and_mixed_pages_require_exact_review(
    text_pdf, tmp_path, monkeypatch, mixed
):
    path = tmp_path / "raster.pdf"
    with pymupdf.open(text_pdf) as source, pymupdf.open() as pdf:
        pix = source[0].get_pixmap()
        page = pdf.new_page(width=655, height=650 if mixed else 500)
        area = pymupdf.Rect(0, 150 if mixed else 0, 655, page.rect.height)
        page.insert_image(area, pixmap=pix)
        if mixed:
            write_text(page, 30, 40, METADATA)
            write_text(page, 30, 70, "Textová hlavička nad naskenovanou tabulkou")
        pdf.save(path)

    calls = []

    def recognize(_page, _output, key, *, clip, sparse):
        calls.append((key, clip, sparse))
        return TSV

    monkeypatch.setattr(youth_pdf, "recognize", recognize)
    output, _, report = youth_pdf.convert(path, tmp_path / "ocr")
    assert output is None and calls
    (ocr,) = report["pages"][0]["ocr"]
    assert ocr["status"] == "requires_review" and ocr["words"] == 1
    assert ocr["key"] == ("1-region-1" if mixed else "1")
    assert ocr_words(TSV)[0] == {
        "text": "1O,3S",
        "bbox": [20, 25, 60, 35],
        "confidence": 35.2,
    }

    top = area.y0
    reviewed = {
        "verified": True,
        "metadata_lines": [METADATA],
        "tables": [
            {
                "bbox": [20, top + 5, 635, top + 100],
                "heading": HURDLES,
                "category": "Dorky mladší",
                "name_order": "surname-first",
                "rows": [
                    {
                        "bbox": [20, top + 60, 635, top + 90],
                        "cells": {
                            "rank": "1",
                            "name": "Černá Alena",
                            "first": "18,58",
                            "second": "DNS",
                            "final": "18,58",
                        },
                    }
                ],
            }
        ],
    }
    manifest = {report["sha256"]: {"regions": {ocr["key"]: reviewed}}}
    output, _, report = youth_pdf.convert(path, tmp_path / "ocr", manifest)
    assert not report["errors"]
    assert report["pages"][0]["ocr"][0]["status"] == "visually_verified"
    assert (
        output["competition"]["categories"][0]["results"][0]["times"][1][
            "invalid_reason"
        ]
        == "DNS"
    )
    reviewed["tables"][0]["heading"] = PHP
    with pytest.raises(ValueError, match="jednoznačné záhlaví"):
        checked_region(reviewed, area)


def test_conflicts_and_unpublished_values():
    report = {"warnings": []}
    data = youth_pdf.metadata(
        [
            [
                (5, METADATA),
                (10, "Okresní kolo v PS 13.6.2026 Písek"),
                (20, "Jihočeský kraj"),
            ],
            [(5, "Datum: 14.6.2026")],
        ],
        report,
    )
    assert data["name"] == "Krajská soutěž dorostu" and data["date"] is None
    assert data["league"] is None
    assert len(report["metadata_evidence"]["date"]) == 3
    assert any("Rozporné názvy" in w for w in report["warnings"])
    source = SourceRow(
        "Dorky",
        {"name": "Černá Alena", "first": "DNS", "second": "NP", "final": "DNF"},
        True,
        (),
    )
    row, _ = youth_pdf.parse_result(source, {"page": 1, "table": 1, "row": 1}, [])
    assert row["final_time"] is None and row["final_status"] == "invalid"
    assert headline_kind("Štafeta 4 × 100 m s překážkami") == "other"


def test_duplicate_geometry_and_unresolved_layout(text_pdf, tmp_path, monkeypatch):
    expected = youth_pdf.extract_sections

    def doubled(*args):
        sections, carry, lines = expected(*args)
        for section in sections:
            if section.kind == "hurdles":
                section.rows.insert(0, section.rows[0])
        return sections, carry, lines

    monkeypatch.setattr(youth_pdf, "extract_sections", doubled)
    _, _, report = youth_pdf.convert(text_pdf, tmp_path / "review")
    assert report["results"] == 2 and report["excluded"]["duplicate_extraction"] == 2


def test_batch_continues_and_dry_run_only_writes_diagnostics(text_pdf, tmp_path):
    (tmp_path / "bad.pdf").write_bytes(b"%PDF-bad")
    data = tmp_path / "data"
    diagnostics = tmp_path / "reports"
    assert (
        youth_pdf.main(
            [
                str(tmp_path),
                "--output",
                str(data),
                "--diagnostics",
                str(diagnostics),
                "--dry-run",
            ]
        )
        == 1
    )
    assert not data.exists()
    docs = json.loads((diagnostics / "batch-report.json").read_text())["documents"]
    assert [(entry["results"], bool(entry["errors"])) for entry in docs] == [
        (0, True),
        (2, False),
    ]


def test_jihocesky_reference(tmp_path):
    path = os.environ.get("YOUTH_PDF_JIHOCESKY")
    if not path:
        pytest.skip("Set YOUTH_PDF_JIHOCESKY to the supplied 24-page PDF")
    result, _, report = youth_pdf.convert(Path(path), tmp_path)
    assert report["errors"] == [] and len(report["pages"]) == 24
    assert report["counts"] == {
        "Dorky": 42,
        "Dorci": 27,
        "Dorky mladší": 4,
        "Dorky střední": 5,
        "Dorky starší": 6,
        "Dorci mladší": 5,
        "Dorci střední": 6,
        "Dorci starší": 7,
    }
    assert report["excluded"]["placeholder"] == 1
    assert result["competition"]["place"] == "Písek"
    assert result["competition"]["date"] == "2026-06-13"
    assert report["region"] == "Jihočeský"
    assert all(row["page"] not in {11, 13, 16, 19, 22} for row in report["rows"])
    by_category = {
        group["name"]: group["results"] for group in result["competition"]["categories"]
    }
    assert by_category["Dorky"][0]["final_time"] == 18.58
    assert by_category["Dorky"][16]["final_time"] == 20.54
    assert by_category["Dorci"][0]["final_time"] == 17.24
    row = by_category["Dorky mladší"][0]
    assert (row["last_name"], row["first_name"], row["start_number"]) == (
        "Pozníčková",
        "Kateřina",
        "2",
    )
    assert [a["time"] for a in row["times"]] == [24.59, 20.13]
    assert any(r.get("source_identifier") == "55" for r in report["rows"])


@pytest.mark.parametrize("layout", ["two-attempts", "final-only"])
def test_horizontal_discipline_bands(tmp_path, layout):
    """Use neighboring PHP/duel and overall cells as data leak sentinels."""
    path = tmp_path / f"{layout}.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=950, height=500)
        write_text(page, 25, 35, METADATA)
        if layout == "two-attempts":
            columns = [
                20,
                55,
                185,
                265,
                350,
                440,
                490,
                540,
                610,
                660,
                710,
                760,
                830,
                880,
                920,
                940,
            ]
            fields = [
                "St.č.",
                "Příjmení a jméno",
                "OSH",
                "Družstvo/SDH",
                "kategorie",
                "čas",
                "čas",
                "Výsledný čas",
                "Pořadí",
                "čas",
                "čas",
                "Výsledný čas",
                "Pořadí",
                "Součet",
                "Celkové Pořadí",
            ]
            values = [
                "1",
                "Černá Alena",
                "Březina",
                "Liberec",
                "Mladší dorky",
                "16,30",
                "16,20",
                "16,20",
                "1",
                "20,10",
                "DNS",
                "20,10",
                "2",
                "3",
                "1",
            ]
            header_bands = [(5, "100m s PHP"), (9, "100m")]
            band_divisions = {0, 5, 9, 13, 15}
        else:
            columns = [20, 85, 215, 330, 390, 440, 500, 560, 610, 660, 720]
            fields = [
                "start. číslo",
                "Jméno a příjmení",
                "SOUTĚŽNÍ DRUŽSTVO",
                "Okres",
                "Čas",
                "Pořadí",
                "Čas",
                "Pořadí",
                "Počet bodů",
                "Pořadí",
            ]
            values = [
                "12",
                "Alena Černá",
                "Březina",
                "LI",
                "16,20",
                "1",
                "20,10",
                "2",
                "3",
                "1",
            ]
            header_bands = [(0, "Celkové výsledky"), (4, "Dvojboj"), (6, "Běh na 100m")]
            band_divisions = {0, 4, 6, 8, 10}
        for y in (75, 105, 135, 162, 190):
            page.draw_line((columns[0], y), (columns[-1], y))
        for i, x in enumerate(columns):
            top = (
                75
                if i in {0, len(columns) - 1}
                else 105
                if i in band_divisions
                else 135
            )
            page.draw_line((x, top), (x, 190))
        if layout == "final-only":
            write_text(page, 24, 93, "Jednotlivci - dorostenky mladší")
        for i, label in header_bands:
            write_text(page, columns[i] + 3, 124, label)
        for i, (field, value) in enumerate(zip(fields, values, strict=True)):
            write_text(page, columns[i] + 2, 153, field)
            write_text(page, columns[i] + 2, 181, value)
        pdf.save(path)
    result, _, report = youth_pdf.convert(path, tmp_path / "diagnostics")
    assert report["errors"] == []
    (row,) = result["competition"]["categories"][0]["results"]
    assert row["final_time"] == 20.10 and row["rank"] == 2
    assert row["last_name"] == "Černá"
    expected = (
        ["valid", "invalid"] if layout == "two-attempts" else ["missing", "missing"]
    )
    assert [attempt["status"] for attempt in row["times"]] == expected


def test_damaged_heading_cannot_continue_previous_discipline(text_pdf, tmp_path):
    path = tmp_path / "damaged.pdf"
    with pymupdf.open(text_pdf) as pdf:
        write_text(pdf[1], 30, 18, "Běh na 100 m s P?P")
        pdf.save(path)
    output, _, report = youth_pdf.convert(path, tmp_path / "review")
    assert report["errors"]
    assert report["results"] == 1
    assert output["competition"]["categories"][0]["results"][0]["final_time"] == 18.58


def test_youth_pdf_preserves_source_order_and_spacing_for_explicit_name_columns():
    from app.extraction.youth_pdf import parse_result
    from app.extraction.youth_pdf_tables import SourceRow

    cells = {"first_name": "Anna  Marie", "last_name": "Nováková  Svobodová",
             "source_full_name": "Nováková  Svobodová Anna  Marie",
             "rank": "1", "first": "18.11", "second": "-", "final": "18.11"}
    row, warning = parse_result(SourceRow("Mladší dorostenky", cells, None, (0, 0, 0, 0)),
                                {"page": 1, "table": 1, "row": 1}, [])
    assert warning is None
    assert (row["first_name"], row["last_name"]) == ("Anna Marie", "Nováková Svobodová")
    assert row["source_full_name"] == cells["source_full_name"]
