
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
    await sessions_col.create_index("session_id", unique=True)
    await sessions_col.create_index("expires_at", expireAfterSeconds=0)  # TTL
    
    # anomaly_runs indexes
    await db["anomaly_runs"].create_index("run_id", unique=True, name="idx_run_id_unique")
    await db["anomaly_runs"].create_index([("summary.athlete_id", 1), ("created_at", -1)], name="idx_athlete_created_at")
    
    # anomaly_scores indexes
    await db["anomaly_scores"].create_index([("run_id", 1), ("result_id", 1)], unique=True, name="idx_run_result_unique")
    await db["anomaly_scores"].create_index([("athlete_id", 1), ("competition_date", -1)], name="idx_athlete_competition")
    await db["anomaly_scores"].create_index("run_id", name="idx_run_id")
    
    # results indexes
    await db["results"].create_index([("athlete_id", 1), ("final_status", 1), ("competition_date", 1)], name="idx_athlete_status_date")
