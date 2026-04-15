"""
Service pro import dat ze JSON souborů do MongoDB.
Podporuje import z externího zdroje a automatické vytváření entit.
"""
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId
from app.db.database import db
from app.models.result import MatchStatus
from app.services.quality_flag_service import compute_bounds_for_recompute, compute_quality_flag
from app.services.result_matching import (
    build_match_enrichment_update,
    decide_athlete_match,
    normalize_person_name,
)
from app.services.athlete_identity import normalize_fs_code

logger = logging.getLogger(__name__)

athletes_collection = db["athletes"]
categories_collection = db["categories"]
competitions_collection = db["competitions"]
results_collection = db["results"]


class DataImporter:
    """Třída pro import dat z JSON struktury."""

    def __init__(self):
        self.categories_cache: Dict[str, str] = {}  # category_name -> category_id
        self.competitions_cache: Dict[str, str] = {}  # competition_key -> competition_id
        self._bounds_cache: Optional[dict[ObjectId, tuple[float, float]]] = None  # {category_id: (low, high)} percentilové hranice
        self.stats = {
            "total_imported": 0,
            "review_required": 0,
            "athletes_created_new": 0,
            "athletes_existing_matched": 0,
            "categories_created": 0,
            "competitions_created": 0,
            "results_created": 0,
            "results_matched": 0,
            "results_needs_review": 0,
            "results_unmatched": 0,
            "errors": [],
        }

    @staticmethod
    def _normalize_name(value: str) -> str:
        return normalize_person_name(value)

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
            logger.info(f"Zahájen import dat")
            
            # Import soutěže
            competition_data = data.get("competition", {})
            competition_id = await self._import_competition(competition_data)
            
            if not competition_id:
                raise ValueError("Nepodařilo se importovat soutěž")
            
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
            raise


    async def _import_competition(self, comp_data: Dict[str, Any]) -> Optional[str]:
        """Importuje nebo najde existující soutěž."""
        try:
            # Normalizace datumu
            date_str = comp_data.get("date")
            if isinstance(date_str, str):
                # Parsuj na datetime, ne date!
                comp_date = datetime.strptime(date_str, "%Y-%m-%d")
            else:
                comp_date = date_str
            
            # Klíč pro vyhledání duplicit
            comp_key = f"{comp_data.get('name')}_{comp_data.get('place')}_{comp_date}"
            
            # Kontrola cache
            if comp_key in self.competitions_cache:
                return self.competitions_cache[comp_key]
            
            # Kontrola v DB
            existing = await competitions_collection.find_one({
                "name": comp_data.get("name"),
                "place": comp_data.get("place"),
                "date": comp_date
            })
            
            if existing:
                comp_id = str(existing["_id"])
                self.competitions_cache[comp_key] = comp_id
                logger.info(f"Soutěž '{comp_data.get('name')}' již existuje")
                return comp_id
            
            # Normalizace league na pole stringu
            raw_league = comp_data.get("league", [])
            if isinstance(raw_league, str):
                league = [raw_league] if raw_league else []
            elif isinstance(raw_league, list):
                league = [str(item) for item in raw_league if item]
            else:
                league = []

            # Vytvoření nové soutěže
            new_comp = {
                "name": comp_data.get("name", ""),
                "place": comp_data.get("place", ""),
                "date": comp_date,
                "league": league,
                "created_at": datetime.now()
            }
            
            result = await competitions_collection.insert_one(new_comp)
            comp_id = str(result.inserted_id)
            self.competitions_cache[comp_key] = comp_id
            self.stats["competitions_created"] += 1
            logger.info(f"Vytvořena nová soutěž: {comp_data.get('name')} ({comp_id})")
            return comp_id
            
        except Exception as e:
            logger.error(f"Chyba při importu soutěže: {e}", exc_info=True)
            self.stats["errors"].append(f"Soutěž: {str(e)}")
            return None


    async def _import_category_with_results(
        self, category_data: Dict[str, Any], competition_id: str
    ) -> None:
        """Importuje kategorii a její výsledky."""
        try:
            raw_name = category_data.get("name") or ""
            category_name = self._normalize_category_name(raw_name)
            discipline = category_data.get("discipline") or None
            category_id = await self._import_category(category_name, discipline=discipline)
            
            if not category_id:
                logger.warning(f"Nepodařilo se importovat kategorii '{category_name}'")
                return
            
            # Import výsledků
            results = category_data.get("results", [])
            for result_data in results:
                await self._import_result(
                    result_data, category_id, competition_id
                )
                
        except Exception as e:
            logger.error(f"Chyba při importu kategorie: {e}")
            self.stats["errors"].append(f"Kategorie: {str(e)}")


    async def _import_category(self, name: str, *, discipline: Optional[str] = None) -> Optional[str]:
        """Importuje nebo najde existující kategorii."""
        try:
            if not name:
                logger.warning("Přeskočen import kategorie s prázdným nebo null názvem")
                return None

            # Kontrola cache
            if name in self.categories_cache:
                # Doplnit discipline do existující kategorie, pokud chybí
                if discipline:
                    await categories_collection.update_one(
                        {"name": name, "discipline": {"$exists": False}},
                        {"$set": {"discipline": discipline}},
                    )
                return self.categories_cache[name]
            
            # Kontrola v DB
            existing = await categories_collection.find_one({"name": name})
            if existing:
                cat_id = str(existing["_id"])
                self.categories_cache[name] = cat_id
                # Doplnit discipline, pokud v dokumentu chybí
                if discipline and not existing.get("discipline"):
                    await categories_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"discipline": discipline}},
                    )
                return cat_id

            # Při změně kapitalizace znovu použij existující kategorii
            existing_case_insensitive = await categories_collection.find_one(
                {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            )
            if existing_case_insensitive:
                cat_id = str(existing_case_insensitive["_id"])
                self.categories_cache[name] = cat_id

                update_fields = {}
                if existing_case_insensitive.get("name") != name:
                    update_fields["name"] = name
                if discipline and not existing_case_insensitive.get("discipline"):
                    update_fields["discipline"] = discipline

                if update_fields:
                    await categories_collection.update_one(
                        {"_id": existing_case_insensitive["_id"]},
                        {"$set": update_fields},
                    )
                return cat_id
            
            # Vytvoření nové kategorie
            new_cat = {"name": name, "created_at": datetime.now()}
            if discipline:
                new_cat["discipline"] = discipline
            result = await categories_collection.insert_one(new_cat)
            cat_id = str(result.inserted_id)
            self.categories_cache[name] = cat_id
            self.stats["categories_created"] += 1
            logger.info(f"Vytvořena nová kategorie: {name}")
            return cat_id
            
        except Exception as e:
            logger.error(f"Chyba při importu kategorie: {e}")
            return None


    async def _import_result(
        self, result_data: Dict[str, Any], category_id: str, competition_id: str
    ) -> None:
        """Importuje výsledek (a případně atleta)."""
        try:
            self.stats["total_imported"] += 1

            competition = await competitions_collection.find_one({
                "_id": ObjectId(competition_id)
            })
            competition_date = competition.get("date") if competition else None

            raw_team = result_data.get("team").replace("SDH", "").strip() if result_data.get("team") else None
            team = self._normalize_team_name(raw_team) if raw_team else None

            imported_athlete = self._extract_imported_athlete_data(result_data)
            match = await decide_athlete_match(**imported_athlete, team=team)
            created_new_athlete = False
            if match["match_status"] == MatchStatus.unmatched:
                created_athlete_id = await self._create_athlete_from_imported_result(
                    imported_athlete=imported_athlete,
                    team=team,
                )
                if created_athlete_id:
                    athlete_id = created_athlete_id
                    created_new_athlete = True
                    match = {
                        "match_status": MatchStatus.matched,
                        "match_reason": "auto_created_from_unmatched",
                        "matched_athlete": {"_id": ObjectId(created_athlete_id)},
                    }
                else:
                    athlete_id = None
            else:
                matched_athlete = match.get("matched_athlete")
                athlete_id = str(matched_athlete["_id"]) if matched_athlete else None
                if athlete_id and matched_athlete:
                    enrichment_update = build_match_enrichment_update(
                        athlete=matched_athlete,
                        imported_athlete=imported_athlete,
                        team=team,
                        match_reason=match.get("match_reason"),
                    )
                    if enrichment_update:
                        await athletes_collection.update_one(
                            {"_id": ObjectId(athlete_id)},
                            enrichment_update,
                        )

            times_raw = result_data.get("times", [])
            
            # Transformace times - mapuj "try" -> "attempt"
            times_transformed = []
            for t_data in times_raw:
                try_num = t_data.get("try")
                # Transformuj na formát s "attempt" místo "try"
                times_transformed.append({
                    "attempt": try_num if try_num else None,
                    "time": t_data.get("time"),
                    "status": t_data.get("status", "invalid")
                })
            
            result_doc = {
                "competition": ObjectId(competition_id),
                "category": ObjectId(category_id),
                "date": competition_date,
                "team": team,
                "imported_athlete": imported_athlete,
                "match_status": match["match_status"].value,
                "match_reason": match.get("match_reason"),
                "start_number": result_data.get("start_number"),
                "final_time": result_data.get("final_time"),
                "final_time_status": result_data.get("final_status", "invalid"),
                "rank": result_data.get("rank"),
                "times": times_transformed,
                "created_at": datetime.now()
            }
            if athlete_id:
                result_doc["athlete"] = ObjectId(athlete_id)

            duplicate_query = {
                "competition": ObjectId(competition_id),
                "category": ObjectId(category_id),
                "imported_athlete.first_name": imported_athlete["first_name"],
                "imported_athlete.last_name": imported_athlete["last_name"],
                "start_number": result_data.get("start_number"),
            }
            if imported_athlete["birth_year"] is not None:
                duplicate_query["imported_athlete.birth_year"] = imported_athlete["birth_year"]
            if imported_athlete["fscode"] is not None:
                duplicate_query["imported_athlete.fscode"] = imported_athlete["fscode"]

            existing = await results_collection.find_one(duplicate_query)
            
            if not existing:
                # Výpočet quality_flag
                try:
                    if self._bounds_cache is None and athlete_id:
                        self._bounds_cache = await compute_bounds_for_recompute(db)
                    if athlete_id:
                        flag = await compute_quality_flag(db, result_doc, bounds_cache=self._bounds_cache)
                        result_doc["quality_flag"] = flag.value
                    else:
                        result_doc["quality_flag"] = "ok"
                except Exception as qf_err:
                    logger.warning("Nepodařilo se vypočítat quality_flag: %s", qf_err)
                    result_doc["quality_flag"] = "ok"

                await results_collection.insert_one(result_doc)
                self.stats["results_created"] += 1
                self._increment_match_stats(
                    match["match_status"],
                    created_new_athlete=created_new_athlete,
                )
            
        except Exception as e:
            logger.error(f"Chyba při importu výsledku: {e}")
            self.stats["errors"].append(f"Výsledek: {str(e)}")


    def _extract_imported_athlete_data(self, result_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fscode": normalize_fs_code(result_data.get("fscode")),
            "first_name": self._normalize_name(result_data.get("first_name", "")),
            "last_name": self._normalize_name(result_data.get("last_name", "")),
            "birth_year": result_data.get("birth_year") or None,
        }

    async def _create_athlete_from_imported_result(
        self,
        *,
        imported_athlete: Dict[str, Any],
        team: Optional[str],
    ) -> Optional[str]:
        first_name = (imported_athlete.get("first_name") or "").strip()
        last_name = (imported_athlete.get("last_name") or "").strip()
        if not first_name or not last_name:
            return None

        athlete_doc = {
            "first_name": first_name,
            "last_name": last_name,
            "birth_year": imported_athlete.get("birth_year"),
            "fs_codes": (
                [imported_athlete.get("fscode")]
                if imported_athlete.get("fscode")
                else []
            ),
            "teams": [team] if team else [],
            "is_active": True,
            "merged_into_athlete_id": None,
            "created_at": datetime.now(),
        }
        result = await athletes_collection.insert_one(athlete_doc)
        return str(result.inserted_id)

    def _increment_match_stats(
        self,
        match_status: MatchStatus,
        *,
        created_new_athlete: bool = False,
    ) -> None:
        if match_status == MatchStatus.matched:
            self.stats["results_matched"] += 1
            if created_new_athlete:
                self.stats["athletes_created_new"] += 1
            else:
                self.stats["athletes_existing_matched"] += 1
        elif match_status == MatchStatus.needs_review:
            self.stats["results_needs_review"] += 1
            self.stats["review_required"] += 1
        else:
            self.stats["results_unmatched"] += 1
