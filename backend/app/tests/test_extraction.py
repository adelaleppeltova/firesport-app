"""Offline regression tests for source extraction and publication guards."""

import copy
import json
from pathlib import Path
from unittest.mock import Mock
import pytest
from jsonschema import ValidationError
from app.extraction.times import parse_time, final_time
from app.extraction.penalties import assign_reasons
from app.extraction.participants import fscode, split_name, profile_year
from app.extraction.metadata import discipline, category_discipline, parse_date
from app.extraction.fetch import source_type, Fetcher
from app.extraction.html import parse_html
from app.extraction.pdf import tables_to_html
from app.extraction.storage import document, save, summary
from app.extraction.validation import validate
from app.extraction.__main__ import main
from bs4 import BeautifulSoup

URL = "https://pozarnisporty.cz/races/1034"
FIXTURE = Path(__file__).parent / "fixtures/extraction/race-1034.html"


@pytest.mark.parametrize(
    "raw,time,status",
    [
        ("15,42", 15.42, "valid"),
        ("15.420", 15.42, "valid"),
        ("00:15.42", 15.42, "valid"),
        ("01:23.06", 83.06, "valid"),
        ("00:18.70 P", 18.7, "valid"),
        ("00:20.80 N", None, "invalid"),
        *[
            (v, None, "invalid")
            for v in (
                "999",
                "999,990",
                "998",
                "999990",
                "-1",
                "NP",
                "DNS",
                "DNF",
                "DSQ",
                "0:00-",
                "-",
                "",
                None,
            )
        ],
        ("16:35-", 16.35, "invalid"),
        ("18,42-", 18.42, "invalid"),
        ("16:35- N", None, "invalid"),
        ("01:23.06-", None, "invalid"),
        ("something", None, "invalid"),
        ("00:63.40", None, "invalid"),
    ],
)
def test_times(raw, time, status):
    assert parse_time(raw, []) == {"time": time, "status": status}


def test_absent_is_missing_but_blank_invalid():
    assert parse_time(None, [], absent=True)["status"] == "missing"
    assert parse_time(None, [])["status"] == "invalid"


def test_final_is_never_calculated():
    attempts = [parse_time("15", []), parse_time("14", [])]
    assert final_time(None, attempts, [], absent=True)["time"] is None
    warnings = []
    assert final_time("16", attempts, warnings)["time"] == 16
    assert warnings
    assert (
        final_time("30:00.00", [parse_time("NP", [])] * 2, [], placeholder=True)["time"]
        is None
    )
    assert final_time("30:00.00", attempts, [], placeholder=False)["time"] == 1800


@pytest.mark.parametrize(
    "raw,reasons",
    [
        ("1-rozpojeno", {1: "rozpojeno"}),
        ("1-kladina, 2-obouruč", {1: "kladina", 2: "obouruč"}),
        ("1-nedoběhl, 2-nedoběhl", {1: "nedoběhl", 2: "nedoběhl"}),
        ("2- rozdělovač", {2: "rozdělovač"}),
        ("2.rozpojeno", {2: "rozpojeno"}),
        (
            "1 – cíl v jiné dráze; 2-cíl+rozdělovač",
            {1: "cíl v jiné dráze", 2: "cíl+rozdělovač"},
        ),
        ("", {}),
        ("rozpojeno", {}),
        ("3-spoj", {}),
    ],
)
def test_penalties(raw, reasons):
    attempts = [{"try": i, **parse_time("-", [])} for i in (1, 2)]
    warnings = []
    assert assign_reasons(
        raw, attempts, warnings, "category / athlete / rank 9"
    ) == len(reasons)
    assert {
        t["try"]: t["invalid_reason"] for t in attempts if "invalid_reason" in t
    } == reasons
    if raw in {"rozpojeno", "3-spoj"}:
        assert raw in warnings[0]


def test_penalty_conflict_preserves_official_valid():
    attempts = [{"try": i, **parse_time("15 P", [])} for i in (1, 2)]
    warnings = []
    assign_reasons("2-spoj", attempts, warnings, "test")
    assert attempts[1]["status"] == "valid"
    assert attempts[1]["invalid_reason"] == "spoj"
    assert warnings


