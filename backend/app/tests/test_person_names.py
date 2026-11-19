from app.extraction.participants import split_name
from app.models.result import ImportedAthleteData
from app.person_names import name_issues, normalize_person_name


def test_name_format_keeps_diacritics_particles_and_mixed_case():
    assert normalize_person_name("  jur\u030c ina ") == "juř ina"
    assert normalize_person_name("  jur\u030cina ") == "Juřina"
    assert normalize_person_name("  van   der Meer ") == "van der Meer"
    assert normalize_person_name("McDonald") == "McDonald"
    assert normalize_person_name("Černá-Nováková") == "Černá-Nováková"
    assert name_issues({"first_name": "Jan", "last_name": "NOVÁK"}) == ["verify_last_name"]


def test_source_segmentation_keeps_ambiguity_and_api_accepts_explicit_null():
    warnings = []
    assert split_name("Novák Jan Pavel", warnings, "řádek", surname_first=True) == (None, None)
    assert "Novák Jan Pavel" in warnings[0]
    assert split_name("de la Cruz, Jana Marie", [], "řádek") == ("Jana Marie", "de la Cruz")
    imported = ImportedAthleteData.model_validate({"first_name": None, "last_name": " "})
    assert imported.first_name == imported.last_name == ""
