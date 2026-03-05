"""
Unit tests for backend/app/services/windows.py

Tests:
  1. test_window_for_anchor_2025_yearly    – přesné window_start / window_end pro 2025-12-31
  2. test_window_for_anchor_raises_*       – chyby při neplatném vstupu
  3. test_is_year_end_*                    – validace 31.12
  4. test_list_year_anchors_*              – roční anchory (rozsah, správné hodnoty)
  5. test_year_label_*                     – formát a validace labelu ročního okna
"""

from datetime import date, datetime, timezone

import pytest

from app.services.windows import (
    window_for_anchor,
    is_year_end,
    list_year_anchors,
    year_label,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


# ===========================================================================
# Tests for window_for_anchor
# ===========================================================================

def test_window_for_anchor_2025_yearly():
    """Okno pro anchor 2025-12-31 s years=3 musí být [2023-01-01, 2025-12-31]."""
    anchor = utc(2025, 12, 31)

    window_start, window_end = window_for_anchor(anchor, years=3)

    assert window_end == utc(2025, 12, 31), "window_end musí být shodné s anchorem"
    assert window_start == utc(2023, 1, 1), (
        "window_start = anchor - 3 roky + 1 den = 2023-01-01"
    )
    # Délka okna v dnech: od 2023-01-01 do 2025-12-31 včetně
    # 2023: 365, 2024: 366 (přestupný), 2025: 365 = 1096 dní
    delta_days = (window_end - window_start).days + 1  # +1 pro inclusive window_end
    assert delta_days == 1096, f"Očekáváno 1096 dní, dostáno {delta_days}"


def test_window_for_anchor_raises_on_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        window_for_anchor(datetime(2025, 12, 31))  # naive


def test_window_for_anchor_raises_on_invalid_years():
    with pytest.raises(ValueError, match="years"):
        window_for_anchor(utc(2025, 12, 31), years=0)


# ===========================================================================
# Tests for is_year_end
# ===========================================================================


@pytest.mark.parametrize("year", [2021, 2022, 2023, 2024, 2025])
def test_is_year_end_true_for_dec_31(year):
    """31. 12. kteréhokoli roku musí vrátit True."""
    assert is_year_end(date(year, 12, 31)) is True


@pytest.mark.parametrize("month,day", [
    (12, 30),  # den před koncem roku
    (12, 1),   # začátek prosince
    (11, 30),  # konec listopadu
    (3,  31),  # konec čtvrtletí Q1 – není year-end
    (6,  30),  # konec čtvrtletí Q2
    (9,  30),  # konec čtvrtletí Q3
    (1,  1),   # Nový rok
])
def test_is_year_end_false_for_non_year_end(month, day):
    """Ne-year-end data musí vrátit False."""
    assert is_year_end(date(2025, month, day)) is False


def test_is_year_end_works_with_datetime():
    """is_year_end akceptuje datetime objekt stejně jako date."""
    assert is_year_end(utc(2025, 12, 31)) is True
    assert is_year_end(utc(2025, 12, 30)) is False


# ===========================================================================
# Tests for list_year_anchors
# ===========================================================================


def test_list_year_anchors_values():
    """Pro rozsah 2022-01-01 – 2024-12-31 musí vrátit přesně tři anchory."""
    date_min = utc(2022, 1, 1)
    date_max = utc(2024, 12, 31)

    result = list_year_anchors(date_min, date_max)

    expected = [
        utc(2022, 12, 31),
        utc(2023, 12, 31),
        utc(2024, 12, 31),
    ]
    assert result == expected


def test_list_year_anchors_range_cuts_correctly():
    """date_max před 31.12 vyřadí anchor pro ten rok."""
    date_min = utc(2022, 1, 1)
    date_max = utc(2024, 6, 30)  # před 31.12.2024

    result = list_year_anchors(date_min, date_max)

    # Pouze 2022 a 2023, 2024-12-31 je až po date_max
    assert result == [utc(2022, 12, 31), utc(2023, 12, 31)]


def test_list_year_anchors_single_year():
    """date_min == date_max == 31.12 – vrátí jeden anchor."""
    d = utc(2025, 12, 31)
    result = list_year_anchors(d, d)
    assert result == [utc(2025, 12, 31)]


def test_list_year_anchors_empty_when_no_year_end_in_range():
    """Rozsah bez 31.12 vrátí prázdný seznam."""
    date_min = utc(2025, 1, 1)
    date_max = utc(2025, 12, 30)  # jeden den před year-end
    result = list_year_anchors(date_min, date_max)
    assert result == []


def test_list_year_anchors_raises_on_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        list_year_anchors(
            datetime(2024, 1, 1),  # naive
            datetime(2024, 12, 31),
        )


def test_list_year_anchors_raises_when_min_gt_max():
    with pytest.raises(ValueError, match="date_min"):
        list_year_anchors(utc(2025, 1, 1), utc(2024, 1, 1))


# ===========================================================================
# Tests for year_label
# ===========================================================================


def test_year_label_format():
    """Správný formát labelu pro roční okno."""
    anchor = utc(2025, 12, 31)
    ws = utc(2023, 1, 1)
    we = utc(2025, 12, 31)
    assert year_label(anchor, ws, we) == "Rok 2025 (2023-01-01\u20132025-12-31)"


def test_year_label_with_date_objects():
    """year_label akceptuje date i datetime objekty."""
    label = year_label(
        date(2024, 12, 31),
        date(2022, 1, 1),
        date(2024, 12, 31),
    )
    assert label == "Rok 2024 (2022-01-01\u20132024-12-31)"


def test_year_label_invalid_anchor_raises():
    """Anchor v nezávěrečném datu (např. 30.12) vyvolá ValueError."""
    with pytest.raises(ValueError, match="year-end date"):
        year_label(utc(2025, 12, 30), utc(2023, 1, 1), utc(2025, 12, 30))


def test_year_label_invalid_anchor_quarter_end_raises():
    """Anchor na konci kvartálu Q1 (31.3) není year-end – musí vyhodit ValueError."""
    with pytest.raises(ValueError, match="year-end date"):
        year_label(utc(2026, 3, 31), utc(2023, 4, 1), utc(2026, 3, 31))


def test_year_label_returns_string_with_rok_prefix():
    """Label začíná 'Rok '."""
    label = year_label(utc(2022, 12, 31), utc(2020, 1, 1), utc(2022, 12, 31))
    assert label.startswith("Rok ")
    assert "2022" in label


def test_is_year_end_and_year_label_consistent():
    """Každý anchor kde is_year_end=True musí jít použít v year_label bez chyby."""
    for year in range(2020, 2026):
        anchor = utc(year, 12, 31)
        assert is_year_end(anchor)
        label = year_label(anchor, utc(year - 3, 1, 1), anchor)
        assert f"Rok {year}" in label