@pytest.mark.parametrize(
    "raw,expected", [(None, None), ("12", None), ("1234", 1234), ("00123", 123)]
)
def test_fs_code(raw, expected):
    warnings = []
    assert fscode(raw, warnings, "test") == expected
    if raw == "00123":
        assert warnings


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Van de Kamer Olivia", ("Olivia", "Van de Kamer")),
        ("Černá, Berenika Emílie", ("Berenika Emílie", "Černá")),
        ("Fraňková Alena (Středočeský) (6)", ("Alena", "Fraňková")),
        ("Nejasné Víceslovné Jméno", (None, None)),
    ],
)
def test_names(raw, expected):
    assert split_name(raw, [], "test", surname_first=True, site_suffix=True) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100m PHP", "100mPHP"),
        ("100mP", "100mPHP"),
        ("Štafeta 4×100 m", "4x100m"),
        ("Šedesátky", "60m"),
        ("Stovkování", "100m"),
        ("Požární útok", "PU"),
        ("Výstup na věž", "vez"),
        ("Ženy", None),
    ],
)
def test_disciplines(raw, expected):
    assert discipline(raw) == expected


def test_no_unverified_age_mapping():
    assert category_discipline("mladší žáci A", "", "") is None
    assert parse_date("19.09.2026 08:00") == "2026-09-19"
    assert parse_date("2026-02-30") is None


def fixture_document():
    competition, notes, warnings, audit = parse_html(FIXTURE.read_bytes(), URL)
    return document(URL, competition, notes, warnings), audit


def test_live_source_offline_regression():
    data, audit = fixture_document()
    validate(data, audit)
    counts = summary(data)
    assert (counts["categories"], counts["results"], counts["invalid_reasons"]) == (
        12,
        416,
        76,
    )
    rows = [r for c in data["competition"]["categories"] for r in c["results"]]
    assert sum(any("invalid_reason" in t for t in r["times"]) for r in rows) == 68
    first = rows[0]
    assert first["start_number"] == "6"  # source lane is 3
    assert first["district"] is None
    assert first["fscode"] is None
    assert first["birth_year"] is None  # never inferred from category
    assert first["times"][1]["time"] == 83.06
    assert first["rank"] == 1
    assert [c["discipline"] for c in data["competition"]["categories"]] == [
        "60m"
    ] * 8 + ["100m"] * 4
    assert (
        data["competition"]["name"] == "STIMAX CUP 2026 - 4. (finálové) kolo - Chomutov"
    )
    assert any(
        r["final_time"] is None and all(t["status"] == "invalid" for t in r["times"])
        for r in rows
    )


def minimal_table(name="Ženy", extra="", rows=None):
    rows = (
        rows
        or "<tr><td>7.</td><td>Jana</td><td>Nová</td><td>15,4</td><td>-</td><td>15,4</td><td>2-nenastoupil</td></tr>"
    )
    return f'<h2>{name}</h2><table data-discipline="100m"><tr><th>Pořadí</th><th>Křestní jméno</th><th>Příjmení</th><th>Čas 1</th><th>Čas 2</th><th>Výsl. čas</th><th>Důvod pen.</th></tr>{rows}</table>{extra}'


def test_unoccupied_and_final_block():
    page = minimal_table(extra=minimal_table("Finálový běh"))
    page = page.replace(
        "</table>",
        "<tr><td>8.</td><td>neobsazen</td><td></td><td></td><td></td><td></td><td></td></tr></table>",
    )
    competition, _, _, audit = parse_html(page, "https://example.org/race")
    assert len(competition["categories"]) == 1
    rows = competition["categories"][0]["results"]
    assert len(rows) == 1
    assert rows[0]["rank"] == 7
    assert rows[0]["times"][1]["invalid_reason"] == "nenastoupil"
    assert audit[0]["rows"] == 1


def test_advertised_unloaded_category_blocks_publication():
    page = minimal_table(
        extra='<input wire:model="selectedCategories.1"><input wire:model="selectedCategories.2">'
    )
    with pytest.raises(ValueError, match="advertised categories"):
        parse_html(page, URL)


def test_pagination_blocks_publication():
    with pytest.raises(ValueError, match="Pagination"):
        parse_html(minimal_table(extra='<a rel="next" href="?page=2">Next</a>'), URL)


