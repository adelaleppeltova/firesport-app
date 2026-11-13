"""OCR diagnostics are never automatically promoted to verified source data."""

import json
import shutil
import subprocess


def recognize(page, directory, page_number):
    if not shutil.which("tesseract"):
        raise ValueError("Scanned PDF requires Tesseract with ces language data")
    png = directory / f"page-{page_number}.png"
    page.get_pixmap(dpi=300).save(png)
    completed = subprocess.run(
        ["tesseract", str(png), "stdout", "-l", "ces+eng", "tsv"],
        capture_output=True,
        text=True,
        check=True,
        timeout=180,
    )
    (directory / f"page-{page_number}.ocr.tsv").write_text(
        completed.stdout, encoding="utf-8"
    )
    (directory / "review-required.json").write_text(
        json.dumps(
            {
                "page": page_number,
                "reason": "OCR must be checked against page image before adding a verified source adapter",
            }
        ),
        encoding="utf-8",
    )
    return completed.stdout
