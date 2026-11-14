"""Storage layout and byte-preserving migration; no network or extraction changes."""

import copy
import json
from pathlib import Path
import pytest
from app.extraction.paths import resolve_path, StorageConflict, slug
from app.extraction.storage import save
from app.extraction.migrate import migrate
from app.tests.test_extraction import fixture_document


def result(
    url="https://pozarnisporty.cz/races/1034",
    name="STIMAX CUP 2026 - 4. (finálové) kolo - Chomutov",
    place="Chomutov",
    date="2026-09-19",
):
    data, audit = fixture_document()
    data["source_file"] = url
    data["competition"].update(name=name, place=place, date=date)
    return data, audit


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=3) + "\n", encoding="utf-8"
    )
    return path


def test_year_from_competition_not_generation(tmp_path):
    data, audit = result(date="2022-09-19")
    path = save(data, tmp_path, audit)
    assert path.parent.parent.name == "2022"
    assert path.name.startswith("2022-09-19-")
    assert "results" not in path.parts


def test_existing_custom_folder_by_metadata(tmp_path):
    data, _ = result()
    old = write(tmp_path / "2026/chomutov-stimax/komplet.json", data)
    assert resolve_path(data, tmp_path) == old


def test_empty_custom_folder_requires_event_and_place(tmp_path):
    folder = tmp_path / "2026/chomutov-stimax"
    folder.mkdir(parents=True)
    data, audit = result()
    assert save(data, tmp_path, audit).parent == folder


def test_create_ascii_folder_and_filename(tmp_path):
    data, audit = result(name="Šedesátky – Žďár nad Sázavou", place="Žďár nad Sázavou")
    path = save(data, tmp_path, audit)
    assert (
        path
        == tmp_path
        / "2026/sedesatky-zdar-nad-sazavou/2026-09-19-sedesatky-zdar-nad-sazavou.json"
    )
    assert slug("Říčany & Ústí!") == "ricany-usti"


def test_stimax_readable_filename_without_repeated_place_or_edition(tmp_path):
    data, audit = result()
    path = save(data, tmp_path, audit)
    assert path.name == "2026-09-19-stimax-cup-chomutov.json"


def test_reimport_same_url_updates_same_path_after_title_correction(tmp_path):
    data, audit = result()
    path = save(data, tmp_path, audit)
    data["competition"]["name"] = "Opravený název"
    assert save(data, tmp_path, audit) == path
    assert len(list(tmp_path.rglob("*.json"))) == 1
    assert json.loads(path.read_text())["competition"]["name"] == "Opravený název"


def test_filename_collision_uses_url_race_id(tmp_path):
    data, audit = result()
    first = save(data, tmp_path, audit)
    second = copy.deepcopy(data)
    second["source_file"] = "https://pozarnisporty.cz/races/9999"
    path = save(second, tmp_path, audit)
    assert path.parent == first.parent
    assert path.name == "2026-09-19-stimax-cup-chomutov-9999.json"
    assert save(second, tmp_path, audit) == path
    assert json.loads(first.read_text())["source_file"] == data["source_file"]


def test_same_place_different_competitions_do_not_share_folder(tmp_path):
    data, audit = result(name="Memoriál Jany Nové")
    first = save(data, tmp_path, audit)
    other, _ = result(url="https://pozarnisporty.cz/races/9999", name="Pohár starosty")
    second = save(other, tmp_path, audit)
    assert first.parent != second.parent
    assert first.exists() and second.exists()


def test_same_series_and_place_different_dates_get_distinct_folder(tmp_path):
    data, audit = result()
    first = save(data, tmp_path, audit)
    other, _ = result(url="https://pozarnisporty.cz/races/9999", date="2026-10-01")
    second = save(other, tmp_path, audit)
    assert first.parent != second.parent
    assert second.parent.name.endswith("-9999")


def test_place_only_empty_folder_is_ambiguous(tmp_path):
    (tmp_path / "2026/chomutov").mkdir(parents=True)
    with pytest.raises(StorageConflict, match="Ambiguous"):
        data, audit = result()
        save(data, tmp_path, audit)
    assert not list(tmp_path.rglob("*.json"))


def test_empty_folder_with_another_event_is_not_reused(tmp_path):
    (tmp_path / "2026/nocni-stovka-chomutov").mkdir(parents=True)
    data, audit = result(name="Stovka", place="Chomutov")
    assert save(data, tmp_path, audit).parent.name == "stovka-chomutov"