def test_pdf_page_continuation_and_transition():
    header = [
        "Pořadí",
        "Křestní jméno",
        "Příjmení",
        "Čas 1",
        "Čas 2",
        "Výsl. čas",
        "Důvod pen.",
    ]
    row = ["7.", "Jana", "Nová", "15,4", "-", "15,4", "2-spoj"]
    pages = [
        {"tables": [{"category": "Ženy", "rows": [header, row]}], "result_like": True},
        {
            "tables": [
                {
                    "category": None,
                    "rows": [header, ["8.", "Marie", "Jiná", "17", "18", "17", ""]],
                }
            ],
            "result_like": True,
        },
        {"tables": [{"category": "Muži", "rows": [header, row]}], "result_like": True},
    ]
    competition, _, _, _ = parse_html(
        tables_to_html(pages), "https://example.org/result.pdf"
    )
    assert [len(c["results"]) for c in competition["categories"]] == [2, 1]


def test_missing_pdf_tables_rejected():
    with pytest.raises(ValueError, match="without extracted tables"):
        tables_to_html([{"tables": [], "result_like": True}])


def test_profile_year_only():
    assert (
        profile_year(
            BeautifulSoup(
                "<div><div>Narozen:</div><div>2018</div></div>", "html.parser"
            )
        )
        == 2018
    )
    assert profile_year(BeautifulSoup("<p>category 2018</p>", "html.parser")) is None


@pytest.mark.parametrize(
    "content,expected",
    [(b"%PDF-1.7", "pdf"), (b"<!DOCTYPE html><html></html>", "html")],
)
def test_content_detection(content, expected):
    assert source_type(content) == expected


def test_idempotent_and_reduction_guard(tmp_path):
    data, audit = fixture_document()
    path = save(data, tmp_path, audit)
    before = path.read_bytes()
    data["generated_at"] = "2026-11-14T10:00:00Z"
    assert save(data, tmp_path, audit) == path
    assert path.read_bytes() == before
    removed = data["competition"]["categories"][0]["results"].pop()
    audit[0]["numbered_reasons"] -= sum("invalid_reason" in t for t in removed["times"])
    audit[0]["rows"] -= 1
    with pytest.raises(ValueError, match="remove existing"):
        save(data, tmp_path, audit)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(unexpected=True),
        lambda d: d.update(generated_at="2026-11-13T10:00:00+01:00"),
        lambda d: d["competition"].update(date="2026-02-30"),
        lambda d: d["competition"]["categories"][0].update(discipline="unknown"),
        lambda d: d["competition"]["categories"][0]["results"][0]["times"][0].update(
            invalid_reason=None
        ),
        lambda d: d["competition"]["categories"][0]["results"][0]["times"].append(
            {"try": 3, "time": 15, "status": "valid"}
        ),
    ],
)
def test_strict_schema(mutation):
    data, _ = fixture_document()
    mutation(data)
    with pytest.raises(ValidationError):
        validate(data)


def test_penalty_audit_detects_loss():
    data, audit = fixture_document()
    audit[0]["numbered_reasons"] += 1
    with pytest.raises(ValueError, match="penalty audit"):
        validate(data, audit)


def test_failed_import_writes_diagnostics_only(tmp_path, monkeypatch):
    monkeypatch.setattr(Fetcher, "get", Mock(side_effect=OSError("unavailable")))
    assert (
        main(
            [
                "https://example.org/fail",
                "--output",
                str(tmp_path / "results"),
                "--diagnostics",
                str(tmp_path / "diagnostics"),
            ]
        )
        == 1
    )
    assert not (tmp_path / "results").exists()
    report = json.loads(
        next((tmp_path / "diagnostics").glob("*/report.json")).read_text()
    )
    assert report["success"] is False


def test_validation_duplicate_attempt():
    data, _ = fixture_document()
    data = copy.deepcopy(data)
    attempts = data["competition"]["categories"][0]["results"][0]["times"]
    attempts[1]["try"] = 1
    with pytest.raises(ValueError, match="Duplicate attempt"):
        validate(data)


def test_team_suffix_split_only_with_explicit_columns():
    from app.extraction.participants import split_team_times

    assert split_team_times("Moravský Beroun 24,050 999,990", "", "") == (
        "Moravský Beroun",
        "24,050",
        "999,990",
        True,
    )
    assert split_team_times("Moravský Beroun 24,050 999,990", "25", "")[3] is False
    html = "<h2>Muži</h2><table><tr><th>Pořadí</th><th>Křestní jméno</th><th>Příjmení</th><th>SDH/tým</th><th>Čas 1</th><th>Čas 2</th></tr><tr><td>1</td><td>Jan</td><td>Nový</td><td>Moravský Beroun 24,050 999,990</td><td></td><td></td></tr></table>"
    competition, _, _, _ = parse_html(html, "https://example.org")
    row = competition["categories"][0]["results"][0]
    assert row["team"] == "Moravský Beroun"
    assert row["times"][0]["time"] == 24.05
    assert row["times"][1]["status"] == "invalid"


