"""Unit testy pro quality_flag_service.determine_quality_flag.

Testovány 4 základní případy:
1. Čas ok – nepřekračuje ani absolutní, ani relativní hranici.
2. Absolutní hranice (příliš pomalý čas) → suspicious.
3. Absolutní hranice (příliš rychlý čas) → suspicious.
4. Relativní skok (> 25 % nad mediánem 5 výsledků) → suspicious.
5. Méně než 5 výsledků v historii – relativní pravidlo se neuplatní.
6. Status invalid → quality_flag = ok (bez ohledu na čas).
7. Čas None → quality_flag = ok.
8. Přesně na hranici / prahové hodnotě (hranice vs. uvnitř).
Per-category testy:
9. Percentilové bounds se liší pro dvě různé kategorie.
10. Relativní pravidlo bere historii jen ze stejné kategorie.
"""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

from bson import ObjectId

from app.models.result import QualityFlag
from app.services.quality_flag_service import (
    _compute_percentile_bounds,
    compute_quality_flag,
    determine_quality_flag,
)


# ---------------------------------------------------------------------------
# Pomocné konstanty
# ---------------------------------------------------------------------------

# Typické hranice pro testy: low=14.0, high=40.0
LOW = 14.0
HIGH = 40.0


# ---------------------------------------------------------------------------
# _compute_percentile_bounds
# ---------------------------------------------------------------------------

class TestComputePercentileBounds:
    """Ověřuje výpočet hranic z percentilů."""

    def test_empty_list_returns_abs_defaults(self):
        low, high = _compute_percentile_bounds([])
        assert low == 11.0
        assert high == 45.0

    def test_normal_data_within_abs_limits(self):
        times = list(range(14, 40))  # 14..39
        low, high = _compute_percentile_bounds(times)
        # Q01 může být přibližně 14 → low = max(11, ~14) = ~14
        # Q99 může být přibližně 39 → high = min(45, ~39) = ~39
        assert low >= 11.0
        assert high <= 45.0

    def test_abs_floor_applies_when_q01_too_low(self):
        """Pokud by Q01 byl 8 s (nerealistický), low musí být min. 11."""
        times = [8.0] * 5 + [20.0] * 95
        low, _ = _compute_percentile_bounds(times)
        assert low >= 11.0

    def test_abs_ceiling_applies_when_q99_too_high(self):
        """Pokud by Q99 byl 60 s, high musí být max. 45."""
        times = [20.0] * 95 + [60.0] * 5
        _, high = _compute_percentile_bounds(times)
        assert high <= 45.0


# ---------------------------------------------------------------------------
# determine_quality_flag – základní případy
# ---------------------------------------------------------------------------

