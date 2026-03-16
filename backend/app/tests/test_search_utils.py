import re

from app.services.search_utils import build_diacritic_fuzzy_regex


def test_build_diacritic_fuzzy_regex_matches_plain_and_accented_variants():
    pattern = build_diacritic_fuzzy_regex("Sykora")

    assert re.search(pattern, "Sykora", re.IGNORECASE)
    assert re.search(pattern, "Sýkora", re.IGNORECASE)


def test_build_diacritic_fuzzy_regex_escapes_special_characters():
    pattern = build_diacritic_fuzzy_regex("2024-01.(test)")

    assert re.fullmatch(pattern, "2024-01.(test)", re.IGNORECASE)
