"""Unit testy pro DataImporter – ověření chování quality_flag při importu.

Testována dvě klíčová kritéria:
A) compute_bounds_for_recompute se zavolá maximálně 1× při importu více výsledků.
B) compute_quality_flag se zavolá pro každý nově vložený výsledek.

Veškerá DB volání jsou mockována – testy nepotřebují běžící MongoDB.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from bson import ObjectId

from app.models.result import MatchStatus, QualityFlag


# ---------------------------------------------------------------------------
# Helpers pro tvorbu testovacích dat
# ---------------------------------------------------------------------------

def _make_result_data(start_number: int = 1) -> dict:
    """Minimální slovník odpovídající jednomu záznamu výsledku z JSON."""
    return {
        "first_name": "Jana",
        "last_name": "Testová",
        "fscode": 99900 + start_number,
        "team": "SDH Testov",
        "start_number": start_number,
        "final_time": 20.0,
        "final_status": "valid",
        "rank": start_number,
        "times": [],
    }


FAKE_CATEGORY_ID = str(ObjectId())
FAKE_COMPETITION_ID = str(ObjectId())
FAKE_ATHLETE_ID = str(ObjectId())


# ---------------------------------------------------------------------------
# Fixture: DataImporter s plně mockovaným DB prostředím
# ---------------------------------------------------------------------------

@pytest.fixture()
def importer_with_mocks():
    """
    Vrátí trojici (importer, mock_bounds, mock_quality_flag).

    Interní kolekce DataImporteru jsou patchovány tak, aby:
    - find_one na results vrátil None  → výsledek neexistuje → bude vložen
    - find_one na competitions vrátil dokument se 'date'
    - insert_one na results uspěl
    - decide_athlete_match vrátí jednoznačný match na FAKE_ATHLETE_ID
    """
    from app.services.data_import import DataImporter

    importer = DataImporter()

    # Mock competitions_collection.find_one
    fake_competition = {"_id": ObjectId(FAKE_COMPETITION_ID), "date": None}
    mock_comp_find = AsyncMock(return_value=fake_competition)

    # Mock results_collection.find_one → None (žádný duplicitní výsledek)
    mock_res_find = AsyncMock(return_value=None)

    # Mock results_collection.insert_one
    mock_res_insert = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    mock_athlete_insert = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    # Mock compute_bounds_for_recompute a compute_quality_flag
    fake_bounds: dict = {ObjectId(FAKE_CATEGORY_ID): (14.0, 40.0)}
    mock_bounds = AsyncMock(return_value=fake_bounds)
    mock_quality = AsyncMock(return_value=QualityFlag.ok)
    mock_match = AsyncMock(
        return_value={
            "match_status": MatchStatus.matched,
            "match_reason": "fscode",
            "matched_athlete": {"_id": ObjectId(FAKE_ATHLETE_ID)},
        }
    )

    with (
        patch("app.services.data_import.competitions_collection") as mock_comp_col,
        patch("app.services.data_import.results_collection") as mock_res_col,
        patch("app.services.data_import.compute_bounds_for_recompute", mock_bounds),
        patch("app.services.data_import.compute_quality_flag", mock_quality),
        patch("app.services.data_import.decide_athlete_match", mock_match),
        patch("app.services.data_import.athletes_collection") as mock_athletes_col,
    ):
        mock_comp_col.find_one = mock_comp_find
        mock_res_col.find_one = mock_res_find
        mock_res_col.insert_one = mock_res_insert
        mock_athletes_col.insert_one = mock_athlete_insert
        mock_athletes_col.update_one = AsyncMock(return_value=MagicMock())

        yield importer, mock_bounds, mock_quality


# ---------------------------------------------------------------------------
# Testy
# ---------------------------------------------------------------------------

class TestDataImporterQualityFlag:
    """Ověřuje integraci quality_flag v DataImporter._import_result."""

    def test_bounds_computed_once_for_multiple_results(self, importer_with_mocks):
        """compute_bounds_for_recompute se zavolá právě 1× i při importu více výsledků."""
        importer, mock_bounds, mock_quality = importer_with_mocks

        n_results = 4
        for i in range(n_results):
            asyncio.run(
                importer._import_result(
                    _make_result_data(i + 1), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID
                )
            )

        mock_bounds.assert_called_once(), (
            f"compute_bounds_for_recompute byl zavolán {mock_bounds.call_count}× (očekáváno 1×)"
        )

    def test_quality_flag_called_for_each_inserted_result(self, importer_with_mocks):
        """compute_quality_flag se zavolá pro každý nově vložený výsledek."""
        importer, mock_bounds, mock_quality = importer_with_mocks

        n_results = 3
        for i in range(n_results):
            asyncio.run(
                importer._import_result(
                    _make_result_data(i + 1), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID
                )
            )

        assert mock_quality.call_count == n_results, (
            f"compute_quality_flag byl zavolán {mock_quality.call_count}× (očekáváno {n_results}×)"
        )

    def test_bounds_cache_reused_across_calls(self, importer_with_mocks):
        """_bounds_cache importeru se po prvním výsledku nastaví a dále sdílí."""
        importer, mock_bounds, _ = importer_with_mocks

        assert importer._bounds_cache is None, "Cache má být na začátku None"

        asyncio.run(
            importer._import_result(_make_result_data(1), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID)
        )
        first_cache = importer._bounds_cache
        assert isinstance(first_cache, dict), "Cache má být dict po prvním výsledku"

        asyncio.run(
            importer._import_result(_make_result_data(2), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID)
        )
        assert importer._bounds_cache is first_cache, "Cache se nesmí přepsat při druhém výsledku"
        mock_bounds.assert_called_once()

    def test_quality_flag_value_set_on_result_doc(self, importer_with_mocks):
        """Hodnota quality_flag vrácená compute_quality_flag se zapíše do result_doc."""
        from app.services.data_import import DataImporter

        importer, _, mock_quality = importer_with_mocks
        mock_quality.return_value = QualityFlag.suspicious

        inserted_docs = []

        import app.services.data_import as di_module
        original_insert = di_module.results_collection.insert_one

        async def capture_insert(doc):
            inserted_docs.append(dict(doc))
            return MagicMock(inserted_id=ObjectId())

        with patch("app.services.data_import.results_collection.insert_one", side_effect=capture_insert):
            asyncio.run(
                importer._import_result(_make_result_data(1), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID)
            )

        assert len(inserted_docs) == 1
        assert inserted_docs[0].get("quality_flag") == QualityFlag.suspicious.value


def test_normalize_category_name_uses_sentence_case_with_hzs():
    from app.services.data_import import DataImporter

    assert (
        DataImporter._normalize_category_name("MLADŠÍ DOROSTENKY")
        == "Mladší dorostenky"
    )
    assert (
        DataImporter._normalize_category_name("MUŽI A STARŠÍ DOROSTENCI")
        == "Muži a starší dorostenci"
    )
    assert DataImporter._normalize_category_name("MUŽI HZS") == "Muži HZS"


def test_import_category_reuses_existing_case_variant():
    from app.services.data_import import DataImporter

    importer = DataImporter()
    existing_id = ObjectId()
    exact_find = AsyncMock(return_value=None)
    case_insensitive_find = AsyncMock(
        return_value={"_id": existing_id, "name": "Mladší Dorostenky"}
    )
    update_one = AsyncMock()
    insert_one = AsyncMock()

    with patch("app.services.data_import.categories_collection") as mock_categories:
        mock_categories.find_one = AsyncMock(
            side_effect=[exact_find.return_value, case_insensitive_find.return_value]
        )
        mock_categories.update_one = update_one
        mock_categories.insert_one = insert_one

        category_id = asyncio.run(importer._import_category("Mladší dorostenky"))

    assert category_id == str(existing_id)
    update_one.assert_awaited_once_with(
        {"_id": existing_id},
        {"$set": {"name": "Mladší dorostenky"}},
    )
    insert_one.assert_not_awaited()


def test_unmatched_result_creates_new_athlete_and_matches_result():
    from app.services.data_import import DataImporter

    importer = DataImporter()
    created_athlete_id = ObjectId()
    fake_competition = {"_id": ObjectId(FAKE_COMPETITION_ID), "date": None}

    with (
        patch("app.services.data_import.competitions_collection") as mock_comp_col,
        patch("app.services.data_import.results_collection") as mock_res_col,
        patch("app.services.data_import.athletes_collection") as mock_athletes_col,
        patch("app.services.data_import.compute_bounds_for_recompute", AsyncMock(return_value={})),
        patch("app.services.data_import.compute_quality_flag", AsyncMock(return_value=QualityFlag.ok)),
        patch(
            "app.services.data_import.decide_athlete_match",
            AsyncMock(
                return_value={
                    "match_status": MatchStatus.unmatched,
                    "match_reason": "no_match",
                    "matched_athlete": None,
                }
            ),
        ),
    ):
        mock_comp_col.find_one = AsyncMock(return_value=fake_competition)
        mock_res_col.find_one = AsyncMock(return_value=None)
        inserted_results = []

        async def capture_result_insert(doc):
            inserted_results.append(dict(doc))
            return MagicMock(inserted_id=ObjectId())

        mock_res_col.insert_one = AsyncMock(side_effect=capture_result_insert)
        mock_athletes_col.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=created_athlete_id)
        )

        asyncio.run(
            importer._import_result(_make_result_data(1), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID)
        )

    assert len(inserted_results) == 1
    assert inserted_results[0]["match_status"] == MatchStatus.matched.value
    assert inserted_results[0]["match_reason"] == "auto_created_from_unmatched"
    assert inserted_results[0]["athlete"] == created_athlete_id


def test_conflicting_name_only_identity_creates_new_athlete():
    from app.services.data_import import DataImporter

    importer = DataImporter()
    created_athlete_id = ObjectId()
    fake_competition = {"_id": ObjectId(FAKE_COMPETITION_ID), "date": None}

    with (
        patch("app.services.data_import.competitions_collection") as mock_comp_col,
        patch("app.services.data_import.results_collection") as mock_res_col,
        patch("app.services.data_import.athletes_collection") as mock_athletes_col,
        patch("app.services.data_import.compute_bounds_for_recompute", AsyncMock(return_value={})),
        patch("app.services.data_import.compute_quality_flag", AsyncMock(return_value=QualityFlag.ok)),
        patch(
            "app.services.data_import.decide_athlete_match",
            AsyncMock(
                return_value={
                    "match_status": MatchStatus.unmatched,
                    "match_reason": "name_match_conflicting_identity_create_new",
                    "matched_athlete": None,
                }
            ),
        ),
    ):
        mock_comp_col.find_one = AsyncMock(return_value=fake_competition)
        mock_res_col.find_one = AsyncMock(return_value=None)
        inserted_results = []

        async def capture_result_insert(doc):
            inserted_results.append(dict(doc))
            return MagicMock(inserted_id=ObjectId())

        mock_res_col.insert_one = AsyncMock(side_effect=capture_result_insert)
        mock_athletes_col.insert_one = AsyncMock(
            return_value=MagicMock(inserted_id=created_athlete_id)
        )

        asyncio.run(
            importer._import_result(_make_result_data(7), FAKE_CATEGORY_ID, FAKE_COMPETITION_ID)
        )

    assert len(inserted_results) == 1
    assert inserted_results[0]["match_status"] == MatchStatus.matched.value
    assert inserted_results[0]["match_reason"] == "auto_created_from_unmatched"
    assert inserted_results[0]["athlete"] == created_athlete_id
