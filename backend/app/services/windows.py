"""
Utility functions for generating anchor dates and rolling time windows.

Yearly anchor dates are December 31 of each year (UTC).

Rolling window definition
--------------------------
For a given anchor date, the 3-year rolling window is:

  window_end   = anchor  (inclusive)
  window_start = anchor - relativedelta(years=years) + timedelta(days=1)  (inclusive)

Example for anchor = 2025-12-31 and years = 3:
  window_start = 2022-12-31 + 1 day = 2023-01-01
  window_end   = 2025-12-31

This gives exactly 3 years of data with no day overlap between consecutive
yearly windows (the previous yearly window would end on 2024-12-31 and
start on 2022-01-01, so the intervals are contiguous but not overlapping).
"""

from datetime import date, datetime, timedelta, timezone
from typing import Union

from dateutil.relativedelta import relativedelta

# Year-end constants (December 31)
_YEAR_END_MONTH: int = 12
_YEAR_END_DAY: int = 31


def adaptive_contamination(
    n: int,
    *,
    min_c: float = 0.02,
    max_c: float = 0.10,
) -> float:
    """Return an adaptive contamination rate for Isolation Forest.

    The raw estimate is ``1 / n`` (one expected outlier per *n* samples).
    The result is clamped to ``[min_c, max_c]`` so it stays in a
    meaningful range regardless of the dataset size.

    Parameters
    ----------
    n:
        Number of samples.  Must be a positive integer (≥ 1).
    min_c:
        Lower clamp bound.  Defaults to 0.02 (2 %).
    max_c:
        Upper clamp bound.  Defaults to 0.10 (10 %).

    Returns
    -------
    float
        ``clamp(1/n, min_c, max_c)``

    Raises
    ------
    ValueError
        If *n* ≤ 0.

    Notes
    -----
    The ML pipeline requires at least 10 results to run (``min_results_used``).
    This function is intentionally general and does **not** enforce that
    threshold – callers are responsible for the guard.

    Examples
    --------
    >>> adaptive_contamination(10)   # 1/10 = 0.10  → clamped to max_c
    0.1
    >>> adaptive_contamination(20)   # 1/20 = 0.05
    0.05
    >>> adaptive_contamination(100)  # 1/100 = 0.01 → clamped to min_c
    0.02
    """
    if n <= 0:
        raise ValueError(f"n must be a positive integer, got {n!r}.")
    raw = 1.0 / n
    return max(min_c, min(raw, max_c))


def window_for_anchor(
    anchor: datetime,
    years: int = 3,
) -> tuple[datetime, datetime]:
    """Return the (window_start, window_end) of a rolling window ending at *anchor*.

    Both endpoints are **inclusive**.

    ``window_end   = anchor``
    ``window_start = anchor - relativedelta(years=years) + timedelta(days=1)``

    The +1 day shift ensures that consecutive windows are contiguous without
    overlap.  For example, with years=3 and Dec-31 anchors:

      anchor 2025-12-31  →  window [2023-01-01, 2025-12-31]
      anchor 2024-12-31  →  window [2022-01-01, 2024-12-31]

    Parameters
    ----------
    anchor:
        The anchor date (timezone-aware), e.g. December 31 for yearly windows.
    years:
        Number of full years the window covers. Defaults to 3.

    Returns
    -------
    tuple[datetime, datetime]
        ``(window_start, window_end)`` both timezone-aware in UTC.

    Raises
    ------
    ValueError
        If *anchor* is not timezone-aware or *years* is not a positive integer.
    """
    if anchor.tzinfo is None:
        raise ValueError("anchor must be a timezone-aware datetime.")
    if not isinstance(years, int) or years < 1:
        raise ValueError("years must be a positive integer.")

    anchor_utc = anchor.astimezone(timezone.utc)
    window_end = anchor_utc
    window_start = anchor_utc - relativedelta(years=years) + timedelta(days=1)

    return window_start, window_end


def is_year_end(dt: Union[date, datetime]) -> bool:
    """Return ``True`` when *dt* falls on December 31 (year-end day).

    Works with both :class:`datetime.date` and :class:`datetime.datetime`
    objects.

    Parameters
    ----------
    dt:
        Any date or datetime.

    Returns
    -------
    bool

    Examples
    --------
    >>> from datetime import date
    >>> is_year_end(date(2025, 12, 31))
    True
    >>> is_year_end(date(2025, 3, 31))
    False
    """
    return dt.month == _YEAR_END_MONTH and dt.day == _YEAR_END_DAY


