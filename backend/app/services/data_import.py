"""
Service pro import dat ze JSON souborů do MongoDB.
Podporuje inkrementální import výsledků k existujícím závodníkům.
"""
import json
import logging
import re
from collections import Counter
from datetime import datetime
from hashlib import sha256
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.db.database import db
from app.models.admin import ImportStats
from app.models.result import MatchStatus
from app.services.athlete_identity import normalize_fs_code
from app.services.quality_flag_service import compute_bounds_for_recompute, compute_quality_flag
from app.services.result_matching import (
    decide_athlete_match,
    normalize_person_name,
)

logger = logging.getLogger(__name__)


def _import_id(scope: str, *fields: Any) -> ObjectId:
    serialized = json.dumps([scope, *fields], ensure_ascii=False, sort_keys=True, default=str)
    return ObjectId(sha256(serialized.encode()).digest()[:12])


async def _insert_import_document(collection, document: dict) -> bool:
    try:
        await collection.insert_one(document)
    except DuplicateKeyError:
        if await collection.find_one({"_id": document["_id"]}):
            return False
        raise
    return True


categories_collection = db["categories"]
competitions_collection = db["competitions"]
results_collection = db["results"]


class DataImporter:
    """Třída pro import dat z JSON struktury."""

    def __init__(self):
        self.categories_cache: dict[tuple[str, Optional[str]], str] = {}
        self._bounds_cache: Optional[dict[ObjectId, tuple[float, float]]] = None  # {category_id: (low, high)} percentilové hranice
        self.stats = ImportStats().model_dump()

    @staticmethod
    def _normalize_category_name(value: str) -> str:
        """Převede název kategorie do prezentačního formátu pro ukládání do DB.

        První slovo začíná velkým písmenem, další slova jsou malými písmeny.
        Zkratka 'HZS' zůstává vždy velkými písmeny.

        Příklady:
        - 'MLADŠÍ DOROSTENKY' -> 'Mladší dorostenky'
        - 'MUŽI A STARŠÍ DOROSTENCI' -> 'Muži a starší dorostenci'
        - 'MUŽI HZS' -> 'Muži HZS'
        """
        keep_upper = {"hzs"}
        stripped = value.strip()
        if not stripped:
            return stripped
        normalized_words = []
        for index, word in enumerate(stripped.split()):
            lower_word = word.lower()
            if lower_word in keep_upper:
                normalized_words.append(lower_word.upper())
            elif index == 0:
                normalized_words.append(
                    word[0].upper() + word[1:].lower() if word else ""
                )
            else:
                normalized_words.append(lower_word)
        return " ".join(normalized_words)

    async def import_from_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Importuje data ze slovníku (parsovaný JSON).

        Očekávaná struktura:
        {
            "competition": {
                "name": "...",
                "place": "...",
                "date": "2025-05-04",
                "type": "...",
                "league": "...",
                "categories": [
                    {
                        "name": "Ženy",
                        "results": [...]
                    }
                ]
            }
        }
        """
        try:
            logger.info("Zahájen import dat")

            # Import soutěže
            competition_data = data.get("competition", {})
            source = urlsplit(data.get("source_file") or "")
            source_url = source._replace(fragment="").geturl() if source.scheme in ("http", "https") and source.netloc else None
            competition_id = await self._import_competition(competition_data, source_url=source_url)

            # Import kategorií a jejich výsledků
            for category_data in competition_data.get("categories", []):
                await self._import_category_with_results(
                    category_data, competition_id
                )

            logger.info(f"Import dokončen: {self.stats}")
            return self.stats

        except Exception as e:
            logger.error(f"Chyba během importu: {e}", exc_info=True)
            self.stats["errors"].append(str(e))
            return self.stats


    async def _import_competition(
        self, comp_data: Dict[str, Any], *, source_url: Optional[str] = None
    ) -> str:
        comp_date = comp_data.get("date")
        if isinstance(comp_date, str):
            comp_date = datetime.strptime(comp_date, "%Y-%m-%d")
        metadata = {"name": comp_data.get("name"), "place": comp_data.get("place"), "date": comp_date}
        if not all(metadata.values()):
            raise ValueError("Chybí název, místo nebo datum závodu.")

        if source_url:
            sources = await competitions_collection.find({"source_url": source_url}).limit(2).to_list(2)
            if sources:
                if len(sources) != 1 or any(sources[0].get(key) != value for key, value in metadata.items()):
                    raise ValueError(f"Konflikt metadat pro zdroj závodu {source_url}.")
                return str(sources[0]["_id"])

        # Legacy races may be spread across several source files which share the same metadata.
        existing = await competitions_collection.find(metadata).limit(2).to_list(2)
        if len(existing) > 1 or (
            existing and source_url and existing[0].get("source_url") not in (None, source_url)
        ):
            raise ValueError(f"Nejednoznačná identita závodu {metadata['name']} ({comp_date.date()}).")
        if existing:
            race = existing[0]
            if source_url and not race.get("source_url"):
                outcome = await competitions_collection.update_one(
                    {"_id": race["_id"], "source_url": None}, {"$set": {"source_url": source_url}}
                )
                if not outcome.matched_count:
                    latest = await competitions_collection.find_one({"_id": race["_id"]})
                    if not latest or latest.get("source_url") != source_url:
                        raise ValueError(f"Konflikt zdrojů závodu {metadata['name']}.")
            return str(race["_id"])

        raw_league = comp_data.get("league") or []
        league = [raw_league] if isinstance(raw_league, str) else [str(item) for item in raw_league if item]
        document = {
            "_id": _import_id("competition", metadata),
            **metadata,
            "league": league,
            "created_at": datetime.now(),
        }
        if source_url:
            document["source_url"] = source_url
        if await _insert_import_document(competitions_collection, document):
            self.stats["competitions_created"] += 1
            return str(document["_id"])
        return await self._import_competition(comp_data, source_url=source_url)

    async def _import_category_with_results(
        self, category_data: Dict[str, Any], competition_id: str
    ) -> None:
        """Importuje kategorii a její výsledky."""
        try:
            raw_name = category_data.get("name") or ""
            category_name = self._normalize_category_name(raw_name)
            discipline = category_data.get("discipline") or None
            category_id = await self._import_category(category_name, discipline=discipline)


            # Import výsledků
            results = category_data.get("results", [])
            row_counts = Counter(json.dumps(row, sort_keys=True) for row in results)
            for result_data in results:
                row_key = json.dumps(result_data, sort_keys=True)
                if row_counts[row_key] > 1:
                    self.stats["errors"].append(
                        f"Kategorie {category_name}: nerozlišitelné řádky ve vstupním souboru."
                    )
                    continue
                await self._import_result(
                    result_data, category_id, competition_id
                )

        except Exception as e:
            logger.error(f"Chyba při importu kategorie: {e}")
            self.stats["errors"].append(f"Kategorie: {str(e)}")


    async def _import_category(self, name: str, *, discipline: Optional[str] = None) -> str:
        """Importuje nebo najde existující kategorii."""
        if not name:
            raise ValueError("Chybí název kategorie.")

        cache_key = (name, discipline)
        if cache_key in self.categories_cache:
            return self.categories_cache[cache_key]

        same_name = {"name": {"$regex": rf"^{re.escape(name)}$", "$options": "i"}}
        candidates = await categories_collection.find(same_name).to_list(length=None)
        matching = [doc for doc in candidates if doc.get("discipline") == discipline] if discipline else candidates
        if discipline and not matching and len(candidates) == 1 and not candidates[0].get("discipline"):
            candidate = candidates[0]
            outcome = await categories_collection.update_one(
                {"_id": candidate["_id"], "discipline": {"$in": [None, "", discipline]}},
                {"$set": {"discipline": discipline}},
            )
            if outcome.matched_count:
                matching = [candidate]
            else:
                return await self._import_category(name, discipline=discipline)
        if len(matching) > 1 or (not matching and any(not doc.get("discipline") for doc in candidates)):
            raise ValueError(f"Nejednoznačná kategorie {name!r} ({discipline}).")
        if matching:
            category_id = str(matching[0]["_id"])
        else:
            new_category = {
                "_id": _import_id("category", name, discipline),
                "name": name,
                "created_at": datetime.now(),
            }
            if discipline:
                new_category["discipline"] = discipline
            if await _insert_import_document(categories_collection, new_category):
                self.stats["categories_created"] += 1
            category_id = str(new_category["_id"])

        self.categories_cache[cache_key] = category_id
        return category_id

    async def _import_result(
        self, result_data: Dict[str, Any], category_id: str, competition_id: str
    ) -> None:
        """Importuje nový řádek a existující výkon ponechá beze změny."""
        try:
            team = result_data.get("team")
            imported_athlete = self._extract_imported_athlete_data(result_data)
            competition = await competitions_collection.find_one({"_id": ObjectId(competition_id)})
            row = {
                "competition": ObjectId(competition_id),
                "category": ObjectId(category_id),
                "team": team,
                "district": result_data.get("district"),
                "imported_athlete": imported_athlete,
                "start_number": result_data.get("start_number"),
                "final_time": result_data.get("final_time"),
                "final_time_status": result_data.get("final_status", "invalid"),
                "rank": result_data.get("rank"),
                "times": [
                    {
                        "attempt": attempt.get("try"),
                        "time": attempt.get("time"),
                        "status": attempt.get("status", "invalid"),
                        **({"invalid_reason": attempt["invalid_reason"]} if attempt.get("invalid_reason") else {}),
                    }
                    for attempt in result_data.get("times", [])
                ],
            }
            if await self._existing_result(row):
                return

            match = await decide_athlete_match(**imported_athlete, team=team)
            result_doc = {
                "_id": _import_id("result", self._row_identity(row)),
                **row,
                "date": competition.get("date") if competition else None,
                "match_status": match["match_status"].value,
                "match_reason": match["match_reason"],
                "created_at": datetime.now(),
                "quality_flag": "ok",
            }
            if match["matched_athlete"]:
                result_doc["athlete"] = ObjectId(match["matched_athlete"]["_id"])
                try:
                    if self._bounds_cache is None:
                        self._bounds_cache = await compute_bounds_for_recompute(db)
                    flag = await compute_quality_flag(db, result_doc, bounds_cache=self._bounds_cache)
                    result_doc["quality_flag"] = flag.value
                except Exception as exc:
                    logger.warning("Nepodařilo se vypočítat quality_flag: %s", exc)

            if not await _insert_import_document(results_collection, result_doc):
                self.stats["results_duplicates_skipped"] += 1
                return

            self.stats["total_imported"] += 1
            self.stats["results_created"] += 1
            self._increment_match_stats(match["match_status"])
        except Exception as exc:
            self.stats["errors"].append(f"Výsledek: {exc}")
            logger.error("Chyba při importu výsledku: %s", exc)

    @staticmethod
    def _row_identity(row: dict) -> dict:
        athlete = row.get("imported_athlete") or {}
        # Compare the representation written by both the old and new importer.
        team = re.sub(r"\bSDH\b", "", row.get("team") or "", flags=re.IGNORECASE)
        return {
            "competition": row["competition"],
            "category": row["category"],
            "team": " ".join(team.split()).casefold(),
            "name": tuple(
                normalize_person_name(athlete.get(field)).replace(" ", "").casefold()
                for field in ("first_name", "last_name")
            ),
            "birth_year": athlete.get("birth_year"),
            "fscode": normalize_fs_code(athlete.get("fscode")),
            "start_number": str(row["start_number"]).strip() if row.get("start_number") else None,
            "rank": row.get("rank"),
            "final_time": float(row["final_time"]) if row.get("final_time") is not None else None,
            "final_time_status": row.get("final_time_status"),
            "times": [
                (attempt.get("attempt"), float(attempt["time"]) if attempt.get("time") is not None else None,
                 attempt.get("status"))
                for attempt in row.get("times") or []
            ],
        }

    async def _existing_result(self, row: dict) -> bool:
        identity = self._row_identity(row)
        scope = {key: row[key] for key in ("competition", "category")}
        # A changed identity or performance in the same row is a conflict, not an update.
        exact = 0
        ambiguous = 0
        async for existing in results_collection.find(scope):
            previous = self._row_identity(existing)
            if previous == identity:
                exact += 1
            elif any(
                identity[field] is not None and identity[field] == previous[field]
                for field in ("start_number", "fscode")
            ) or (
                all(identity["name"]) and identity["name"] == previous["name"]
                and not (
                    identity["birth_year"] is not None and previous["birth_year"] is not None
                    and identity["birth_year"] != previous["birth_year"]
                )
            ) or (
                identity["rank"] is not None and identity["rank"] == previous["rank"]
                and not (all(identity["name"]) and all(previous["name"]) and identity["name"] != previous["name"])
                and not (
                    identity["start_number"] is not None and previous["start_number"] is not None
                    and identity["start_number"] != previous["start_number"]
                )
            ):
                ambiguous += 1

        has_row_evidence = any(
            identity[key] is not None for key in ("start_number", "rank", "fscode", "final_time")
        ) or any(time is not None for _, time, _ in identity["times"])
        if exact == 1 and has_row_evidence:
            self.stats["results_duplicates_skipped"] += 1
            return True
        if exact or ambiguous:
            raise ValueError(
                f"Nejednoznačný řádek závodu {row['competition']}, kategorie {row['category']} "
                f"(startovní číslo {row['start_number']}, pořadí {row['rank']})."
            )
        return False

    def _extract_imported_athlete_data(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fscode": normalize_fs_code(result_data.get("fscode")),
            "first_name": result_data.get("first_name") or "",
            "last_name": result_data.get("last_name") or "",
            "birth_year": result_data.get("birth_year") or None,
        }

    def _increment_match_stats(self, match_status: MatchStatus) -> None:
        if match_status == MatchStatus.matched:
            self.stats["results_matched"] += 1
            self.stats["athletes_existing_matched"] += 1
        elif match_status == MatchStatus.needs_review:
            self.stats["results_needs_review"] += 1
            self.stats["review_required"] += 1
        else:
            self.stats["results_unmatched"] += 1