def test_multiple_given_names_explicit_columns():
    competition, _, _, _ = parse_html(
        minimal_table().replace("Jana", "Berenika Emílie").replace("Nová", "Černá"),
        "https://example.org",
    )
    row = competition["categories"][0]["results"][0]
    assert row["first_name"] == "Berenika Emílie"
    assert row["last_name"] == "Černá"


def test_two_invalid_attempts_remain_distinct():
    page = (
        minimal_table()
        .replace("15,4", "NP")
        .replace("2-nenastoupil", "1-spoj, 2-nenastoupil")
    )
    competition, _, _, audit = parse_html(page, "https://example.org")
    row = competition["categories"][0]["results"][0]
    assert [t["status"] for t in row["times"]] == ["invalid", "invalid"]
    assert [t["invalid_reason"] for t in row["times"]] == ["spoj", "nenastoupil"]
    assert row["final_status"] == "invalid"
    assert row["final_time"] is None
    assert audit[0]["numbered_reasons"] == 2


def test_pdf_extraction_inspects_all_pages(tmp_path, monkeypatch):
    import pdfplumber
    import pymupdf
    from app.extraction.pdf import parse_pdf

    header = [
        "Pořadí",
        "Křestní jméno",
        "Příjmení",
        "Čas 1",
        "Čas 2",
        "Výsl. čas",
        "Důvod pen.",
    ]
    pages = []
    for i in range(3):
        page = Mock(width=600)
        page.extract_text.return_value = "Závod: Český pohár\nMísto: Budíkovice\nDatum konání: 5.7.2025\nVýsledky Čas Pořadí"
        page.crop.return_value.extract_text.return_value = (
            "Kategorie: Ženy" if i < 2 else "Kategorie: Muži"
        )
        table = Mock(bbox=(0, 100, 500, 600))
        table.extract.return_value = [
            header,
            [str(i + 1), "Jana", "Nová", "15", "NP", "15", "2-spoj"],
        ]
        page.find_tables.return_value = [table]
        pages.append(page)
    from unittest.mock import MagicMock

    document = MagicMock()
    document.__enter__.return_value.pages = pages
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: document)
    rendered = MagicMock()
    monkeypatch.setattr(pymupdf, "open", lambda *a, **kw: rendered)
    competition, notes, _, audit = parse_pdf(
        b"fake", "https://example.org/results.pdf", tmp_path
    )
    assert [len(c["results"]) for c in competition["categories"]] == [2, 1]
    assert competition["name"] == "Český pohár – Budíkovice"
    assert competition["date"] == "2025-07-05"
    assert len(audit) == 2
    assert len(list(tmp_path.glob("page-*.txt"))) == 3
    assert "all 3 pages" in notes[0]


def test_ocr_all_pages_require_review(tmp_path, monkeypatch):
    import pdfplumber
    import pymupdf
    from unittest.mock import MagicMock
    from app.extraction.pdf import parse_pdf
    from app.extraction import ocr

    pages = [Mock(), Mock()]
    for page in pages:
        page.extract_text.return_value = ""
    source = MagicMock()
    source.__enter__.return_value.pages = pages
    monkeypatch.setattr(pdfplumber, "open", lambda *a, **kw: source)
    monkeypatch.setattr(pymupdf, "open", lambda *a, **kw: MagicMock())
    recognize = Mock(side_effect=ValueError("Tesseract unavailable"))
    monkeypatch.setattr(ocr, "recognize", recognize)
    with pytest.raises(ValueError, match="visual verification"):
        parse_pdf(b"fake", "https://example.org/results.pdf", tmp_path)
    assert recognize.call_count == 2
    assert len(json.loads((tmp_path / "ocr-review.json").read_text())["errors"]) == 2


def test_same_count_cannot_silently_replace_participant(tmp_path):
    data, audit = fixture_document()
    save(data, tmp_path, audit)
    data["competition"]["categories"][0]["results"][0]["start_number"] = "unrelated"
    with pytest.raises(ValueError, match="participant identities"):
        save(data, tmp_path, audit)


