"""python -m app.extraction URL [URL ...]"""

import argparse
import json
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .fetch import Fetcher, source_type, render_html
from .html import parse_html
from .pdf import parse_pdf
from .storage import source_id, document, save, summary

ROOT = Path(__file__).resolve().parents[3]


def extract(url, fetcher, diagnostics, browser=False):
    data, resolved = fetcher.get(url)
    kind = source_type(data)
    diagnostics.mkdir(parents=True, exist_ok=True)
    (diagnostics / f"source.{kind}").write_bytes(data)
    if kind == "pdf":
        return parse_pdf(data, resolved, diagnostics)
    try:
        return parse_html(data, resolved, fetcher)
    except ValueError as original:
        # Only select linked PDFs when no result table exists, never hide failed HTML parses.
        soup = BeautifulSoup(data, "html.parser")
        if soup.find("table"):
            if browser:
                return parse_html(render_html(resolved), resolved, fetcher)
            raise
        links = list(
            dict.fromkeys(
                urljoin(resolved, a["href"])
                for a in soup.select("a[href]")
                if "vysled" in a.get_text(" ", strip=True).lower()
                or a["href"].lower().split("?")[0].endswith(".pdf")
            )
        )
        pdfs = []
        for link in links:
            content, target = fetcher.get(link)
            if source_type(content) == "pdf":
                pdfs.append((content, target))
        if len(pdfs) == 1:
            content, target = pdfs[0]
            result = parse_pdf(content, target, diagnostics)
            result[1].append(f"Results PDF linked from {resolved}: {target}")
            return result
        if pdfs:
            raise ValueError(
                "Multiple attached result PDFs require an adapter to distinguish categories/races"
            ) from original
        if browser:
            return parse_html(render_html(resolved), resolved, fetcher)
        raise ValueError(
            f"{original}; dynamic sources: retry with --browser or add source adapter"
        ) from original


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("urls", nargs="+")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data",
        help="Data root; results go into year/competition-folder",
    )
    parser.add_argument(
        "--diagnostics", type=Path, default=ROOT / ".extraction-diagnostics"
    )
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args(argv)
    fetcher, report, failed = Fetcher(), [], False
    for url in dict.fromkeys(args.urls):
        directory = args.diagnostics / source_id(url)
        directory.mkdir(parents=True, exist_ok=True)
        result = None
        try:
            competition, notes, warnings, audit = extract(
                url, fetcher, directory, args.browser
            )
            result = document(url, competition, notes, warnings)
            path = save(result, args.output, audit)
            entry = {"url": url, "success": True, "path": str(path), **summary(result)}
            (directory / "audit.json").write_text(
                json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            failed = True
            if result is not None:
                (directory / "pending.json").write_text(
                    json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)
                    + "\n",
                    encoding="utf-8",
                )
            entry = {
                "url": url,
                "success": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        (directory / "report.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        report.append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    print(
        json.dumps(
            {
                "processed_urls": len(report),
                "successful_competitions": sum(e["success"] for e in report),
            },
            ensure_ascii=False,
        )
    )
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
