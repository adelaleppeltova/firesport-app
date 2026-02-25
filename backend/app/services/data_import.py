"""
Service pro import dat ze JSON souborů do MongoDB.
Podporuje import z externího zdroje a automatické vytváření entit.
"""
import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from bson import ObjectId
from app.db.database import db

logger = logging.getLogger(__name__)

athletes_collection = db["athletes"]
categories_collection = db["categories"]
competitions_collection = db["competitions"]
results_collection = db["results"]


class DataImporter:
    """Třída pro import dat z JSON struktury."""

    def __init__(self):
        self.athletes_cache: Dict[int, str] = {}  # fscode -> athlete_id
        self.categories_cache: Dict[str, str] = {}  # category_name -> category_id
        self.competitions_cache: Dict[str, str] = {}  # competition_key -> competition_id
        self.stats = {
            "athletes_created": 0,
            "athletes_skipped": 0,
            "categories_created": 0,
            "competitions_created": 0,
            "results_created": 0,
            "errors": [],
        }

    @staticmethod
    def _normalize_name(value: str) -> str:
        return "".join(part[:1].upper() + part[1:].lower() for part in value.strip().split())

    @staticmethod
    def _normalize_category_name(value: str) -> str:
        """Převede název kategorie tak, aby měl první písmeno velké a zbytek malý (např. 'ŽENY' -> 'Ženy')."""
        stripped = value.strip()
        if not stripped:
            return stripped
        return stripped[0].upper() + stripped[1:].lower()


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
            
            # Vytvoření nové soutěže
            new_comp = {
                "name": comp_data.get("name", ""),
                "place": comp_data.get("place", ""),
                "date": comp_date,
                "league": comp_data.get("league", ""),
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
            category_id = await self._import_category(category_name)
            
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


    async def _import_category(self, name: str) -> Optional[str]:
        """Importuje nebo najde existující kategorii."""
        try:
            if not name:
                logger.warning("Přeskočen import kategorie s prázdným nebo null názvem")
                return None

            # Kontrola cache
            if name in self.categories_cache:
                return self.categories_cache[name]
            
            # Kontrola v DB
            existing = await categories_collection.find_one({"name": name})
            if existing:
                cat_id = str(existing["_id"])
                self.categories_cache[name] = cat_id
                return cat_id
            
            # Vytvoření nové kategorie
            new_cat = {"name": name, "created_at": datetime.now()}
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
            competition = await competitions_collection.find_one({
                "_id": ObjectId(competition_id)
            })
            competition_date = competition.get("date") if competition else None

            team = result_data.get("team").replace("SDH", "").strip() if result_data.get("team") else None

            # Importuj či najdi atleta
            athlete_id = await self._import_or_get_athlete(result_data, team)
            if not athlete_id:
                logger.warning(f"Nepodařilo se zpracovat atleta")
                return

            times_raw = result_data.get("times", [])
            time_1 = None
            time_2 = None
            
            # Transformace times - mapuj "try" -> "attempt"
            times_transformed = []
            for t_data in times_raw:
                try_num = t_data.get("try")
                if try_num == 1:
                    time_1 = t_data.get("time")
                elif try_num == 2:
                    time_2 = t_data.get("time")
                
                # Transformuj na formát s "attempt" místo "try"
                times_transformed.append({
                    "attempt": try_num if try_num else None,
                    "time": t_data.get("time"),
                    "status": t_data.get("status", "invalid")
                })
            
            result_doc = {
                "athlete": ObjectId(athlete_id),
                "competition": ObjectId(competition_id),
                "category": ObjectId(category_id),
                "date": competition_date,
                "team": team,
                "start_number": result_data.get("start_number"),
                "time_1": time_1,
                "time_1_status": "valid" if time_1 else "invalid",
                "time_2": time_2,
                "time_2_status": "valid" if time_2 else "invalid",
                "final_time": result_data.get("final_time"),
                "final_time_status": result_data.get("final_status", "invalid"),
                "rank": result_data.get("rank"),
                "times": times_transformed,
                "created_at": datetime.now()
            }
            
            # Kontrola duplicit (stejný atleta + soutěž + kategorie)
            existing = await results_collection.find_one({
                "athlete": ObjectId(athlete_id),
                "competition": ObjectId(competition_id),
                "category": ObjectId(category_id)
            })
            
            if not existing:
                await results_collection.insert_one(result_doc)
                self.stats["results_created"] += 1
            
        except Exception as e:
            logger.error(f"Chyba při importu výsledku: {e}")
            self.stats["errors"].append(f"Výsledek: {str(e)}")


    async def _find_by_name(
        self,
        first_name: str,
        last_name: str,
    ):
        """Najde závodníka podle jména a příjmení."""
        if not first_name or not last_name:
            return None
        
        existing = await athletes_collection.find_one({
            "first_name": first_name,
            "last_name": last_name
        })
        return existing


    async def _import_or_get_athlete(self, result_data: Dict[str, Any], team: Optional[str] = None) -> Optional[str]:
        """Importuje atleta nebo vrátí existující."""
        try:
            fscode = result_data.get("fscode") or None
            first_name = self._normalize_name(result_data.get("first_name", ""))
            last_name = self._normalize_name(result_data.get("last_name", ""))
            birth_year = result_data.get("birth_year") or None
            district = result_data.get("district") or None

            existing = None

            # 1. Primární vyhledávání podle fscode
            if fscode:
                existing = await athletes_collection.find_one({"fscode": fscode})

            # 2. Vyhledávání podle jména a příjmení
            if not existing and first_name and last_name:
                existing = await self._find_by_name(first_name, last_name)

            # 3. Nalezený závodník – doplnit pouze chybějící skalární hodnoty + přidat team do pole teams
            if existing:
                new_values = {
                    "first_name": first_name or None,
                    "last_name": last_name or None,
                    "birth_year": birth_year,
                    "fscode": fscode,
                    "district": district,
                }
                update_fields = {
                    field: value
                    for field, value in new_values.items()
                    if value is not None and not existing.get(field)
                }
                update: Dict[str, Any] = {}
                if update_fields:
                    update_fields["updated_at"] = datetime.now()
                    update["$set"] = update_fields
                if team:
                    update["$addToSet"] = {"teams": team}
                if update:
                    await athletes_collection.update_one({"_id": existing["_id"]}, update)
                    logger.info(
                        f"Aktualizován závodník {first_name} {last_name}: set={list(update_fields.keys()) if update_fields else []}, team={team}"
                    )
                elif team:
                    # I když není co doplňovat, přidej team
                    await athletes_collection.update_one(
                        {"_id": existing["_id"]},
                        {"$addToSet": {"teams": team}}
                    )
                return str(existing["_id"])

            # 4. Vytvoření nového závodníka
            athlete_doc: Dict[str, Any] = {
                "first_name": first_name,
                "last_name": last_name,
                "birth_year": birth_year,
                "fscode": fscode,
                "district": district,
                "teams": [team] if team else [],
                "created_at": datetime.now(),
            }

            result = await athletes_collection.insert_one(athlete_doc)
            new_athlete_id = str(result.inserted_id)

            if fscode:
                self.athletes_cache[fscode] = new_athlete_id

            self.stats["athletes_created"] += 1
            logger.info(f"Vytvořen nový atleta: {first_name} {last_name}")
            return new_athlete_id

        except Exception as e:
            logger.error(f"Chyba při importu atleta: {e}", exc_info=True)
            return None


async def import_json_file(file_path: str) -> Dict[str, Any]:
    """Bezpečně importuje JSON soubor a vrátí statistiky."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        importer = DataImporter()
        await importer.import_from_dict(data)
        return importer.stats
        
    except json.JSONDecodeError as e:
        logger.error(f"Chyba při parsování JSON {file_path}: {e}")
        return {"errors": [f"JSON parse error: {str(e)}"]}
    except Exception as e:
        logger.error(f"Chyba při importu souboru {file_path}: {e}")
        return {"errors": [str(e)]}
