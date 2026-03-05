"""
Unit tests for adaptive_contamination() in backend/app/services/windows.py

Testované případy:
  1. n=10   → 0.10  (1/10 = max_c, clamp nahoře)
  2. n=20   → 0.05  (1/20 = 0.05, v rozsahu)
  3. n=100  → 0.02  (1/100 = 0.01, clamp dole na min_c)
  4. n=0    → ValueError
  5. n=-5   → ValueError
  6. n=5    → 0.10  (1/5 = 0.20, clamp nahoře na max_c)
  7. vlastní min_c/max_c hranice
"""

import pytest

from app.services.windows import adaptive_contamination


# ---------------------------------------------------------------------------
# Požadované testy zadání
# ---------------------------------------------------------------------------

def test_n_10_returns_max():
    """1/10 = 0.10 – přesně max_c, výsledek nesmí být oříznut."""
    assert adaptive_contamination(10) == pytest.approx(0.10)


def test_n_20_in_range():
    """1/20 = 0.05 – leží uvnitř [0.02, 0.10], vrátí se beze změny."""
    assert adaptive_contamination(20) == pytest.approx(0.05)


def test_n_100_clamped_to_min():
    """1/100 = 0.01 < min_c=0.02 → clamp na 0.02."""
    assert adaptive_contamination(100) == pytest.approx(0.02)


def test_n_zero_raises_value_error():
    """n=0 je nepřípustné → ValueError."""
    with pytest.raises(ValueError, match="positive integer"):
        adaptive_contamination(0)


# ---------------------------------------------------------------------------
# Doplňkové testy
# ---------------------------------------------------------------------------

def test_n_negative_raises_value_error():
    """Záporné n je taky nepřípustné."""
    with pytest.raises(ValueError, match="positive integer"):
        adaptive_contamination(-5)


def test_n_5_clamped_to_max():
    """1/5 = 0.20 > max_c=0.10 → clamp na 0.10."""
    assert adaptive_contamination(5) == pytest.approx(0.10)


def test_custom_bounds():
    """Ověří fungování vlastních hranic min_c / max_c."""
    # n=50 → 1/50 = 0.02; s min_c=0.05 se musí clampnout na 0.05
    assert adaptive_contamination(50, min_c=0.05, max_c=0.15) == pytest.approx(0.05)

    # n=4 → 1/4 = 0.25; s max_c=0.20 se musí clampnout na 0.20
    assert adaptive_contamination(4, min_c=0.05, max_c=0.20) == pytest.approx(0.20)