def test_ambiguous_metadata_folders_block_write(tmp_path):
    data, audit = result()
    write(tmp_path / "2026/first/a.json", data)
    write(tmp_path / "2026/second/b.json", data)
    with pytest.raises(StorageConflict, match="Multiple files"):
        save(data, tmp_path, audit)


@pytest.mark.parametrize("date", [None, "2026-02-30", "unknown"])
def test_unknown_date_does_not_create_final_directory(tmp_path, date):
    data, _ = result(date=date)
    with pytest.raises(StorageConflict, match="date"):
        resolve_path(data, tmp_path / "data")
    assert not (tmp_path / "data").exists()


def test_forbidden_results_output(tmp_path):
    data, audit = result()
    with pytest.raises(StorageConflict, match="forbidden"):
        save(data, tmp_path / "results", audit)
    assert not (tmp_path / "results").exists()


def test_migration_preserves_original_bytes_and_removes_empty_legacy_folder(tmp_path):
    data, _ = result()
    source = write(tmp_path / "results/legacyhash.json", data)
    raw = source.read_bytes()
    preview = migrate(tmp_path)
    assert preview[0]["status"] == "planned" and source.read_bytes() == raw
    report = migrate(tmp_path, apply=True)
    target = Path(report[0]["target"])
    assert report[0]["status"] == "moved"
    assert target.read_bytes() == raw
    assert not (tmp_path / "results").exists()


def test_migration_conflict_preserves_both_files(tmp_path):
    data, _ = result()
    source = write(tmp_path / "results/legacyhash.json", data)
    old = copy.deepcopy(data)
    old["warnings"].append("Different existing version")
    target = write(tmp_path / "2026/chomutov-stimax/komplet.json", old)
    before = (source.read_bytes(), target.read_bytes())
    report = migrate(tmp_path, apply=True)
    assert report[0]["status"] == "conflict"
    assert (source.read_bytes(), target.read_bytes()) == before
    assert len(list(tmp_path.rglob("*.json"))) == 2


def test_same_source_in_wrong_year_requires_resolution(tmp_path):
    data, audit = result()
    write(tmp_path / "2025/chomutov-stimax/komplet.json", data)
    with pytest.raises(StorageConflict, match="different competition year"):
        save(data, tmp_path, audit)


def test_unrelated_invalid_historical_json_does_not_block_current_year(tmp_path):
    path = tmp_path / "2022/old/incomplete.json"
    path.parent.mkdir(parents=True)
    path.write_text("")
    data, audit = result()
    assert save(data, tmp_path, audit).parent.parent.name == "2026"
    assert path.read_bytes() == b""


def test_unknown_date_cli_retains_pending_document(tmp_path, monkeypatch):
    from app.extraction import __main__ as cli

    data, audit = result(date=None)
    monkeypatch.setattr(
        cli,
        "extract",
        lambda *a, **kw: (data["competition"], [], ["Unknown date"], audit),
    )
    assert (
        cli.main(
            [
                data["source_file"],
                "--output",
                str(tmp_path / "data"),
                "--diagnostics",
                str(tmp_path / "diagnostics"),
            ]
        )
        == 1
    )
    pending = list((tmp_path / "diagnostics").glob("*/pending.json"))
    assert len(pending) == 1
    assert json.loads(pending[0].read_text())["competition"]["date"] is None
    assert not (tmp_path / "data").exists()


def test_identical_existing_migration_target_is_reported_without_removal(tmp_path):
    data, _ = result()
    original = write(tmp_path / "results/hash.json", data)
    existing = write(tmp_path / "2026/chomutov-stimax/komplet.json", data)
    report = migrate(tmp_path, apply=True)
    assert report[0]["status"] == "conflict"
    assert "identical bytes=True" in report[0]["error"]
    assert original.read_bytes() == existing.read_bytes()


def test_metadata_name_with_or_without_place_identifies_existing_event(tmp_path):
    data, audit = result(name="Český pohár", place="Budíkovice")
    old = copy.deepcopy(data)
    old["competition"]["name"] = "Český pohár – Budíkovice"
    old["source_file"] = "https://example.org/results.pdf"
    write(tmp_path / "2026/budikovice/komplet.json", old)
    # Existing same-event result must be reported rather than duplicated.
    with pytest.raises(StorageConflict, match="same competition"):
        save(data, tmp_path, audit)
    assert len(list(tmp_path.rglob("*.json"))) == 1


def test_event_only_empty_folder_is_not_duplicated_automatically(tmp_path):
    (tmp_path / "2026/stimax-cup").mkdir(parents=True)
    data, audit = result()
    with pytest.raises(StorageConflict, match="Ambiguous"):
        save(data, tmp_path, audit)
