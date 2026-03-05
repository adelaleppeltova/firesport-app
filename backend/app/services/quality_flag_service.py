"""Service pro výpočet quality_flag výsledků (100m překážek).

quality_flag = "suspicious" pokud:
1) Absolutní hranice: time_seconds < low nebo > high
   kde low = max(11.0, Q01) a high = min(45.0, Q99)
   z distribuce valid časů *ve stejné kategorii* (results.category).
2) Relativní skok: aktuální čas je o více než 25 % horší než medián
   posledních 5 validních výsledků sportovce *ve stejné kategorii*.
"""

import logging
import statistics
from datetime import datetime
from typing import Optional

import numpy as np
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.result import QualityFlag

logger = logging.getLogger(__name__)

# Absolutní hranice (pojistka i když percentily selžou)
_ABS_LOW = 11.0
_ABS_HIGH = 45.0

# Relativní skok: > 25 % nad mediánem → suspicious
_RELATIVE_THRESHOLD = 1.25

# Minimální počet předchozích výsledků pro relativní pravidlo
_MIN_HISTORY = 5


def _compute_percentile_bounds(times: list[float]) -> tuple[float, float]:
    """Z dat spočítá Q01 a Q99 a vrátí (low, high) s absolutními pojistkami."""
    if not times:
        return _ABS_LOW, _ABS_HIGH
    arr = np.array(times, dtype=float)
    q01 = float(np.percentile(arr, 1))
    q99 = float(np.percentile(arr, 99))
    low = max(_ABS_LOW, q01)
    high = min(_ABS_HIGH, q99)
    return low, high


async def _load_valid_times_for_category(
    db: AsyncIOMotorDatabase,
    category_id: ObjectId,
) -> list[float]:
    """Načte valid final_time hodnoty z DB pro danou kategorii."""
    cursor = db["results"].find(
        {
            "final_time_status": "valid",
            "final_time": {"$ne": None},
            "category": category_id,
        },
        projection={"final_time": 1, "_id": 0},
    )
    docs = await cursor.to_list(None)
    return [d["final_time"] for d in docs if d.get("final_time") is not None]


async def _load_athlete_history(
    db: AsyncIOMotorDatabase,
    athlete_id: ObjectId,
    category_id: ObjectId,
    before_date: Optional[datetime],
) -> list[float]:
    """Vrátí časy posledních 5 validních výsledků sportovce v dané kategorii před datem závodu."""
    query: dict = {
        "athlete": athlete_id,
        "category": category_id,
        "final_time_status": "valid",
        "final_time": {"$ne": None},
    }
    if before_date is not None:
        query["date"] = {"$lt": before_date}

    cursor = (
        db["results"]
        .find(query, projection={"final_time": 1, "_id": 0})
        .sort("date", -1)
        .limit(_MIN_HISTORY)
    )
    docs = await cursor.to_list(_MIN_HISTORY)
    return [d["final_time"] for d in docs if d.get("final_time") is not None]


def determine_quality_flag(
    time_seconds: Optional[float],
    final_time_status: str,
    low: float,
    high: float,
    history_times: list[float],
) -> QualityFlag:
    """Čistá (synchronní) funkce – určí quality_flag pro jeden výsledek.

    Parametry
    ---------
    time_seconds:
        final_time výsledku (může být None).
    final_time_status:
        "valid" nebo "invalid".  Pro invalid vracíme rovnou ok.
    low, high:
        Absolutní hranice odvozené z percentilů kategorie (předpočítané mimo tuto funkci).
    history_times:
        Časy posledních max. 5 validních výsledků sportovce ve stejné kategorii.
    """
    # Status invalid → quality_flag neřešíme
    if final_time_status != "valid":
        return QualityFlag.ok

    # Null čas → quality_flag neřešíme
    if time_seconds is None:
        return QualityFlag.ok

    # Pravidlo 1 – absolutní hranice
    if time_seconds < low or time_seconds > high:
        return QualityFlag.suspicious

    # Pravidlo 2 – relativní skok (jen pokud máme dost historie)
    if len(history_times) >= _MIN_HISTORY:
        median_last5 = statistics.median(history_times)
        if time_seconds > median_last5 * _RELATIVE_THRESHOLD:
            return QualityFlag.suspicious

    return QualityFlag.ok


def _parse_object_id(raw) -> Optional[ObjectId]:
    """Převede raw hodnotu na ObjectId; při chybě vrátí None."""
    if raw is None:
        return None
    if isinstance(raw, ObjectId):
        return raw
    try:
        return ObjectId(str(raw))
    except Exception:
        return None


