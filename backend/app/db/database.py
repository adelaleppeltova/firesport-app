
from motor.motor_asyncio import AsyncIOMotorClient
from os import getenv

MONGO_URL = getenv("MONGO_URL", "mongodb://mongo:27017")
client = AsyncIOMotorClient(MONGO_URL)
db = client["firesport"]

users_col = db["users"]
sessions_col = db["sessions"]

def get_db():
    return db

# Indexy při startu
async def ensure_indexes():
    await users_col.create_index("email", unique=True)
    await users_col.create_index("role")
    await sessions_col.create_index("session_id", unique=True)
    await sessions_col.create_index("expires_at", expireAfterSeconds=0)  # TTL
    await db["athletes"].create_index("fscode", name="idx_athletes_fscode")
    await db["athletes"].create_index("fs_codes", name="idx_athletes_fs_codes")
    await db["athletes"].create_index(
        [("first_name", 1), ("last_name", 1), ("birth_year", 1)],
        name="idx_athletes_identity",
    )
    
    # anomaly_runs indexes
    await db["anomaly_runs"].create_index("run_id", unique=True, name="idx_run_id_unique")
    await db["anomaly_runs"].create_index([("summary.athlete_id", 1), ("created_at", -1)], name="idx_athlete_created_at")
    
    # anomaly_scores indexes
    await db["anomaly_scores"].create_index([("run_id", 1), ("result_id", 1)], unique=True, name="idx_run_result_unique")
    await db["anomaly_scores"].create_index([("athlete_id", 1), ("competition_date", -1)], name="idx_athlete_competition")
    await db["anomaly_scores"].create_index("run_id", name="idx_run_id")
    
    # results indexes
    await db["results"].create_index(
        [("athlete", 1), ("final_time_status", 1), ("date", 1)],
        name="idx_results_athlete_status_date",
    )
    await db["results"].create_index("match_status", name="idx_results_match_status")
    await db["results"].create_index(
        [
            ("competition", 1),
            ("category", 1),
            ("imported_athlete.first_name", 1),
            ("imported_athlete.last_name", 1),
            ("imported_athlete.birth_year", 1),
        ],
        name="idx_results_import_identity",
    )
