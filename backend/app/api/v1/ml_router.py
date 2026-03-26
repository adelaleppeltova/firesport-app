"""
ML endpoints for anomaly detection and performance analysis.
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query

from app.db.database import get_db
from app.models.anomaly import (
    WindowListItem,
    YearlyBatchResponse,
)
from app.services.anomaly_service import (
    list_detection_windows,
    recompute_yearly_batch,
)
from app.services.windows import year_label

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/windows", response_model=list[WindowListItem])
async def get_detection_windows(
    athlete_id: Optional[str] = Query(
        default=None,
        description=(
            "Volitelné athlete_id (ObjectId jako string). "
            "Pokud je zadáno, vrátí pouze okna, pro která závodník skutečně "
            "má anomaly skóre (tj. byl zařazen do detekce)."
        ),
    ),
    db=Depends(get_db),
):
    """Return distinct detection windows stored in anomaly_runs.

    Each item represents a unique (window_start, window_end) pair
    with at least one completed yearly run (window_type=yearly_3y).
    Results are sorted by ``window_end`` descending (newest year first).
    When ``athlete_id`` is provided, only windows with scores for that
    athlete are returned.

    Recommended MongoDB index for performance::

        db.anomaly_runs.create_index(
            [("window_type", 1), ("window.end_date", -1)]
        )
    """
    raw_windows = await list_detection_windows(db, window_type="yearly_3y")

    # Filter to windows where the athlete actually has scores
    if athlete_id:
        try:
            from bson import ObjectId
            athlete_oid = ObjectId(athlete_id)
        except Exception:
            athlete_oid = None

        if athlete_oid is not None:
            athlete_run_ids: set = set(
                await db["anomaly_scores"].distinct(
                    "run_id",
                    {"athlete_id": athlete_oid},
                )
            )
            raw_windows = [w for w in raw_windows if w["run_id"] in athlete_run_ids]

    items: list[WindowListItem] = []
    for row in raw_windows:
        anchor: datetime = row["window_end"]
        start: datetime = row["window_start"]

        # Ensure timezone-aware (Motor may return naive UTC datetimes from Mongo)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        try:
            label = year_label(anchor, start, anchor)
        except ValueError:
            # Fallback for non-standard anchor dates (shouldn’t happen in practice)
            label = f"Custom ({start.date().isoformat()}–{anchor.date().isoformat()})"

        items.append(
            WindowListItem(
                run_id=row["run_id"],
                anchor_date=anchor.date().isoformat(),
                window_start=start,
                window_end=anchor,
                label=label,
            )
        )

    return items


@router.post("/recompute-yearly", response_model=YearlyBatchResponse)
async def recompute_yearly(
    from_date: Optional[date] = Query(
        default=None,
        alias="from",
        description=(
            "Earliest anchor date to include (YYYY-MM-DD). "
            "Defaults to min(results.date) in the database."
        ),
    ),
    to_date: Optional[date] = Query(
        default=None,
        alias="to",
        description=(
            "Latest anchor date to include (YYYY-MM-DD). "
            "Defaults to max(results.date) in the database."
        ),
    ),
    force: bool = Query(
        default=False,
        description=(
            "If False (default), anchors that already have a run are skipped. "
            "If True, every anchor is recomputed (old run is superseded)."
        ),
    ),
    db=Depends(get_db),
):
    """Batch-recompute Isolation Forest for all yearly anchors (Dec 31) in a date range.

    Year-end anchors (December 31) are generated for the resolved ``[from, to]``
    range using :func:`list_year_anchors`.  For each anchor
    :func:`recompute_for_window` is called with a 3-year rolling window and
    ``window_type="yearly_3y"``.

    Window boundaries for anchor ``YYYY-12-31`` with years=3::

        window_start = (YYYY-3)-12-31 + 1 day = (YYYY-2)-01-01
        window_end   = YYYY-12-31

    Idempotence
    -----------
    * ``force=false`` – anchors with an existing non-superseded run are
      skipped and reported as ``status="skipped_existing"``.
    * ``force=true`` – every anchor is recomputed; the previous run is
      marked ``is_superseded=True`` and its scores are deleted.

    Recommended index::

        db.anomaly_runs.create_index(
            [("window_type", 1), ("window.end_date", -1)]
        )
    """
    date_min: Optional[datetime] = None
    date_max: Optional[datetime] = None

    if from_date is not None:
        date_min = datetime(from_date.year, from_date.month, from_date.day, tzinfo=timezone.utc)
    if to_date is not None:
        date_max = datetime(to_date.year, to_date.month, to_date.day, tzinfo=timezone.utc)

    return await recompute_yearly_batch(
        db,
        date_min=date_min,
        date_max=date_max,
        force=force,
    )
