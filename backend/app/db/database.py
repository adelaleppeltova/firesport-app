from motor.motor_asyncio import AsyncIOMotorClient
from os import getenv

MONGO_URL = getenv("MONGO_URL", "mongodb://mongo:27017")
client = AsyncIOMotorClient(MONGO_URL)
db = client["firesport"]

users_col = db["users"]
sessions_col = db["sessions"]

# Indexy při startu
async def ensure_indexes():
    await users_col.create_index("email", unique=True)
    await sessions_col.create_index("session_id", unique=True)
    await sessions_col.create_index("expires_at", expireAfterSeconds=0)  # TTL