def test_profile_failure_cannot_erase_previously_known_year(tmp_path):
    data, audit = fixture_document()
    data["competition"]["categories"][0]["results"][0]["birth_year"] = 2018
    save(data, tmp_path, audit)
    data["competition"]["categories"][0]["results"][0]["birth_year"] = None
    with pytest.raises(ValueError, match="previously published birth_year"):
        save(data, tmp_path, audit)


def test_conflicting_document_disciplines_are_not_guessed():
    assert category_discipline("Ženy", "", "Disciplíny: 60 m a 100 m") is None


def test_missing_rank_column_is_null_not_calculated():
    page = minimal_table().replace("<th>Pořadí</th>", "").replace("<td>7.</td>", "")
    competition, _, warnings, _ = parse_html(page, "https://example.org")
    assert competition["categories"][0]["results"][0]["rank"] is None
    assert any("unavailable rank" in warning for warning in warnings)


def test_legacy_result_card_uses_explicit_age_label():
    html = """
    <div><div class="text-red-600"><div>dívky - věk: 13 - 14</div>
    <div>závodníků v kategorii: 1</div></div><div>
    <table><tr><th>Poř.</th><th>Jméno</th><th>Čas 1</th></tr>
    <tr><td>1</td><td>Nová Jana (12)</td><td>15.00 P</td></tr></table>
    </div></div>
    """
    competition, _, _, audit = parse_html(html, "https://pozarnisporty.cz/races/382")
    assert competition["categories"][0]["name"] == "dívky - věk: 13 - 14"
    assert audit[0]["rows"] == 1


def test_shared_reason_for_explicitly_numbered_attempts():
    attempts = [{"status": "invalid"}, {"status": "invalid"}]
    warnings = []
    assert assign_reasons("1, 2 - nenastoupil - úraz", attempts, warnings, "row") == 2
    assert [a["invalid_reason"] for a in attempts] == ["nenastoupil - úraz"] * 2
    assert warnings == []


def test_empty_legacy_category_is_not_a_participant():
    html = """
    <div><div class="text-red-600"><div>ženy - věk: 17 - 18</div>
    <div>závodníků v kategorii: 0</div></div><div>
    <table><tr><th>Poř.</th><th>Jméno</th><th>Čas 1</th></tr>
    <tr><td colspan="3">V kategorii není nikdo přihlášen</td></tr></table>
    </div></div>
    """
    competition, _, _, audit = parse_html(html, "https://pozarnisporty.cz/races/1239")
    assert competition["categories"][0]["results"] == []
    assert audit[0]["rows"] == 0


def test_compact_team_timing_uses_published_results_and_ignores_roster(tmp_path):
    from app.extraction.__main__ import extract

    url = "https://pozarnisporty.cz/races/927"
    data = FIXTURE.with_name("compact-team-results.html").read_bytes()
    fetcher = Mock()
    fetcher.get.return_value = (data, url)
    competition, notes, warnings, audit = extract(url, fetcher, tmp_path)
    validate(document(url, competition, notes, warnings), audit)
    category, = competition["categories"]
    assert category["name"] == "přípravka"
    first, second = category["results"]
    assert first["team"] == "Rokytnice nad Rokytnou 11 (Třebíč) [54]"
    assert all(first[field] is None for field in ("first_name", "last_name", "start_number", "district"))
    assert first["final_time"] == 78.71
    assert first["times"][1]["time"] == 87.58
    assert second["rank"] == 3
    assert second["final_time"] is None
    assert second["times"] == [
        {"try": 1, "status": "invalid", "time": None, "invalid_reason": "N-kužel"},
        {"try": 2, "status": "invalid", "time": None},
    ]


def test_compact_team_timing_rejects_mixed_layout():
    from app.extraction.team_html import parse_team_html

    data = FIXTURE.with_name("compact-team-results.html").read_bytes()
    data = data.replace(b"</main>", b"<table><tr><th>Po&#345;.</th><th>Body</th></tr></table></main>")
    with pytest.raises(ValueError, match="Mixed or unsupported team table"):
        parse_team_html(data)


