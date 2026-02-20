from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from app.dependencies import get_current_user
from pydantic import BaseModel
import logging
from app.db.database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/me", tags=["user"])

class PairAthleteRequest(BaseModel):
    athlete_id: str

@router.get("")
def get_me(user=Depends(get_current_user)):
    """Vrátí údaje o aktuálně přihlášeném uživateli"""
    return {
        "user_id": user["id"],
        "email": user["email"],
        "athlete_id": user.get("athlete_id")
    }

@router.patch("/pair-athlete")
def pair_athlete(body: PairAthleteRequest, user=Depends(get_current_user)):
    """Spáruje uživatele s atletem"""
    from app.dependencies import sync_db
    from bson import ObjectId
    
    logger.info(f"Pairing user {user['id']} with athlete {body.athlete_id}")
    
    # Použij existující sync_db z dependencies
    users_collection = sync_db["users"]
    
    result = users_collection.update_one(
        {"_id": ObjectId(user["id"])},
        {"$set": {"athlete_id": body.athlete_id}}
    )
    
    logger.info(f"Matched: {result.matched_count}, Modified: {result.modified_count}")
    
    return {"ok": True, "athlete_id": body.athlete_id}
