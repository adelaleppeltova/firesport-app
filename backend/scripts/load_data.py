#!/usr/bin/env python3
"""
Seed script pro automatický import dat ze složky /app/data do MongoDB.
Entrypoint jej při startu Docker kontejneru spustí pouze s IMPORT_DATA=true.

Použití:
    python scripts/load_data.py
    
Očekává struktura:
    /app/data/*/
        *.json (JSON soubory s výsledky závodů)
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# Add app to path - ale NEIMPORTUJ data_import ZATÍM!
sys.path.insert(0, '/app')

MONGO_URL = "mongodb://mongo:27017"
DATA_DIR = Path("/app/data")
MAX_RETRIES = 30
RETRY_DELAY = 1


async def wait_for_mongo():
    """Čeká dokud není MongoDB připravena."""
    for attempt in range(MAX_RETRIES):
        try:
            client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            await client.admin.command('ping')
            logger.info("✓ MongoDB je připravena!")
            client.close()
            return True
        except Exception as e:
            attempt_num = attempt + 1
            logger.info(f"⏳ Pokus {attempt_num}/{MAX_RETRIES}: Čekání na MongoDB... ({e})")
            await asyncio.sleep(RETRY_DELAY)
    
    logger.error(f"✗ MongoDB se nepodařilo připojit po {MAX_RETRIES} pokusech")
    return False


async def load_all_json_files():
    """Najde a importuje všechny JSON soubory ze složky data/."""
    # TEPRVE TEĎKA importuj DataImporter - po čekání na MongoDB!
    from app.services.data_import import DataImporter
    from app.db.database import db
    
    # Smaz existující kolekce results a competitions
    results_collection = db["results"]
    competitions_collection = db["competitions"]
    athletes_collection = db["athletes"]
    categories_collection = db["categories"]
    anomaly_runs_collection = db["anomaly_runs"]
    anomaly_scores_collection = db["anomaly_scores"]
    
    await results_collection.delete_many({})
    await competitions_collection.delete_many({})
    await athletes_collection.delete_many({})
    await categories_collection.delete_many({})
    await anomaly_runs_collection.delete_many({})
    await anomaly_scores_collection.delete_many({})
    logger.info("✓ Smazány všechny existující výsledky, soutěže, atleti, kategorie a anomálie z MongoDB pro čistý start")
    
    # Kontrola existence složky
    if not DATA_DIR.exists():
        logger.warning(f"Složka {DATA_DIR} neexistuje - přeskočit import")
        return
    
    # Najdi všechny JSON soubory
    json_files = list(DATA_DIR.rglob("*.json"))
    
    if not json_files:
        logger.info(f"Žádné JSON soubory nalezeny v {DATA_DIR}")
        return
    
    logger.info(f"Nalezeno {len(json_files)} JSON souborů k importu")
    
    total_stats = {
        "athletes_created": 0,
        "athletes_skipped": 0,
        "categories_created": 0,
        "competitions_created": 0,
        "results_created": 0,
        "errors": []
    }
    
    for json_file in sorted(json_files):
        try:
            logger.info(f"Importuji: {json_file}")
            
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            importer = DataImporter()
            stats = await importer.import_from_dict(data)
            
            # Agregace statistik
            total_stats["athletes_created"] += stats.get("athletes_created", 0)
            total_stats["athletes_skipped"] += stats.get("athletes_skipped", 0)
            total_stats["categories_created"] += stats.get("categories_created", 0)
            total_stats["competitions_created"] += stats.get("competitions_created", 0)
            total_stats["results_created"] += stats.get("results_created", 0)
            total_stats["errors"].extend(stats.get("errors", []))
            
            logger.info(f"✓ Import souboru {json_file.name} dokončen: {stats}")
            
        except json.JSONDecodeError as e:
            error_msg = f"JSON parse error v {json_file}: {e}"
            logger.error(error_msg)
            total_stats["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Chyba při importu {json_file}: {e}"
            logger.error(error_msg, exc_info=True)
            total_stats["errors"].append(error_msg)
    
    logger.info("=" * 60)
    logger.info("SOUHRN IMPORTU")
    logger.info("=" * 60)
    logger.info(f"✓ Atleti: {total_stats['athletes_created']} nových, {total_stats['athletes_skipped']} existujících")
    logger.info(f"✓ Kategorie: {total_stats['categories_created']} nových")
    logger.info(f"✓ Soutěže: {total_stats['competitions_created']} nových")
    logger.info(f"✓ Výsledky: {total_stats['results_created']} importováno")
    
    if total_stats["errors"]:
        logger.warning(f"⚠ Chyby ({len(total_stats['errors'])}): {total_stats['errors']}")
    else:
        logger.info("✓ Bez chyb!")
    
    logger.info("=" * 60)


async def main():
    """Hlavní funkce - čeka na Mongo, pak importuje data."""
    logger.info("=" * 60)
    logger.info("SPOUŠTĚNÍ SEED SCRIPTU")
    logger.info("=" * 60)
    
    # Nejdříve čekej na Mongo
    if not await wait_for_mongo():
        logger.error("Nemůžu pokračovat bez MongoDB")
        sys.exit(1)
    
    # Pak importuj data
    try:
        await load_all_json_files()
        logger.info("✓ Seed script dokončen úspěšně")
    except Exception as e:
        logger.error(f"Fatální chyba: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
