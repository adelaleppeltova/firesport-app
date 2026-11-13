"""All-page extraction of ruled PDF tables; unknown layouts fail closed."""

import io
import re
import json
import subprocess
from html import escape
from .html import column_map, parse_html, is_result_header
from .metadata import norm


def tables_to_html(pages):
    """Merge explicitly identified continuation tables, retaining category transitions."""
    groups = []
    current = None
    headers = None
    for page in pages:
        for block in page["tables"]:
            label, rows = block["category"], block["rows"]
            if label and re.search(r"\b(finalovy beh|superfinale)\b", norm(label)):
                continue
            if label:
                current = next(
                    (group for group in groups if group["name"] == label), None
                )
                if current is None:
                    current = {"name": label, "rows": []}
                    groups.append(current)
                    headers = None
            if current is None:
                raise ValueError("PDF table has no explicit category heading")
            for row in rows:
                row = [str(c or "").strip() for c in row]
                mapping = column_map(row)
                if is_result_header(mapping):
                    if headers is not None and row != headers:
                        raise ValueError(
                            "Changed PDF continuation header; adapter needed"
                        )
                    if not current["rows"]:
                        current["rows"].append(row)
                    headers = row
                else:
                    if headers is None or len(row) != len(headers):
                        raise ValueError(
                            "Unresolved PDF wrapped/merged row; adapter needed"
                        )
                    current["rows"].append(row)
        if not page["tables"] and page["result_like"]:
            raise ValueError(
                "Result-like PDF page without extracted tables; adapter/OCR review needed"
            )
    output = []
    for group in groups:
        output.append("<table><caption>" + escape(group["name"]) + "</caption>")
        for row in group["rows"]:
            output.append(
                "<tr>" + "".join("<td>" + escape(c) + "</td>" for c in row) + "</tr>"
            )
        output.append("</table>")
    return "".join(output)


def parse_pdf(data, url, diagnostics):
    import pdfplumber
    import pymupdf
    from .ocr import recognize

    diagnostics.mkdir(parents=True, exist_ok=True)
    pages, used_ocr, ocr_errors, metadata_lines = [], False, [], []
    with (
        pdfplumber.open(io.BytesIO(data)) as document,
        pymupdf.open(stream=data, filetype="pdf") as rendered,
    ):
        for number, page in enumerate(document.pages, 1):
            text = page.extract_text() or ""
            (diagnostics / f"page-{number}.txt").write_text(text, encoding="utf-8")
            metadata_lines.extend(text.splitlines())
            if len(text.strip()) < 30 or "\ufffd" in text:
                used_ocr = True
                try:
                    recognize(rendered[number - 1], diagnostics, number)
                except (
                    ValueError,
                    OSError,
                    RuntimeError,
                    subprocess.SubprocessError,
                ) as exc:
                    ocr_errors.append({"page": number, "error": str(exc)})
                continue
            blocks = []
            for table in page.find_tables():
                before = (
                    page.crop((0, 0, page.width, table.bbox[1])).extract_text() or ""
                )
                # Accept explicit category labels only, not guessed title/athlete lines.
                labels = re.findall(
                    r"(?im)^\s*(?:Kategorie\s*:\s*(.+)|(Finálový běh|Superfinále)\s*)$",
                    before,
                )
                labels = [category or final for category, final in labels]
                blocks.append(
                    {
                        "category": labels[-1].strip() if labels else None,
                        "rows": table.extract(),
                    }
                )
            pages.append(
                {
                    "tables": blocks,
                    "result_like": bool(re.search(r"\b(?:Čas|Pořadí|Or\.)", text)),
                }
            )
        count = len(document.pages)
    if used_ocr:
        (diagnostics / "ocr-review.json").write_text(
            json.dumps(
                {"pages": count, "errors": ocr_errors, "review_required": True},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        raise ValueError(
            "OCR diagnostics saved; visual verification and a source adapter are required before publishing"
        )
    labels = {"name": [], "place": [], "date": [], "league": []}
    for line in metadata_lines:
        for pattern, key in [
            (r"(?:Závod|Název závodu)\s*:\s*(.+)", "name"),
            (r"Místo(?: konání)?\s*:\s*(.+)", "place"),
            (r"Datum(?: konání)?\s*:\s*(.+)", "date"),
            (r"(?:Liga|Seriál)\s*:\s*(.+)", "league"),
        ]:
            match = re.fullmatch(pattern, line.strip(), re.I)
            if match and match[1] not in labels[key]:
                labels[key].append(match[1])
    tags = []
    for key, values in labels.items():
        if len(values) != 1:
            continue
        value = escape(values[0])
        tags.append(
            f"<h1>{value}</h1>"
            if key == "name"
            else f"<div data-race-{key}>{value}</div>"
        )
    competition, notes, warnings, audit = parse_html(
        "".join(tags) + tables_to_html(pages), url
    )
    notes[:0] = [
        f"Source: PDF; all {count} pages inspected; text layer and ruled tables; OCR not used."
    ]
    notes.append(
        "PDF metadata accepted only from unambiguous explicit labels; no organizer/team location inference."
    )
    return competition, notes, warnings, audit
