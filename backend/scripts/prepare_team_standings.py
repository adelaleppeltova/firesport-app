"""Read the six verified SH ČMS editions' team totals and named 100 m rows offline."""
import argparse
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
import re

from bson import json_util
import pymupdf

from app.services.category_normalization import label_key
from app.services.category_source_rules import event_identity, team_member_source
from scripts.migrate_category_catalog import fingerprint, load_snapshot, private_file

HEADINGS = {"st.č.", "Suma", "Poř.", "Pokus", "SDH"}
TIME_TOKEN = r"\d+[,.]\d{2}|DNF|DNS|NP|DSQ"


def time_token(token: str) -> tuple[float | None, str]:
    if re.fullmatch(r"\d+[,.]\d{2}", token):
        return float(token.replace(",", ".")), "valid"
    if token in {"DNF", "DNS", "NP", "DSQ"}:
        return None, "invalid"
    raise ValueError(f"Neznámý publikovaný čas {token!r}.")


def read_total_rows(document):
    headers = {}
    output = []
    for number, page in enumerate(document, 1):
        words = [(pymupdf.Rect(*word[:4]) * page.rotation_matrix, word[4]) for word in page.get_text("words")]
        headers.update((text, rectangle) for rectangle, text in words if text in HEADINGS)
        if set(headers) != HEADINGS:
            raise ValueError("Týmové listině chybí záhlaví.")
        start, total, rank = (headers[name] for name in ("st.č.", "Suma", "Poř."))
        ranks = [(rect, text) for rect, text in words if rect.y0 > start.y0 + 7
                 and rank.x0 - 4 <= rect.x0 <= rank.x0 + 21 and re.fullmatch(r"\d{1,2}", text)]
        for rect, position in sorted(ranks, key=lambda row: row[0].y0):
            def cells(left, right, tolerance=6):
                return [text for word, text in sorted(words, key=lambda pair: (pair[0].x0, pair[0].y0))
                        if left <= word.x0 < right and abs(word.y0 - rect.y0) <= tolerance]
            bib = cells(start.x0 - 3, start.x0 + 19)
            name = " ".join(cells(start.x0 + 18, headers["Pokus"].x0 - 4, 16)) or None
            tokens = cells(total.x0 - 5, rank.x0 - 7)
            if len(bib) != 1 or not bib[0].isdigit() or len(tokens) != 1:
                raise ValueError(f"Nerozpoznaný týmový řádek na stránce {number}.")
            value, status = time_token(tokens[0])
            if name is None and status == "valid":
                raise ValueError("Platný týmový součet nemá jméno družstva.")
            output.append({"source_number": int(bib[0]), "name": name, "rank": int(position),
                           "total_time": value, "total_status": status, "source_page": number,
                           "source_total": tokens[0]})
    if len(output) != 15 or {line["source_number"] for line in output} != set(range(1, 16)):
        raise ValueError("Nekompletní ověřovaná listina týmových součtů MČR.")
    return output


def read_member_rows(document):
    rows = {}
    for number, page in enumerate(document, 1):
        for line in page.get_text(sort=True).splitlines():
            if match := re.match(r"\s*(\d+)\.?\s+(\d+)\s+(\S.*)", line):
                key = tuple(map(int, match.groups()[:2]))
                cells = match[3].rsplit(maxsplit=3)
                if key in rows or len(cells) != 4:
                    raise ValueError(f"Nerozpoznaný řádek člena na stránce {number}.")
                rows[key] = number, cells
    return rows


def get_source(folder, year, kind, sex):
    matches = list(folder.glob(f"{year}-{kind}-*{sex}*.pdf"))
    if kind == "list":
        matches = [path for path in matches if "100" in path.name and "4x100" not in path.name]
    if len(matches) != 1:
        raise ValueError(f"Chybí jednoznačný dokument {year}/{kind}/{sex}.")
    path = matches[0]
    raw = path.read_bytes()
    source = {"source_url": path.with_suffix(".pdf.url").read_text().strip(),
              "source_sha256": sha256(raw).hexdigest()}
    reader = read_total_rows if kind == "total" else read_member_rows
    with pymupdf.open(stream=raw, filetype="pdf") as document:
        data = reader(document)
    return source, data


def build_evidence(db, pdf_dir):
    scopes = defaultdict(list)
    for row in db["results"].values():
        category = db["categories"].get(row.get("category")) or {}
        event = db["competitions"].get(row.get("competition")) or {}
        key = label_key(category.get("name"))
        if team_member_source(key, category.get("discipline"), event):
            scopes[row["competition"], key].append(row)

    evidence = []
    for (competition, key), rows in sorted(scopes.items(), key=lambda pair: (str(pair[0][0]), pair[0][1])):
        year = event_identity(db["competitions"][competition])[0][:4]
        sex = "dorci" if key == "dorostenci" else "dorky"
        totals_source, totals = get_source(pdf_dir, year, "total", sex)
        member_source, members = get_source(pdf_dir, year, "list", sex)
        names = {label_key(total["name"]): total["source_number"] for total in totals if total["name"]}
        if len(names) != sum(total["name"] is not None for total in totals):
            raise ValueError("Nejednoznačný název družstva.")
        proofs = []
        used = set()
        for row in sorted(rows, key=lambda item: str(item["_id"])):
            bib, rank = int(row["start_number"]), row["rank"]
            page, cells = members[rank, bib]
            if (rank, bib) in used:
                raise ValueError(f"Více importovaných běhů odpovídá řádku {rank}/{bib}.")
            used.add((rank, bib))
            published_name, published_team = re.split(r"\s{2,}", cells[0].strip(), maxsplit=1)
            team_key = label_key(row["team"])
            result_time, status = time_token(cells[3])
            if (not team_key or label_key(published_team) != team_key or not published_name.strip()
                    or (result_time, status) != (row["final_time"], row["final_time_status"])):
                raise ValueError(f"Nesoulad oficiální listiny člena {row['_id']}.")
            attempts = []
            for attempt, token in enumerate(cells[1:3], 1):
                value, status = time_token(token)
                attempts.append({"attempt": attempt, "time": value, "status": status})
            # The raw imported row and its penalties stay intact. The display
            # uses the explicitly published attempt cells from the official PDF.
            person = row.get("imported_athlete") or {}
            old_name = " ".join(person.get(field) or "" for field in ("first_name", "last_name"))
            proofs.append({
                "id": row["_id"], "row_sha256": fingerprint(row), "team_number": names[team_key],
                "source_page": page, "published_attempts": attempts,
                **({"published_name": published_name}
                   if sorted(label_key(old_name).split()) != sorted(label_key(published_name).split()) else {}),
            })
        evidence.append({
            "competition": competition, "source_category_key": key,
            "totals_source": totals_source, "members_source": member_source,
            "totals": totals, "members": proofs,
            "unrepresented_source_rows": [
                {"rank": rank, "start_number": bib, "source_page": members[rank, bib][0],
                 "final_status": time_token(members[rank, bib][1][3])[1]}
                for rank, bib in sorted(set(members) - used)
            ],
        })
    return {"version": 1, "team_lists": evidence}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--pdf-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    evidence = build_evidence(load_snapshot(args.snapshot), args.pdf_dir)
    with private_file(args.output) as handle:
        handle.write(json_util.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    print(f"Ověřených týmových listin: {len(evidence['team_lists'])}.")


if __name__ == "__main__":
    main()