def test_compact_team_timing_rejects_whole_minutes_encoding_rank():
    from app.extraction.team_html import parse_team_html

    data = FIXTURE.with_name("compact-team-results.html").read_bytes()
    start = data.index(b"<tbody>")
    end = data.index(b"</tbody>", start)
    rows = "".join(
        f"<tr><td>{i}.</td><td>Team {i}</td><td>00:00:00.00</td>"
        f"<td>00:0{i}:00.00 (P)</td><td></td><td>00:00:00.00 (P)</td><td></td><td>0</td></tr>"
        for i in range(1, 4)
    )
    shaped = data[:start] + b"<tbody>" + rows.encode() + data[end:]
    with pytest.raises(ValueError, match="encode rank"):
        parse_team_html(shaped)


def test_site_zero_times_are_unmeasured_placeholders():
    html = b"""
    <main><div class="text-normal">TFA</div>
    <table><caption>Muzi</caption>
    <tr><th>Po&#345;.</th><th>Jm&eacute;no</th><th>V&yacute;sl. &#269;as</th><th>&#268;as 1</th></tr>
    <tr><td>4.</td><td>Novak Jan</td><td>00:00.00</td><td>00:00.00</td></tr>
    </table></main>
    """
    competition, _, warnings, _ = parse_html(html, URL)
    row = competition["categories"][0]["results"][0]
    assert row["rank"] == 4
    assert row["final_time"] is None and row["final_status"] == "invalid"
    assert row["times"][0]["time"] is None
    assert any("site zero time placeholder" in warning for warning in warnings)


def test_compact_team_timing_excludes_unscored_registration():
    from app.extraction.team_html import parse_team_html

    fixture = FIXTURE.with_name("compact-team-results.html").read_bytes()
    registration = (
        b"<tr><td></td><td>Unscored team</td><td>00:00:00.00</td><td>00:00:00.00 (P)</td>"
        b"<td></td><td>00:00:00.00 (P)</td><td></td><td>0</td></tr>"
    )
    competition, _, _, audit = parse_team_html(fixture.replace(b"</tbody>", registration + b"</tbody>"))
    assert len(competition["categories"][0]["results"]) == audit[0]["rows"] == 2


def test_checkpoint_timing_keeps_official_finish_and_leaves_attempts_missing(tmp_path):
    from app.extraction.__main__ import extract

    url = "https://pozarnisporty.cz/races/1188"
    fetcher = Mock()
    fetcher.get.return_value = (FIXTURE.with_name("checkpoint-results.html").read_bytes(), url)
    competition, notes, warnings, audit = extract(url, fetcher, tmp_path)
    validate(document(url, competition, notes, warnings), audit)
    category, = competition["categories"]
    assert category["name"] == "MLADŠÍ" and category["discipline"] is None
    first, second = category["results"]
    assert first["final_time"] == 2118 and first["rank"] == 1
    assert first["times"] == [
        {"try": 1, "status": "missing", "time": None},
        {"try": 2, "status": "missing", "time": None},
    ]
    assert first["start_number"] is None and first["district"] is None
    assert second["final_time"] is None and second["rank"] == 4


def test_team_stream_times_do_not_become_overall_attempts(tmp_path):
    from app.extraction.__main__ import extract

    url = "https://pozarnisporty.cz/races/1075"
    fetcher = Mock()
    fetcher.get.return_value = (FIXTURE.with_name("stream-results.html").read_bytes(), url)
    competition, notes, warnings, audit = extract(url, fetcher, tmp_path)
    validate(document(url, competition, notes, warnings), audit)
    category, = competition["categories"]
    assert category["discipline"] == "PU"
    first, second = category["results"]
    assert first["rank"] == 2 and first["final_time"] == 23.10
    assert first["times"] == second["times"] == [
        {"try": 1, "status": "missing", "time": None},
        {"try": 2, "status": "missing", "time": None},
    ]
    assert second["final_time"] is None and second["final_status"] == "invalid"
    assert any("left stream note for try 1: N-nesestříknuto" in w for w in warnings)


def test_compact_team_timing_skips_ranked_zero_time_roster():
    from app.extraction.team_html import parse_team_html

    fixture = FIXTURE.with_name("compact-team-results.html").read_bytes()
    start = fixture.index(b"<tbody>")
    end = fixture.index(b"</tbody>", start)
    ranked_placeholder = (
        b"<tr><td>1.</td><td>Team</td><td>-----</td><td>00:00:00.00 (N)</td>"
        b"<td></td><td>00:00:00.00 (P)</td><td></td><td>0</td></tr>"
    )
    with pytest.raises(ValueError, match="No published compact team results"):
        parse_team_html(fixture[:start] + b"<tbody>" + ranked_placeholder + fixture[end:])


