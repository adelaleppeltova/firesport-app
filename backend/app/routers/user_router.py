from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from pymongo import MongoClient
import os

router = APIRouter(prefix="/user", tags=["user"])

# Synchronní PyMongo client
MONGO_URL = os.getenv("MONGO_URL", "mongodb://firesport-mongodb:27017")
sync_client = MongoClient(MONGO_URL)
sync_db = sync_client["firesport"]
users_collection = sync_db["users"]
athletes_collection = sync_db["athletes"]
activities_collection = sync_db["activities"]

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    """Vrátí údaje o aktuálně přihlášeném uživateli"""
    return {
        "user_id": user["id"],
        "email": user["email"],
        "athlete_id": user.get("athlete_id")  # může být None
    }

@router.patch("/me/athlete")
def pair_athlete(athlete_id: str, user=Depends(get_current_user)):
    """Spáruje uživatele s atletem"""
    from bson import ObjectId
    
    users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"athlete_id": athlete_id}}
    )
    
    return {"ok": True}