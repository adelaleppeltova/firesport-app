"""Batch conversion of local youth 100 m hurdle PDFs without database access."""

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

from jsonschema.exceptions import ValidationError
from pdfminer.pdfparser import PDFSyntaxError

import pdfplumber
import pymupdf

from app.result_values import best_valid_attempt, invalid_name_fields

from .metadata import norm, parse_date
from .ocr import recognize
from .participants import fscode, integer, split_name
from .paths import resolve_path
from .storage import document, save, source_id
from .times import parse_time
from .validation import validate
from .youth_pdf_tables import AGE, YOUTH, clean, extract_sections
from .youth_pdf_review import checked_region, ocr_lines, ocr_words, read_review

PLACEHOLDER = re.compile(
    r"^(?:nestartoval[oai]?|nestartuje|neobsazen[oa]?|volno|dns|[-–—])$", re.I
)
DATE = re.compile(r"\b\d{1,2}\s*[./]\s*\d{1,2}\s*[./]\s*\d{4}\b")
TITLE = re.compile(
    r"\b(?:(?:krajska soutez|krajske kolo(?: souteze)?|ii\.\s*kolo souteze)\s+dorost\w*|okresni kolo v ps)\b"
)


def write_json(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def category_info(label, team):
    key = norm(label).replace("_", " ")
    gender, age = YOUTH.search(key), AGE.search(key)
    if not gender:
        return None
    female = gender[0] in {"dorky", "dorostenky"}
    if age and not team:
        prefix = {
            "mladsi": "Mladší",
            "stredni": "Střední",
            "st edni": "Střední",
            "starsi": "Starší",
        }[age[0]]
        return f"{prefix} {'dorostenky' if female else 'dorostenci'}"
    if team:
        return "Dorostenky - družstvo" if female else "Dorostenci - družstvo"
    return None


def metadata(pages, report):
    evidence = {key: [] for key in ("name", "date", "place", "region", "league")}

    def add(key, value, page, original):
        if value:
            evidence[key].append({"page": page, "value": value, "source": original})

    for page, lines in enumerate(pages, 1):
        for _, line in lines:
            key = norm(line)
            if (match := DATE.search(line)) and (
                TITLE.search(key)
                or re.match(r"^(?:Datum\s*:\s*)?\d{1,2}\s*[./]", line, re.I)
                or key.startswith("datum:")
            ):
                add("date", parse_date(match[0].replace("/", ".")), page, line)
                after = line[match.end() :].strip(" ,–-")
                if (
                    after
                    and any(c.isalpha() for c in after)
                    and re.fullmatch(r"[\w. ()-]+", after)
                    and not TITLE.search(norm(after))
                ):
                    add("place", after, page, line)
                before = line[: match.start()]
                if (title := TITLE.search(norm(before))) and "–" in before:
                    add("place", before.split("–")[-1].strip(" ,"), page, line)
                elif title and re.fullmatch(
                    r"[\w. ()-]+", before[title.end() :].strip()
                ):
                    candidate = before[title.end() :].strip()
                    if any(c.isalpha() for c in candidate) and norm(candidate) not in {
                        "mladsi",
                        "stredni",
                        "starsi",
                        "v ps",
                    }:
                        add("place", candidate, page, line)
            if explicit := re.fullmatch(
                r"(?:Závod|Název závodu)\s*:\s*(.+)", line, re.I
            ):
                if norm(explicit[1]) not in {"vysledkova listina", "celkove vysledky"}:
                    add("name", explicit[1], page, line)
            elif (title := TITLE.search(key)) and not key.startswith(
                "celkove vysledky"
            ):
                # The normalized heading is positionally identical for Czech accents.
                add("name", line[title.start() : title.end()], page, line)
            if match := re.fullmatch(r"(?:Kraj:\s*)?([\w]+)(?:\s+kraj)?", line, re.I):
                if key.startswith("kraj:") or key.endswith(" kraj"):
                    add("region", match[1], page, line)
            if match := re.search(r"[–-]\s*([\w]+) kraj\s*[–-]", line, re.I):
                add("region", match[1], page, line)
            if match := re.match(r"(?:Liga|Seriál)\s*:\s*(.+)", line, re.I):
                add("league", match[1], page, line)
            if match := re.fullmatch(r"Místo(?: konání)?\s*:\s*(.+)", line, re.I):
                add("place", match[1], page, line)

    report["metadata_evidence"] = evidence
    values = {}
    for key, entries in evidence.items():
        candidates = {
            re.sub(r"\.\s*", ".", norm(entry["value"])): entry["value"]
            for entry in reversed(entries)
        }
        if len(candidates) <= 1:
            values[key] = next(iter(candidates.values()), None)
        elif (
            key == "name" and "okresni kolo v ps" in candidates and len(candidates) == 2
        ):
            # The document supplies an explicit regional youth title alongside
            # the generic label used in the team-results printout.
            values[key] = next(
                value
                for label, value in candidates.items()
                if label != "okresni kolo v ps"
            )
            report["warnings"].append(
                f"Rozporné názvy závodu: {list(candidates.values())!r}"
            )
        else:
            values[key] = None
            report["warnings"].append(
                f"Rozporné metadata {key}: {list(candidates.values())!r}"
            )
    report["region"] = values.pop("region")
    for key in ("name", "date", "place"):
        if not values[key]:
            report["warnings"].append(f"Chybí ověřené metadata: {key}.")
    return values


def result_time(raw, warnings, context, *, attempt=None):
    if raw is None:
        return parse_time(None, warnings, context, absent=True)
    raw = clean(raw).replace("–", "-").replace("—", "-")
    status = re.fullmatch(
        r"(?:\d+[.,]\d+\s*)?\(?(NP|DNS|DNF|DSQ|DQ|DISQ)\)?", raw, re.I
    )
    if status:
        result = {"time": None, "status": "invalid"}
        if attempt:
            result["invalid_reason"] = status[1].upper()
        return result
    result = parse_time(raw, warnings, context)
    if result["time"] == 0:
        warnings.append(f"{context}: nulový čas vyžaduje ověření")
        return {"time": None, "status": "invalid"}
    if not attempt and result["status"] != "valid":
        result["time"] = None
    return result


def parse_result(source, location, warnings, *, best_attempt_rule=None):
    cells = source.cells
    raw_name = cells.get("name") or ""
    prefix = re.fullmatch(r"(\d+)\s*[-–—\u00ad]\s*(.+)", raw_name)
    if prefix:
        raw_name = prefix[2]
        location["source_identifier"] = prefix[1]
    context = f"Strana {location['page']}, {source.category}, tabulka {location['table']}, řádek {location['row']}"
    if PLACEHOLDER.fullmatch(norm(raw_name)):
        return None, "placeholder"
    if not raw_name or not any(c.isalpha() for c in raw_name):
        if not any(
            cells.get(key) for key in ("team", "first", "second", "final", "rank")
        ):
            return None, "empty_slot"
        warnings.append(f"{context}: chybí skutečné jméno závodníka")
        return None, "unverified_name"
    location["source_name"] = raw_name

    if cells.get("name_overflow"):
        first = last = None
        warnings.append(f"{context}: text přesahuje buňku jména; ověřte podle PDF")
    else:
        ordered = source.surname_first
        if ordered is None and len(raw_name.split()) == 2:
            a, b = raw_name.split()
            if a.isupper() != b.isupper():
                ordered = a.isupper()
        if ordered is None:
            first, last = split_name(raw_name, warnings, context)
        elif not ordered and len(raw_name.split()) == 2:
            first, last = raw_name.split()
        else:
            first, last = split_name(raw_name, warnings, context, surname_first=ordered)

    attempts = [
        {
            "try": number,
            **result_time(cells.get(key), warnings, context, attempt=number),
        }
        for number, key in enumerate(("first", "second"), 1)
    ]
    raw_final = cells.get("final")
    final = result_time(raw_final if raw_final else None, warnings, context)
    best = best_valid_attempt(attempts)
    provenance = None
    if final["status"] == "valid":
        provenance = "published"
        if best is not None and final["time"] != best:
            warnings.append(
                f"{context}: zveřejněný výsledný čas se liší od minima pokusů"
            )
            location["final_time_conflict"] = {
                "published": final["time"],
                "best_attempt": best,
            }
    elif final["status"] == "invalid":
        location["final_time_reason"] = "published_invalid"
        if best is not None:
            warnings.append(
                f"{context}: neplatný výsledný výkon má zveřejněný platný pokus"
            )
            location["final_time_conflict"] = {
                "published_status": "invalid",
                "best_attempt": best,
            }
    elif best is not None and best_attempt_rule:
        final = {"time": best, "status": "valid"}
        provenance = "derived_from_attempts"
        location["final_time_rule"] = best_attempt_rule
    elif best is not None:
        location["final_time_reason"] = "best_attempt_rule_unverified"
    elif all(attempt["status"] == "invalid" for attempt in attempts):
        final["status"] = "invalid"
        location["final_time_reason"] = "all_attempts_invalid"
    else:
        location["final_time_reason"] = "insufficient_published_attempts"

    location["final_time"] = final["time"]
    location["final_time_status"] = final["status"]
    location["final_time_source"] = provenance
    if invalid_name_fields({"first_name": first, "last_name": last}):
        warnings.append(f"{context}: jméno nebo příjmení nelze ověřit: {raw_name!r}")
        return None, "unverified_name"
    rank = integer(cells.get("rank"))
    if cells.get("rank") and not rank:
        warnings.append(f"{context}: neznámý formát pořadí {cells['rank']!r}")
    bib = cells.get("bib")
    if bib and not integer(bib):
        warnings.append(f"{context}: nejednoznačné startovní číslo {bib!r}")
        bib = None
    return {
        "rank": rank or None,
        "start_number": bib or None,
        "first_name": first,
        "last_name": last,
        "team": cells.get("team") or None,
        "district": cells.get("district") or None,
        "birth_year": None,
        "fscode": fscode(cells.get("fscode"), warnings, context),
        "times": attempts,
        "final_time": final["time"],
        "final_status": final["status"],
        **({"final_time_source": provenance} if provenance else {}),
    }, None


def convert(path, diagnostics, review=None):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    entry = (review or {}).get(digest, {})
    best_attempt_rule = entry.get("best_attempt_rule")
    if best_attempt_rule is not None and (
        not isinstance(best_attempt_rule, str) or not best_attempt_rule.strip()
    ):
        raise ValueError(
            "Pravidlo nejlepšího pokusu musí obsahovat odkaz nebo popis podkladu."
        )
    name_order = entry.get("name_order")
    if name_order not in {"surname-first", "given-first", None}:
        raise ValueError("Neplatné ověřené pořadí jména.")
    report = {
        "source": path.resolve().as_uri(),
        "sha256": digest,
        "pages": [],
        "rows": [],
        "warnings": [],
        "errors": [],
    }
    issues, warnings = report["errors"], report["warnings"]
    categories, printed, excluded = {}, Counter(), Counter()
    previous = None
    metadata_pages = []
    seen = set()
    count = 0
    with pymupdf.open(path) as rendered, pdfplumber.open(path) as document_pdf:
        if not rendered.is_pdf:
            raise ValueError("Vstup nemá formát PDF")
        for page_number, (pdf_page, page) in enumerate(
            zip(rendered, document_pdf.pages, strict=True), 1
        ):
            page_report = {"page": page_number, "tables": [], "ocr": []}
            report["pages"].append(page_report)
            source_text = pdf_page.get_text()
            page_report["text_layer"] = bool(source_text.strip())
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / f"page-{page_number}.txt").write_text(
                source_text, encoding="utf-8"
            )
            sections, previous, lines = extract_sections(pdf_page, page, previous)
            image_boxes = [
                pymupdf.Rect(info["bbox"]) & pdf_page.rect
                for info in pdf_page.get_image_info()
            ]
            if len(source_text.strip()) < 30 or "\ufffd" in source_text:
                regions = [(None, pdf_page.rect)]
            else:
                # Embedded graphics smaller than a plausible table need no OCR.
                regions = [
                    (i, box)
                    for i, box in enumerate(image_boxes, 1)
                    if box.width >= pdf_page.rect.width * 0.45
                    and box.height >= 80
                    and not any(
                        (pymupdf.Rect(section.bbox) & box).get_area()
                        >= box.get_area() * 0.8
                        and section.kind != "unresolved"
                        for section in sections
                    )
                ]
            reviewed_sections, reviewed_lines = [], []
            for region, box in regions:
                key = (
                    str(page_number)
                    if region is None
                    else f"{page_number}-region-{region}"
                )
                page_report["ocr"].append(
                    {"key": key, "bbox": tuple(box), "status": "requires_review"}
                )
                try:
                    tsv = recognize(pdf_page, diagnostics, key, clip=box, sparse=True)
                    words = ocr_words(tsv)
                    write_json(diagnostics / f"page-{key}.ocr-words.json", words)
                    write_json(
                        diagnostics / f"page-{key}.ocr-lines.json", ocr_lines(words)
                    )
                    page_report["ocr"][-1]["words"] = len(words)
                except (
                    ValueError,
                    OSError,
                    RuntimeError,
                    subprocess.SubprocessError,
                ) as exc:
                    page_report["ocr"][-1]["error"] = str(exc)
                verified = entry.get("regions", {}).get(key)
                if verified is None:
                    issues.append(
                        f"Strana {page_number}, oblast {key}: OCR vyžaduje vizuální ověření."
                    )
                else:
                    try:
                        accepted, evidence = checked_region(verified, box)
                    except (KeyError, TypeError, ValueError) as exc:
                        issues.append(
                            f"Strana {page_number}, oblast {key}: neplatné ověření OCR ({exc})."
                        )
                        continue
                    reviewed_sections.extend(accepted)
                    reviewed_lines.extend(evidence)
                    page_report["ocr"][-1]["status"] = "visually_verified"
                    # A scan cannot provide a proven continuation for the next page.
                    previous = None
            sections += reviewed_sections
            sections.sort(key=lambda section: (section.bbox[1], section.bbox[0]))
            metadata_pages.append(lines + reviewed_lines)
            if not sections and not regions:
                issues.append(
                    f"Strana {page_number}: nerozpoznané rozložení bez tabulky."
                )
            for table_number, section in enumerate(sections, 1):
                table_report = {
                    "table": table_number,
                    "heading": section.heading,
                    "kind": section.kind,
                    "bbox": section.bbox,
                    "source_rows": len(section.rows),
                }
                page_report["tables"].append(table_report)
                if section.kind == "unresolved":
                    issues.append(
                        f"Strana {page_number}, tabulka {table_number}: {section.heading}"
                    )
                if section.kind not in {"hurdles", "team_individuals"}:
                    excluded[section.kind] += sum(
                        isinstance(row, list) and integer(row[0]) is not None
                        for row in section.rows
                    )
                    continue
                if not section.rows:
                    issues.append(
                        f"Strana {page_number}, tabulka {table_number}: žádné rozpoznané řádky."
                    )
                for row_number, row in enumerate(section.rows, 1):
                    if not row.category:
                        issues.append(
                            f"Strana {page_number}, tabulka {table_number}: chybí kategorie."
                        )
                        excluded["unresolved"] += 1
                        continue
                    loc = {
                        "page": page_number,
                        "table": table_number,
                        "row": row_number,
                        "category": row.category,
                        "bbox": row.bbox,
                        "source_cells": row.cells,
                        "source_category": row.source_category or row.category,
                        "normalized_category": category_info(
                            row.category, section.kind == "team_individuals"
                        ),
                        "team_section": section.kind == "team_individuals",
                    }
                    report["rows"].append(loc)
                    signature = (
                        page_number,
                        tuple(round(x, 1) for x in row.bbox),
                        row.category,
                    )
                    if signature in seen:
                        loc["excluded"] = "duplicate_extraction"
                        excluded["duplicate_extraction"] += 1
                        continue
                    seen.add(signature)
                    warning_start = len(warnings)
                    if row.surname_first is None and name_order:
                        row.surname_first = name_order == "surname-first"
                    parsed, reason = parse_result(
                        row, loc, warnings, best_attempt_rule=best_attempt_rule
                    )
                    if any(
                        "unrecognized time" in warning or "invalid seconds" in warning
                        for warning in warnings[warning_start:]
                    ):
                        issues.append(
                            f"Strana {page_number}, tabulka {table_number}, řádek {row_number}: nejednoznačný čas."
                        )
                    if len(warnings) > warning_start:
                        loc["review"] = warnings[warning_start:]
                    if reason:
                        loc["excluded"] = reason
                        excluded[reason] += 1
                        if reason in {"unresolved", "unverified_name"}:
                            issues.append(
                                f"Strana {page_number}, tabulka {table_number}, řádek {row_number}: jméno účastníka vyžaduje ověření."
                            )
                        continue
                    current = categories.setdefault(row.category, [])
                    loc["result_index"] = len(current)
                    current.append(parsed)
                    printed[row.category] += 1
                    count += 1

    info = metadata(metadata_pages, report)
    folder_year = next(
        (part for part in reversed(path.parts[:-1]) if re.fullmatch(r"20\d{2}", part)),
        None,
    )
    if info["date"] and folder_year and info["date"][:4] != folder_year:
        issues.append(
            f"Datum v PDF ({info['date']}) se liší od roku složky ({folder_year})."
        )
    if report["rows"] and any(
        loc.get("final_time_reason") == "best_attempt_rule_unverified"
        for loc in report["rows"]
    ):
        warnings.append(
            "U části výsledků není uveden samostatný výsledný čas; zůstává null."
        )
    if any("source_affiliation" in loc["source_cells"] for loc in report["rows"]):
        warnings.append(
            "Záhlaví OSH a Družstvo/SDH jsou v rozporu s obsahem; údaje zůstaly v reportu."
        )
    report["counts"] = dict(printed)
    report["results"] = count
    source_rows = sum(
        table["source_rows"]
        for page in report["pages"]
        for table in page["tables"]
        if table["kind"] in {"hurdles", "team_individuals"}
    )
    report["hurdles_source_rows"] = source_rows
    accounted = count + sum(
        excluded[key]
        for key in (
            "placeholder",
            "empty_slot",
            "duplicate_extraction",
            "unresolved",
            "unverified_name",
        )
    )
    if accounted != source_rows:
        issues.append(
            f"Zdrojových řádků {source_rows}, přiřazených nebo vyřazených {accounted}."
        )
    report["excluded"] = {reason: n for reason, n in excluded.items() if n}
    report["final_times"] = dict(
        Counter(
            loc["final_time_source"] or loc["final_time_reason"]
            for loc in report["rows"]
            if "final_time_status" in loc
        )
    )
    report["final_time_conflicts"] = sum(
        "final_time_conflict" in loc for loc in report["rows"]
    )
    if not categories:
        issues.append("Nebyla ověřena žádná individuální tabulka stovky.")
        return None, None, report
    info["categories"] = [
        {"name": name, "discipline": "100m", "results": results}
        for name, results in categories.items()
    ]
    audit = [
        {
            "category": name,
            "rows": printed[name],
            "numbered_reasons": sum(
                "invalid_reason" in attempt
                for result in results
                for attempt in result["times"]
            ),
        }
        for name, results in categories.items()
    ]
    output = document(
        report["source"],
        info,
        [
            f"Provenience řádků (index od 0 v rámci kategorie): {source_id(report['source'])}/report.json.",
            "Převedeny individuální výsledky běhu na 100 m s překážkami.",
            *(
                [f"Pravidlo nejlepšího platného pokusu: {best_attempt_rule}"]
                if best_attempt_rule
                else []
            ),
        ],
        warnings,
    )
    try:
        validate(output, audit)
    except (ValueError, ValidationError) as exc:
        issues.append(
            f"Validace výstupu: {exc.message if isinstance(exc, ValidationError) else exc}"
        )
        return None, None, report
    return output, audit, report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input", type=Path, help="Adresář PDF; podsložky se procházejí rekurzivně"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data"),
        help="Kořen dat pro ověřené výsledky",
    )
    parser.add_argument(
        "--diagnostics", type=Path, default=Path(".extraction-diagnostics/youth-pdf")
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Uloží pouze kandidáty a reporty do diagnostiky",
    )
    parser.add_argument(
        "--review",
        type=Path,
        help="Ověřené oblasti OCR a konvence jmen podle SHA-256 PDF",
    )
    args = parser.parse_args(argv)
    try:
        review = read_review(args.review)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if not args.input.is_dir():
        parser.error("Vstup musí být adresář.")
    reports = []
    for path in sorted(p for p in args.input.rglob("*") if p.is_file()):
        if path.suffix.lower() != ".pdf":
            try:
                with path.open("rb") as stream:
                    if b"%PDF-" not in stream.read(1024):
                        continue
            except OSError:
                continue
        uri = path.resolve().as_uri()
        diagnostics = args.diagnostics / source_id(uri)
        try:
            output, audit, report = convert(path, diagnostics, review)
            if output:
                destination = diagnostics / "pending.json"
                write_json(destination, output)
                report["output"] = str(destination)
                if not report["errors"] and not args.dry_run:
                    try:
                        report["output"] = str(save(output, args.output, audit))
                    except ValueError as exc:
                        report["errors"].append(str(exc))
                elif not report["errors"]:
                    try:
                        resolve_path(output, args.output)
                    except ValueError as exc:
                        report["errors"].append(str(exc))
        except (
            OSError,
            ValueError,
            RuntimeError,
            ValidationError,
            PDFSyntaxError,
        ) as exc:
            report = {"source": uri, "errors": [str(exc)], "results": 0}
        report_path = diagnostics / "report.json"
        write_json(report_path, report)
        reports.append(
            {
                "source": uri,
                "results": report["results"],
                "excluded": report.get("excluded", {}),
                "final_times": report.get("final_times", {}),
                "final_time_conflicts": report.get("final_time_conflicts", 0),
                "ocr_pages": [p["page"] for p in report.get("pages", []) if p["ocr"]],
                "errors": report["errors"],
                "report": str(report_path),
                "output": report.get("output"),
            }
        )
    write_json(args.diagnostics / "batch-report.json", {"documents": reports})
    return int(not reports or any(r["errors"] for r in reports))


if __name__ == "__main__":
    raise SystemExit(main())