def test_implausible_published_birth_year_is_retained_as_null():
    html = b"""
    <main><div class="text-normal">TFA</div>
    <div id="start"><div>Start:</div><div>06.09.2026</div></div>
    <table><caption>Muzi</caption>
    <tr><th>Po&#345;.</th><th>Jm&eacute;no</th><th>Rok narozen&iacute;</th><th>V&yacute;sl. &#269;as</th><th>&#268;as 1</th></tr>
    <tr><td>4.</td><td>Novak Jan</td><td>7777</td><td>18.36</td><td>00:00.00
 P</td></tr>
    </table></main>
    """
    competition, _, warnings, _ = parse_html(html, URL)
    row = competition["categories"][0]["results"][0]
    assert row["birth_year"] is None
    assert row["times"][0]["time"] is None
    assert row["final_time"] == 18.36
    assert any("implausible published birth year 7777" in warning for warning in warnings)


def test_preserve_source_full_name_when_html_order_does_not_resolve_multiple_words():
    page = (minimal_table()
            .replace("<th>Křestní jméno</th><th>Příjmení</th>", "<th>Jméno</th>")
            .replace("<td>Jana</td><td>Nová</td>", "<td>Souček Stanislav Gabriel</td>"))
    competition, notes, warnings, audit = parse_html(page, URL)
    data = document(URL, competition, notes, warnings)
    validate(data, audit)
    row = competition["categories"][0]["results"][0]
    assert row["source_full_name"] == "Souček Stanislav Gabriel"
    assert row["first_name"] is None and row["last_name"] is None


def test_grounded_multi_part_names_and_ambiguous_text():
    warnings = []
    assert split_name("Hudousková, Anna Marie", warnings, "test") == ("Anna Marie", "Hudousková")
    assert split_name("Anna Marie, Hudousková", warnings, "test", surname_first=False) == ("Anna Marie", "Hudousková")
    assert split_name("VAN DER BERG Anna Marie", warnings, "test", surname_first=True,
                      surname_uppercase=True) == ("Anna Marie", "VAN DER BERG")
    assert split_name("Anna Marie NOVÁKOVÁ SVOBODOVÁ", warnings, "test", surname_first=False,
                      surname_uppercase=True) == ("Anna Marie", "NOVÁKOVÁ SVOBODOVÁ")
    assert split_name("Hudousková Anna Marie", warnings, "test", surname_first=True) == (None, None)
    assert split_name("Jan Novák", warnings, "test") == (None, None)
    assert split_name(None, warnings, "test", surname_first=True) == (None, None)
    assert "Hudousková Anna Marie" in warnings[0]


def test_structured_result_headers_preserve_original_name_text_and_null():
    html = """
    <table data-discipline="100m"><caption>Ženy</caption>
    <tr><th>Pořadí</th><th>Příjmení</th><th>Jméno</th><th>Výsledný čas</th></tr>
    <tr><td>1</td><td>Nováková  Svobodová</td><td>Anna   Marie</td><td>16,00</td></tr>
    <tr><td>2</td><td>Hudousková</td><td></td><td>17,00</td></tr>
    </table>
    """
    race, _, warnings, _ = parse_html(html, "https://example.com/results")
    first, second = race["categories"][0]["results"]
    assert (first["first_name"], first["last_name"]) == ("Anna Marie", "Nováková Svobodová")
    assert first["source_full_name"] == "Nováková  Svobodová Anna   Marie"
    assert (second["first_name"], second["last_name"]) == (None, "Hudousková")
    assert second["source_full_name"] == "Hudousková"
    assert any("missing or invalid explicit name field" in w for w in warnings)


def test_linked_participant_text_ignores_comment_outside_link():
    html = """
    <table data-discipline="100m"><caption>Ženy</caption>
    <tr><th>Pořadí</th><th>Jméno</th><th>Výsledný čas</th></tr>
    <tr><td>1</td><td><a href="/user/card/8">Přerostová  Elena</a> (náhrada)</td><td>16,00</td></tr>
    </table>
    """
    race, _, _, _ = parse_html(html, URL)
    row, = race["categories"][0]["results"]
    assert row["source_full_name"] == "Přerostová  Elena"
    assert (row["first_name"], row["last_name"]) == ("Elena", "Přerostová")
