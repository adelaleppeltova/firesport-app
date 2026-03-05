"""
Unit tests for recompute_for_window helpers in anomaly_service.py.

Testují se čisté (pure) funkce bez DB závislosti:
  1. _contamination_stats – min/median/max
  2. edge-cases: prázdný vstup, jeden prvek, lichý/sudý počet prvků
  3. Integrace s adaptive_contamination – ověření výstupních hodnot
"""

import statistics

import pytest

# Import testovaných funkcí
from app.services.anomaly_service import _contamination_stats
from app.models.anomaly import ContaminationStats
from app.services.windows import adaptive_contamination


# ---------------------------------------------------------------------------
# Tests for _contamination_stats (pure function)
# ---------------------------------------------------------------------------

def test_contamination_stats_empty():
    """Prázdný vstup musí vrátit None."""
    assert _contamination_stats([]) is None


def test_contamination_stats_single_value():
    """Jeden prvek → min == median == max."""
    result = _contamination_stats([0.05])
    assert isinstance(result, ContaminationStats)
    assert result.min == pytest.approx(0.05)
    assert result.median == pytest.approx(0.05)
    assert result.max == pytest.approx(0.05)


def test_contamination_stats_odd_count():
    """Lichý počet prvků → median je prostřední hodnota."""
    values = [0.02, 0.05, 0.10]
    result = _contamination_stats(values)
    assert result.min == pytest.approx(0.02)
    assert result.median == pytest.approx(statistics.median(values))
    assert result.max == pytest.approx(0.10)


def test_contamination_stats_even_count():
    """Sudý počet prvků → median je průměr dvou prostředních."""
    values = [0.02, 0.04, 0.08, 0.10]
    result = _contamination_stats(values)
    assert result.min == pytest.approx(0.02)
    assert result.median == pytest.approx(statistics.median(values))  # 0.06
    assert result.max == pytest.approx(0.10)


def test_contamination_stats_unsorted_input():
    """Funkce nesmí být závislá na pořadí vstupu."""
    values_shuffled = [0.10, 0.02, 0.07]
    result = _contamination_stats(values_shuffled)
    assert result.min == pytest.approx(0.02)
    assert result.max == pytest.approx(0.10)
    assert result.median == pytest.approx(0.07)


# ---------------------------------------------------------------------------
# Integration: adaptive_contamination feeds into _contamination_stats
# ---------------------------------------------------------------------------

def test_contamination_stats_from_adaptive_values():
    """Ověří, že výstupy adaptive_contamination správně vstoupí do stats."""
    ns = [10, 20, 50, 100]               # → 0.10, 0.05, 0.02(clamped), 0.02(clamped)
    values = [adaptive_contamination(n) for n in ns]

    assert values == pytest.approx([0.10, 0.05, 0.02, 0.02])

    result = _contamination_stats(values)
    assert result.min == pytest.approx(0.02)
    assert result.max == pytest.approx(0.10)
    assert result.median == pytest.approx(statistics.median(values))  # (0.02+0.05)/2=0.035


# ---------------------------------------------------------------------------
# Tests for ContaminationStats model fields
# ---------------------------------------------------------------------------

def test_contamination_stats_model_fields():
    """ContaminationStats pydantic model musí mít pole min/median/max."""
    cs = ContaminationStats(min=0.02, median=0.05, max=0.10)
    assert cs.min == 0.02
    assert cs.median == 0.05
    assert cs.max == 0.10