class TestDetermineQualityFlag:

    # --- Případ 1: čas uvnitř hranic, bez relevantní historie ---
    def test_ok_within_bounds_no_history(self):
        """Validní čas uvnitř hranic, bez historie → ok."""
        flag = determine_quality_flag(
            time_seconds=20.0,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag == QualityFlag.ok

    # --- Případ 2: příliš pomalý čas (> high) → suspicious ---
    def test_suspicious_too_slow(self):
        """Čas výrazně over high → suspicious (absolutní hranice)."""
        _ = determine_quality_flag(
            time_seconds=45.0,  # == HIGH, tedy > HIGH je 45.1
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        # Přesně na high (HIGH=40.0) je ještě ok; 40.1 je suspicious
        flag_over = determine_quality_flag(
            time_seconds=40.1,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag_over == QualityFlag.suspicious

    # --- Případ 3: příliš rychlý čas (< low) → suspicious ---
    def test_suspicious_too_fast(self):
        """Čas pod low → suspicious (absolutní hranice)."""
        flag = determine_quality_flag(
            time_seconds=10.0,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag == QualityFlag.suspicious

    # --- Případ 4: relativní skok > 25 % → suspicious ---
    def test_suspicious_relative_jump(self):
        """Čas o více než 25 % nad mediánem posledních 5 výsledků → suspicious."""
        # Medián 5 výsledků = 20.0; 20.0 * 1.25 = 25.0; čas 26.0 > 25.0
        history = [19.0, 20.0, 20.0, 21.0, 22.0]  # medián = 20.0
        flag = determine_quality_flag(
            time_seconds=26.0,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=history,
        )
        assert flag == QualityFlag.suspicious

    # --- Případ 5: relativní pravidlo se neuplatní při < 5 výsledcích ---
    def test_ok_relative_rule_skipped_for_short_history(self):
        """Pokud sportovec má méně než 5 předchozích výsledků, relativní pravidlo se nespustí."""
        history = [19.0, 20.0, 21.0, 22.0]  # jen 4 výsledky
        flag = determine_quality_flag(
            time_seconds=26.0,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=history,
        )
        # Čas 26.0 je uvnitř (LOW, HIGH) → ok, i když by relativně byl suspicious
        assert flag == QualityFlag.ok

    # --- Případ 6: status invalid → vždy ok ---
    def test_ok_for_invalid_status(self):
        """Pro status invalid se quality_flag nepočítá (vracíme ok)."""
        flag = determine_quality_flag(
            time_seconds=99.0,  # absurdně pomalý čas
            final_time_status="invalid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag == QualityFlag.ok

    # --- Případ 7: čas None → vždy ok ---
    def test_ok_for_none_time(self):
        """Pro null čas vracíme ok."""
        flag = determine_quality_flag(
            time_seconds=None,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag == QualityFlag.ok

    # --- Případ 8: přesně na hranici → ok (hranice je exkluzivní pro suspicious) ---
    def test_ok_exactly_on_bounds(self):
        """Čas přesně roven low nebo high je stále ok (< low resp. > high)."""
        flag_low = determine_quality_flag(
            time_seconds=LOW,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        flag_high = determine_quality_flag(
            time_seconds=HIGH,
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=[],
        )
        assert flag_low == QualityFlag.ok
        assert flag_high == QualityFlag.ok

    # --- Případ 9: relativní skok přesně 25 % → ok (pravidlo: > 1.25×medián) ---
    def test_ok_relative_exactly_at_threshold(self):
        """Čas přesně 25 % nad mediánem není suspicious (podmínka je > , ne >=)."""
        history = [20.0, 20.0, 20.0, 20.0, 20.0]  # medián = 20.0
        flag = determine_quality_flag(
            time_seconds=25.0,  # == 20.0 * 1.25 → NOT > threshold
            final_time_status="valid",
            low=LOW,
            high=HIGH,
            history_times=history,
        )
        assert flag == QualityFlag.ok


# ---------------------------------------------------------------------------
# Per-category percentilové bounds
# ---------------------------------------------------------------------------

class TestCategoryPercentileBounds:
    """Ověřuje, že percentilové bounds se liší pro různé kategorie."""

    def test_bounds_differ_for_two_categories(self):
        """Dvě různé distribuce dávají různé (low, high), což odráží rozdíl kategorií."""
        # Dorostenci: časy ~25–40 s
        times_a = [float(t) for t in range(25, 41)]
        # Muži/ženy: časy ~13–20 s
        times_b = [float(t) for t in range(13, 21)]

        low_a, high_a = _compute_percentile_bounds(times_a)
        low_b, high_b = _compute_percentile_bounds(times_b)

        # Bounds kategorie A (pomalejší) musí být vyšší než bounds kategorie B
        assert low_a > low_b, "Pomalejší kategorie musí mít vyšší low"
        assert high_a > high_b, "Pomalejší kategorie musí mít vyšší high"

    def test_empty_category_returns_abs_defaults(self):
        """Prázdná kategorie (žádná valid data) → fallback na absolutní hranice."""
        low, high = _compute_percentile_bounds([])
        assert low == 11.0
        assert high == 45.0


# ---------------------------------------------------------------------------
# Per-category relativní pravidlo
# ---------------------------------------------------------------------------

class TestCategoryHistory:
    """Ověřuje, že relativní pravidlo bere historii jen ze stejné kategorie."""

    def test_relative_rule_uses_same_category_history(self):
        """Sportovec má historii v kat A s mediánem 20.0; čas 26.0 > 25.0 → suspicious."""
        cat_a = ObjectId()
        athlete_id = ObjectId()

        result_doc = {
            "_id": ObjectId(),
            "final_time": 26.0,
            "final_time_status": "valid",
            "athlete": athlete_id,
            "category": cat_a,
            "date": datetime(2024, 6, 1),
        }

        # Bounds pro kat A: časy 18–34 → low≈18, high≈34; 26.0 je uvnitř hranic
        times_cat_a = [float(t) for t in range(18, 35)]
        # Historie kat A: medián = 20.0 → 26.0 > 20.0 * 1.25 = 25.0 → suspicious
        history_a = [19.0, 20.0, 20.0, 21.0, 22.0]

        async def mock_find_times(db_, cat_id):
            return times_cat_a

        async def mock_history(db_, athlete_id_, category_id_, before_date_):
            assert category_id_ == cat_a, "Historie musí být filtrována pro kat A"
            return history_a

        db = MagicMock()
        with (
            patch(
                "app.services.quality_flag_service._load_valid_times_for_category",
                side_effect=mock_find_times,
            ),
            patch(
                "app.services.quality_flag_service._load_athlete_history",
                side_effect=mock_history,
            ),
        ):
            flag = asyncio.run(compute_quality_flag(db, result_doc))

        assert flag == QualityFlag.suspicious

    def test_no_history_in_category_skips_relative_rule(self):
        """Sportovec nemá historii v dané kategorii → relativní pravidlo se neuplatní → ok."""
        cat_a = ObjectId()

        result_doc = {
            "_id": ObjectId(),
            "final_time": 26.0,
            "final_time_status": "valid",
            "athlete": ObjectId(),
            "category": cat_a,
            "date": datetime(2024, 6, 1),
        }

        times_cat_a = [float(t) for t in range(18, 35)]

        async def mock_find_times(db_, cat_id):
            return times_cat_a

        async def mock_history(db_, athlete_id_, category_id_, before_date_):
            return []  # žádná historie v kat A

        db = MagicMock()
        with (
            patch(
                "app.services.quality_flag_service._load_valid_times_for_category",
                side_effect=mock_find_times,
            ),
            patch(
                "app.services.quality_flag_service._load_athlete_history",
                side_effect=mock_history,
            ),
        ):
            flag = asyncio.run(compute_quality_flag(db, result_doc))

        # 26.0 uvnitř hranic (18–34), bez dostatečné historie → ok
        assert flag == QualityFlag.ok

    def test_missing_category_returns_ok(self):
        """Výsledek bez pole 'category' → QualityFlag.ok (graceful fallback)."""
        result_doc = {
            "_id": ObjectId(),
            "final_time": 26.0,
            "final_time_status": "valid",
            # 'category' záměrně chybí
        }
        db = MagicMock()
        flag = asyncio.run(compute_quality_flag(db, result_doc))
        assert flag == QualityFlag.ok

    def test_bounds_cache_per_category_is_used(self):
        """Pokud bounds_cache obsahuje category_id, DB dotaz na časy se nevyvolá."""
        cat_a = ObjectId()

        result_doc = {
            "_id": ObjectId(),
            "final_time": 26.0,
            "final_time_status": "valid",
            "athlete": ObjectId(),
            "category": cat_a,
            "date": datetime(2024, 6, 1),
        }

        # Cache s předpočítanými hranicemi: 26.0 uvnitř (15, 40)
        bounds_cache = {cat_a: (15.0, 40.0)}

        async def mock_history(db_, athlete_id_, category_id_, before_date_):
            return []  # krátká historie → relativní pravidlo se neuplatní

        db = MagicMock()
        with (
            patch(
                "app.services.quality_flag_service._load_valid_times_for_category",
                side_effect=AssertionError("DB nesmí být dotazována, cache existuje"),
            ),
            patch(
                "app.services.quality_flag_service._load_athlete_history",
                side_effect=mock_history,
            ),
        ):
            flag = asyncio.run(compute_quality_flag(db, result_doc, bounds_cache=bounds_cache))

        assert flag == QualityFlag.ok