def list_year_anchors(
    date_min: datetime,
    date_max: datetime,
) -> list[datetime]:
    """Return all year-end anchor dates (Dec 31) within [date_min, date_max].

    The returned datetimes are timezone-aware (UTC), normalised to
    midnight (00:00:00 UTC) of December 31 for each year in the range.

    Parameters
    ----------
    date_min:
        Earliest date to include (inclusive).  Must be timezone-aware.
    date_max:
        Latest date to include (inclusive).  Must be timezone-aware.

    Returns
    -------
    list[datetime]
        Sorted list of UTC Dec-31 datetimes in [date_min, date_max].

    Raises
    ------
    ValueError
        If date_min or date_max are not timezone-aware, or if date_min > date_max.

    Examples
    --------
    >>> from datetime import datetime, timezone
    >>> d_min = datetime(2022, 1, 1, tzinfo=timezone.utc)
    >>> d_max = datetime(2025, 6, 30, tzinfo=timezone.utc)
    >>> list_year_anchors(d_min, d_max)
    [datetime(2022, 12, 31, ...), datetime(2023, 12, 31, ...), datetime(2024, 12, 31, ...)]
    """
    if date_min.tzinfo is None or date_max.tzinfo is None:
        raise ValueError("date_min and date_max must be timezone-aware datetimes.")
    if date_min > date_max:
        raise ValueError("date_min must not be later than date_max.")

    date_min_utc = date_min.astimezone(timezone.utc)
    date_max_utc = date_max.astimezone(timezone.utc)

    # Always include the year-end anchor for the last year that has any data
    # (i.e. the year of date_max), even if date_max falls before Dec 31.
    year_end_of_max = datetime(date_max_utc.year, _YEAR_END_MONTH, _YEAR_END_DAY, tzinfo=timezone.utc)
    effective_date_max_utc = max(date_max_utc, year_end_of_max)

    anchors: list[datetime] = []
    for year in range(date_min_utc.year, effective_date_max_utc.year + 1):
        anchor = datetime(year, _YEAR_END_MONTH, _YEAR_END_DAY, tzinfo=timezone.utc)
        if date_min_utc <= anchor <= effective_date_max_utc:
            anchors.append(anchor)

    return anchors


def year_label(
    anchor: Union[date, datetime],
    window_start: Union[date, datetime],
    window_end: Union[date, datetime],
) -> str:
    """Return a human-readable label for a yearly rolling window.

    Format::

        "{end_year}–{start_year}"

    Example::

        >>> from datetime import datetime, timezone
        >>> a  = datetime(2025, 12, 31, tzinfo=timezone.utc)
        >>> ws = datetime(2023, 1, 1,  tzinfo=timezone.utc)
        >>> we = datetime(2025, 12, 31, tzinfo=timezone.utc)
        >>> year_label(a, ws, we)
        '2025–2023'

    Parameters
    ----------
    anchor:
        Year-end date (Dec 31, = ``window_end``). Must be a year-end day;
        otherwise ``ValueError`` is raised.
    window_start:
        First day of the rolling window (inclusive).
    window_end:
        Last day of the rolling window (inclusive, should equal anchor).

    Returns
    -------
    str
        Label string suitable for display in the UI.

    Raises
    ------
    ValueError
        If ``anchor`` does not fall on December 31.
    """
    if not is_year_end(anchor):
        anchor_str = (
            anchor.astimezone(timezone.utc).date().isoformat()
            if isinstance(anchor, datetime)
            else anchor.isoformat()
        )
        raise ValueError(
            f"anchor {anchor_str} is not a year-end date (expected Dec 31)."
        )

    # Normalise to date for ISO formatting
    def _to_date(d: Union[date, datetime]) -> date:
        if isinstance(d, datetime):
            return d.astimezone(timezone.utc).date()
        return d

    anchor_dt = _to_date(anchor)
    start_year = _to_date(window_start).year
    return f"{anchor_dt.year}–{start_year}"
