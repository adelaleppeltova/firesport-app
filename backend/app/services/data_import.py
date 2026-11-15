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
from app.services.external_identity import ExternalIdentity, ExternalIdentitySidecar
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

    @staticmethod
    def _normalize_team_name(value: str) -> str:
        """
        Converts team name to proper case with Czech-style capitalization.
        - Prepositions (u, nad, pod, v, z, na, do, od) are lowercase
        - Other words are title case
        - Acronyms like 'HZS', 'VHJ', 'ČHJ', 'PS' stay uppercase
        - Hyphenated words: both parts follow same rules

        Examples:
        - 'DOLNÍ LHOTA' -> 'Dolní Lhota'
        - 'KAMENEC U POLIČKY' -> 'Kamenec u Poličky'
        - 'NAD MORAVOU' -> 'Nad Moravou'
        - 'DOLNÍ-DVŮR' -> 'Dolní-Dvůr'
        """
        KEEP_UPPER = {"hzs", "vhj", "čhj", "ps"}
        LOWERCASE_WORDS = {"u", "nad", "pod", "v", "z", "na", "do", "od"}

        stripped = value.strip()
        if not stripped:
            return stripped

        result = []
        words = stripped.split()

        for word in words:
            # Handle hyphenated words (e.g., 'DOLNÍ-DVŮR')
            if "-" in word:
                parts = word.split("-")
                normalized_parts = []
                for part in parts:
                    if part:
                        lower = part.lower()
                        if lower in KEEP_UPPER:
                            normalized_parts.append(lower.upper())
                        elif lower in LOWERCASE_WORDS:
                            normalized_parts.append(lower)
                        else:
                            normalized_parts.append(part[0].upper() + part[1:].lower() if len(part) > 1 else part.upper())
                    else:
                        normalized_parts.append(part)
                result.append("-".join(normalized_parts))
            else:
                lower = word.lower()
                if lower in KEEP_UPPER:
                    result.append(lower.upper())
                elif lower in LOWERCASE_WORDS:
                    result.append(lower)
                else:
                    result.append(word[0].upper() + word[1:].lower() if len(word) > 1 else word.upper())

        return " ".join(result)


    async def import_from_dict(
        self, data: Dict[str, Any], *, verified_blocks: Optional[dict[int, str]] = None,
        external_sidecar: ExternalIdentitySidecar | None = None,
    ) -> Dict[str, Any]:
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

            competition_data = data.get("competition", {})
            categories = competition_data.get("categories", [])
            if external_sidecar is not None:
                external_sidecar.validate_for(data, categories)
            blocks = verified_blocks or {}
            if any(index not in range(len(categories)) or not isinstance(block, str) or not block.strip()
                   for index, block in blocks.items()):
                raise ValueError("Neplatný identifikátor výsledkové listiny.")
            keys = [
                (self._normalize_category_name(category.get("name") or "").casefold(),
                 category.get("discipline") or None)
                for category in categories
            ]
            scopes = [(key, blocks.get(i)) for i, key in enumerate(keys)]
            counts = Counter(scopes)
            repeated_categories = Counter(keys)
            # The source format may have identical captions for different lists.
            # Block identifiers must come from verified source evidence, never their order.
            if any(counts[(key, block)] > 1 or (repeated_categories[key] > 1 and block is None)
                   for key, block in scopes):
                raise ValueError("Nejednoznačné výsledkové listiny: vyžadují ověřené identifikátory.")

            source = urlsplit(data.get("source_file") or "")
            source_url = source._replace(fragment="").geturl() if source.scheme in ("http", "https") and source.netloc else None
            competition_id = await self._import_competition(competition_data, source_url=source_url)

            external_rows = external_sidecar.categories if external_sidecar else {}
            for index, category_data in enumerate(categories):
                await self._import_category_with_results(
                    category_data, competition_id, block_id=blocks.get(index),
                    external_rows=external_rows.get(index),
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
            existing and source_url and existing[0].get("source_url") != source_url
        ):
            raise ValueError(f"Nejednoznačná identita závodu {metadata['name']} ({comp_date.date()}).")
        if existing:
            return str(existing[0]["_id"])

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
        self, category_data: Dict[str, Any], competition_id: str, *, block_id: Optional[str] = None,
        external_rows: dict[int, ExternalIdentity] | None = None
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
            observations = external_rows or {}
            for index, result_data in enumerate(results):
                row_key = json.dumps(result_data, sort_keys=True)
                if row_counts[row_key] > 1:
                    self.stats["errors"].append(
                        f"Kategorie {category_name}: nerozlišitelné řádky ve vstupním souboru."
                    )
                    continue
                await self._import_result(
                    result_data, category_id, competition_id, block_id=block_id,
                    external_identity=observations.get(index),
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
        matching = [doc for doc in candidates if (doc.get("discipline") or None) == discipline]
        if len(matching) > 1 or (not discipline and len(candidates) != len(matching)):
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
        self, result_data: Dict[str, Any], category_id: str, competition_id: str,
        *, block_id: Optional[str] = None, external_identity: ExternalIdentity | None = None,
    ) -> None:
        """Importuje nový řádek a existující výkon ponechá beze změny."""
        try:
            row = self.build_result_row(result_data, category_id, competition_id, block_id=block_id)
            team = row["team"]
            imported_athlete = row["imported_athlete"]
            competition = await competitions_collection.find_one({"_id": ObjectId(competition_id)})
            if await self._existing_result(row):
                return

            match = await decide_athlete_match(
                **imported_athlete, team=team, external_identity=external_identity,
            )
            result_doc = {
                "_id": _import_id("result", self._row_identity(row)),
                **row,
                **({"external_identity": external_identity.model_dump()} if external_identity else {}),
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
                stored = await results_collection.find_one({"_id": result_doc["_id"]})
                if stored is None or self._row_identity(row) != self._row_identity(stored):
                    raise ValueError("Kolize identifikátoru výsledku s odlišným obsahem.")
                self.stats["results_duplicates_skipped"] += 1
                return

            self.stats["total_imported"] += 1
            self.stats["results_created"] += 1
            self._increment_match_stats(match["match_status"])
        except Exception as exc:
            self.stats["errors"].append(f"Výsledek: {exc}")
            logger.error("Chyba při importu výsledku: %s", exc)

    def build_result_row(
        self, result_data: dict, category_id: str, competition_id: str,
        *, block_id: Optional[str] = None,
    ) -> dict:
        imported_team = result_data.get("team")
        raw_team = (imported_team or "").replace("SDH", "").strip()
        team = self._normalize_team_name(raw_team) if raw_team else None
        start_number = self._parse_start_number(result_data.get("start_number"))
        imported_athlete = self._extract_imported_athlete_data(result_data)
        return {
            "competition": ObjectId(competition_id),
            "category": ObjectId(category_id),
            **({"result_list_id": block_id} if block_id is not None else {}),
            "team": team,
            "imported_team": imported_team,
            "district": result_data.get("district"),
            "imported_athlete": imported_athlete,
            "start_number": start_number,
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

    @staticmethod
    def _parse_start_number(value: Any) -> Optional[int]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        if type(value) is int or (isinstance(value, str) and re.fullmatch(r"[0-9]+", value.strip())):
            return int(value)
        raise ValueError(f"Neplatné startovní číslo {value!r}.")

    @staticmethod
    def _row_identity(row: dict) -> dict:
        athlete = row.get("imported_athlete") or {}
        start_number = DataImporter._parse_start_number(row.get("start_number"))
        # Compare the representation written by both the old and new importer.
        team = re.sub(r"\bSDH\b", "", row.get("team") or "", flags=re.IGNORECASE)
        return {
            "competition": row["competition"],
            "category": row["category"],
            "result_list_id": row.get("result_list_id"),
            "team": " ".join(team.split()).casefold(),
            "district": row.get("district") or None,
            "name": tuple(
                normalize_person_name(athlete.get(field)).casefold()
                for field in ("first_name", "last_name")
            ),
            "birth_year": athlete.get("birth_year"),
            "fscode": normalize_fs_code(athlete.get("fscode")),
            "start_number": str(start_number) if start_number is not None else None,
            "rank": row.get("rank"),
            "final_time": float(row["final_time"]) if row.get("final_time") is not None else None,
            "final_time_status": row.get("final_time_status"),
            "times": [
                (attempt.get("attempt"), float(attempt["time"]) if attempt.get("time") is not None else None,
                 attempt.get("status"), attempt.get("invalid_reason") or None)
                for attempt in row.get("times") or []
            ],
        }

    @staticmethod
    def _result_relationship(incoming: dict, stored: dict) -> Optional[str]:
        """Compare rows within the same event and category, independent of profile assignment."""
        current_list = incoming["result_list_id"]
        stored_list = stored["result_list_id"]
        if current_list and stored_list and current_list != stored_list:
            return None

        same_number = incoming["start_number"] is not None and incoming["start_number"] == stored["start_number"]
        same_code = incoming["fscode"] is not None and incoming["fscode"] == stored["fscode"]
        same_year = incoming["birth_year"] is not None and incoming["birth_year"] == stored["birth_year"]
        complete_names = all(incoming["name"]) and all(stored["name"])
        same_name = complete_names and incoming["name"] == stored["name"]
        different_year = all(r["birth_year"] is not None for r in (incoming, stored)) and not same_year
        different_code = all(r["fscode"] is not None for r in (incoming, stored)) and not same_code
        different_number = all(r["start_number"] is not None for r in (incoming, stored)) and not same_number

        if not same_code and (
            (complete_names and not same_name and (different_year or different_code))
            or (same_name and different_number and (different_year or different_code))
        ):
            return None

        performance = ("rank", "final_time", "final_time_status", "times")
        same_performance = all(incoming[key] == stored[key] for key in performance)
        known_performance = (same_number or incoming["rank"] is not None or incoming["final_time"] is not None
                             or any(attempt[1] is not None for attempt in incoming["times"]))
        if (same_name and (same_number or same_code or same_year) and known_performance
                and not (different_year or different_code or different_number)):
            # A legacy unlabelled result can prevent duplication, but cannot be attributed
            # to a particular list by this comparison.
            if same_performance and current_list == stored_list:
                districts = (incoming["district"], stored["district"])
                return "review" if all(districts) and districts[0] != districts[1] else "duplicate"
            return "review"

        same_rank = incoming["rank"] is not None and incoming["rank"] == stored["rank"]
        if same_number or same_code or same_name or (same_rank and not complete_names):
            return "review"
        return None

    def assess_result(self, row: dict, candidates) -> tuple[str, list]:
        identity = self._row_identity(row)
        duplicate_ids = []
        review_ids = []
        for existing in candidates:
            stored = self._row_identity(existing)
            relationship = self._result_relationship(identity, stored)
            if bool(identity["result_list_id"]) != bool(stored["result_list_id"]):
                relationship = "review"
            if relationship == "duplicate":
                duplicate_ids.append(existing["_id"])
            elif relationship == "review":
                review_ids.append(existing["_id"])

        if len(duplicate_ids) == 1 and not review_ids:
            return "duplicate", duplicate_ids
        if duplicate_ids or review_ids:
            return "review", duplicate_ids + review_ids
        return "insert", []

    async def _existing_result(self, row: dict) -> bool:
        scope = {key: row[key] for key in ("competition", "category")}
        candidates = [existing async for existing in results_collection.find(scope)]
        action, ids = self.assess_result(row, candidates)
        if action == "duplicate":
            self.stats["results_duplicates_skipped"] += 1
            return True
        if action == "review":
            raise ValueError(
                f"Nejednoznačný řádek závodu {row['competition']}, kategorie {row['category']} "
                f"(startovní číslo {row['start_number']}, pořadí {row['rank']}, "
                f"kandidáti {', '.join(map(str, ids))})."
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