async def compute_quality_flag(
    db: AsyncIOMotorDatabase,
    result_doc: dict,
    bounds_cache: Optional[dict[ObjectId, tuple[float, float]]] = None,
) -> QualityFlag:
    """Asynchronní výpočet quality_flag pro jeden result dokument.

    Parametry
    ---------
    db:
        Motor databáze.
    result_doc:
        Raw MongoDB dokument výsledku (musí obsahovat alespoň
        ``final_time``, ``final_time_status``, ``athlete``, ``date``, ``category``).
    bounds_cache:
        Slovník {category_id: (low, high)} – sdílená cache pro hromadný přepočet.
        Pokud None nebo category_id v cache chybí, spočítá se z DB a výsledek
        se do cache uloží (je-li cache dict).
    """
    final_time: Optional[float] = result_doc.get("final_time")
    final_time_status: str = result_doc.get("final_time_status", "invalid")

    if final_time_status != "valid" or final_time is None:
        return QualityFlag.ok

    # Zjistění category_id – povinné pro per-category výpočet
    category_oid = _parse_object_id(result_doc.get("category"))
    if category_oid is None:
        logger.warning(
            "quality_flag: result %s nemá platné pole 'category', přeskakuji (ok).",
            result_doc.get("_id"),
        )
        return QualityFlag.ok

    # Načtení / použití předpočítaných hranic pro tuto kategorii
    if bounds_cache is not None and category_oid in bounds_cache:
        low, high = bounds_cache[category_oid]
    else:
        cat_times = await _load_valid_times_for_category(db, category_oid)
        low, high = _compute_percentile_bounds(cat_times)
        if bounds_cache is not None:
            bounds_cache[category_oid] = (low, high)

    # Načtení historie sportovce (filtrováno na kategorii)
    athlete_oid = _parse_object_id(result_doc.get("athlete"))
    result_date: Optional[datetime] = result_doc.get("date")
    history_times: list[float] = []
    if athlete_oid is not None:
        history_times = await _load_athlete_history(
            db, athlete_oid, category_oid, result_date
        )

    return determine_quality_flag(
        final_time, final_time_status, low, high, history_times
    )


async def compute_bounds_for_recompute(
    db: AsyncIOMotorDatabase,
) -> dict[ObjectId, tuple[float, float]]:
    """Vrátí slovník {category_id: (low, high)} pro hromadný přepočet.

    Pro každou kategorii, která má alespoň jeden valid výsledek, spočítá
    percentilové hranice. Kategorie bez dat dostanou fallback (11.0, 45.0).
    """
    # Distinct category_id z valid výsledků
    category_ids: list[ObjectId] = await db["results"].distinct(
        "category",
        {"final_time_status": "valid", "final_time": {"$ne": None}},
    )

    bounds: dict[ObjectId, tuple[float, float]] = {}
    for cat_id in category_ids:
        if cat_id is None:
            continue
        times = await _load_valid_times_for_category(db, cat_id)
        bounds[cat_id] = _compute_percentile_bounds(times)

    lows = [v[0] for v in bounds.values()]
    highs = [v[1] for v in bounds.values()]
    logger.info(
        "quality_flag recompute: %d kategorií, low ∈ [%.2f, %.2f], high ∈ [%.2f, %.2f]",
        len(bounds),
        min(lows, default=_ABS_LOW),
        max(lows, default=_ABS_LOW),
        min(highs, default=_ABS_HIGH),
        max(highs, default=_ABS_HIGH),
    )
    return bounds


async def recompute_quality_flags(db: AsyncIOMotorDatabase) -> dict:
    """Přepočítá quality_flag pro všechny výsledky v DB.

    Vrátí statistiky: počet zpracovaných, počet suspicious.
    """
    # Jednou načteme per-category hranice (cache pro celý běh)
    bounds: dict[ObjectId, tuple[float, float]] = await compute_bounds_for_recompute(db)

    cursor = db["results"].find(
        {},
        projection={"_id": 1, "final_time": 1, "final_time_status": 1,
                    "athlete": 1, "date": 1, "category": 1},
    )
    docs = await cursor.to_list(None)

    stats = {"processed": 0, "suspicious": 0, "ok": 0, "errors": 0}

    for doc in docs:
        try:
            flag = await compute_quality_flag(db, doc, bounds_cache=bounds)
            await db["results"].update_one(
                {"_id": doc["_id"]},
                {"$set": {"quality_flag": flag.value}},
            )
            stats["processed"] += 1
            if flag == QualityFlag.suspicious:
                stats["suspicious"] += 1
            else:
                stats["ok"] += 1
        except Exception as e:
            logger.exception("quality_flag error for result %s: %s", doc.get("_id"), e)
            stats["errors"] += 1

    logger.info("quality_flag recompute done: %s", stats)
    return stats
