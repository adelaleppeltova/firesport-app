"""Verify previously flagged duplicate pairs against the organizer's original PDFs."""
import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from bson import json_util
import pymupdf

from app.services.category_normalization import label_key
from app.services.category_source_rules import event_identity
from app.services.data_import import DataImporter
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file


@dataclass(frozen=True)
class PublishedList:
    file: str
    url: str
    pages: tuple[int, ...]
    rank_first: bool = False


STOVKY = "https://stovky.cz/"
OSH = "https://www.oshtrutnov.cz/wp-content/uploads/2025/04/"
PUBLISHED_LISTS = {
    ("2019-05-25", "Ostravská stovka", "Ostrava", "Muži"):
        PublishedList("ostrava-m", STOVKY + "ostrava_poruba/2019/stovky_muzi.pdf", (1, 2), rank_first=True),
    ("2019-05-25", "Ostravská stovka", "Ostrava", "Ženy"):
        PublishedList("ostrava-z", STOVKY + "ostrava_poruba/2019/stovky_dorost_zeny.pdf", (3,), rank_first=True),
    ("2020-06-27", "O pohár HVP, a.s.", "Třebíč", "Muži"):
        PublishedList("trebic-m", STOVKY + "trebic/2020/muzi_starsi_dorost.pdf", (1, 2)),
    ("2020-06-27", "O pohár HVP, a.s.", "Třebíč", "Ženy"):
        PublishedList("trebic-z", STOVKY + "trebic/2020/zeny_starsi_dorost.pdf", (1, 2)),
    ("2020-07-25", "Bludovská stovka", "Bludov", "Muži"):
        PublishedList("bludov-m", STOVKY + "bludov/2020/muzi_starsi_dorostenci.pdf", (1, 2)),
    ("2020-07-25", "Bludovská stovka", "Bludov", "Ženy"):
        PublishedList("bludov-z", STOVKY + "bludov/2020/zeny_starsi_dorostenky.pdf", (1, 2)),
    ("2025-04-26", "Dubenecké stovky 2025", "Hradec Králové", "Střední dorostenky"):
        PublishedList("dubenec-str", OSH + "Vysledky-Stredni-dorostenky.pdf", (1,)),
}
DUBENEC_YOUNGER = PublishedList("dubenec-ml", OSH + "Vysledky-Mladsi-dorostenky.pdf", (1,))


def published_lines(folder: Path, source: PublishedList):
    raw = (folder / f"{source.file}.pdf").read_bytes()
    result = []
    with pymupdf.open(stream=raw, filetype="pdf") as document:
        for page in source.pages:
            text = document[page - 1].get_text(sort=True)
            result.extend((page, number, line) for number, line in enumerate(text.splitlines(), start=1))
    return sha256(raw).hexdigest(), result


def matches_published_row(identity: dict, line: str, *, rank_first: bool) -> bool:
    cells = line.split()
    if len(cells) < 3 or identity["start_number"] is None or not all(identity["name"]):
        return False
    bib = cells[1] if rank_first else cells[0]
    if not bib.isdecimal() or int(bib) != int(identity["start_number"]):
        return False
    rank = cells[0] if rank_first else cells[-1].rstrip(".")
    if identity["rank"] is not None and (not rank.isdecimal() or int(rank) != identity["rank"]):
        return False
    text = f" {label_key(line)} "
    if not all(f" {label_key(value)} " in text for value in identity["name"]):
        return False
    expected_times = [value for _, value, status, _ in identity["times"] if value is not None and status == "valid"]
    if identity["final_time"] is not None and identity["final_time_status"] == "valid":
        expected_times.append(identity["final_time"])
    times = [float(value.replace(",", ".")) for value in re.findall(r"\b\d{1,3}[.,]\d{1,3}\b", line)]
    return Counter(expected_times) == Counter(value for value in times if value not in (0, 998, 999, 999.99))


def review_pairs(snapshot: dict, candidates: list[dict], pdf_dir: Path) -> dict:
    sources = {
        selector: (source, *published_lines(pdf_dir, source)) for selector, source in PUBLISHED_LISTS.items()
    }
    _, younger = published_lines(pdf_dir, DUBENEC_YOUNGER)
    verified = []
    for cluster in candidates:
        if len(cluster["result_ids"]) != 2 or cluster["distinct_verified_lists"]:
            continue
        first, second = (snapshot["results"][identifier] for identifier in cluster["result_ids"])
        if first["competition"] != second["competition"]:
            continue
        event = event_identity(snapshot["competitions"][first["competition"]])
        votes = []
        for row, other in ((first, second), (second, first)):
            category = snapshot["categories"][row["category"]]["name"]
            listing = sources.get((*event, category))
            if not listing:
                continue
            source, digest, lines = listing
            identity = DataImporter._row_identity(row)
            hits = [(page, number) for page, number, line in lines
                    if matches_published_row(identity, line, rank_first=source.rank_first)]
            if len(hits) != 1:
                continue
            if source.file == "dubenec-str":
                if any(matches_published_row(identity, line, rank_first=False) for _, _, line in younger):
                    continue
                keep, copy = row, other
            else:
                other_category = snapshot["categories"][other["category"]]["name"]
                if other_category not in {"Muži a starší dorostenci", "Ženy a starší dorostenky"}:
                    continue
                keep, copy = other, row
            page, line = hits[0]
            votes.append({
                "keep": keep["_id"], "copy": copy["_id"], "keep_sha256": fingerprint(keep),
                "copy_sha256": fingerprint(copy), "source_url": source.url, "source_sha256": digest,
                "source_page": page, "text_line": line,
            })
        if len(votes) == 1:
            verified.append(votes[0])
    return {"version": 1, "duplicates": verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--candidate-report", required=True, type=Path)
    parser.add_argument("--pdf-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    snapshot = load_snapshot(args.snapshot)
    candidates = json_util.loads(args.candidate_report.read_text(encoding="utf-8"))["potential_duplicate_results"]
    result = review_pairs(snapshot, candidates, args.pdf_dir)
    with private_file(args.output) as handle:
        handle.write(json_util.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(f"Doložené páry {len(result['duplicates'])} / {len(candidates)}.")


if __name__ == "__main__":
    main()
